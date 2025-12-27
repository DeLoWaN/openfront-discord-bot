from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol, Set, cast

import discord
import discord.abc
from discord import app_commands
from discord.ext import commands

from .central_db import (
    get_guild_entry,
    init_central_db,
    list_active_guilds,
    register_guild,
    remove_guild,
)
from .config import BotConfig, load_config
from .models import (
    GuildModels,
    RoleThresholdExistsError,
    init_guild_db,
    record_audit,
    seed_admin_roles,
    upsert_role_threshold,
    utcnow_naive,
)
from .openfront import OpenFrontClient, OpenFrontError
from .wins import (
    compute_wins_sessions_since_link,
    compute_wins_sessions_with_clan,
    compute_wins_total,
    last_session_username,
)

# Default to INFO until the configured level is applied at startup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
LOGGER = logging.getLogger(__name__)

COUNTING_MODES = ["total", "sessions_since_link", "sessions_with_clan"]
Threshold = Any


class SupportsGuild(Protocol):
    id: int

    def get_role(self, role_id: int) -> Any | None: ...


class SupportsMember(Protocol):
    id: int
    roles: Iterable[Any]
    guild: SupportsGuild
    display_name: str

    async def add_roles(self, *roles: Any, **kwargs: Any) -> Any: ...

    async def remove_roles(self, *roles: Any, **kwargs: Any) -> Any: ...


@dataclass
class GuildContext:
    guild_id: int
    database_path: str
    models: GuildModels
    admin_role_ids: Set[int]
    sync_lock: asyncio.Lock


async def determine_target_role(
    guild: SupportsGuild,
    thresholds: Iterable[Threshold],
    win_count: int,
) -> Any | None:
    target_id = None
    for threshold in sorted(thresholds, key=lambda t: t.wins):
        if threshold.wins <= win_count and threshold.role_id:
            target_id = threshold.role_id
    if target_id:
        role = guild.get_role(target_id)
        return role
    return None


def threshold_role_ids(thresholds: Iterable[Threshold]) -> list[int]:
    return [t.role_id for t in thresholds if t.role_id]


def user_label(
    user_id: int,
    member: SupportsMember | discord.abc.User | None = None,
    models: GuildModels | None = None,
) -> str:
    name: str | None = None
    if member and getattr(member, "display_name", None):
        name = getattr(member, "display_name")
    if not name and models:
        rec = models.User.get_or_none(models.User.discord_user_id == user_id)
        if rec and rec.last_username:
            name = rec.last_username
    return f"{name} ({user_id})" if name else str(user_id)


async def apply_roles(
    member: Any,
    thresholds: Iterable[Threshold],
    win_count: int,
) -> int | None:
    guild = member.guild
    target_role = await determine_target_role(guild, thresholds, win_count)
    threshold_ids = set(threshold_role_ids(thresholds))
    target_role_id = target_role.id if target_role else None

    to_remove = [
        role
        for role in member.roles
        if role.id in threshold_ids and role.id != target_role_id
    ]
    # Avoid redundant API calls if nothing changes
    if (
        target_role_id
        and target_role_id in [r.id for r in member.roles]
        and not to_remove
    ):
        return target_role_id

    if to_remove:
        try:
            await member.remove_roles(*to_remove, reason="Updating win tier role")
        except Exception as exc:
            LOGGER.warning(
                "Failed removing roles for %s: %s", user_label(member.id, member), exc
            )
    if target_role and target_role not in member.roles:
        try:
            await member.add_roles(target_role, reason="Updating win tier role")
            LOGGER.info(
                "Assigned role %s (%s) to user %s",
                target_role.name,
                target_role.id,
                user_label(member.id, member),
            )
        except Exception as exc:
            LOGGER.warning(
                "Failed adding role for %s: %s", user_label(member.id, member), exc
            )
    if not target_role and threshold_ids:
        # Remove stale roles if user falls below minimum
        try:
            await member.remove_roles(
                *[r for r in member.roles if r.id in threshold_ids],
                reason="Clearing tier roles",
            )
        except Exception as exc:
            LOGGER.warning(
                "Failed clearing roles for %s: %s", user_label(member.id, member), exc
            )
    return target_role_id


def admin_role_ids_from_permissions(guild: discord.Guild) -> List[int]:
    role_ids: List[int] = []
    for role in guild.roles:
        perms = role.permissions
        if perms.administrator or perms.manage_guild:
            role_ids.append(role.id)
    return role_ids


class CountingBot(commands.Bot):
    MAX_CONCURRENT_GUILD_SYNCS = 3

    def __init__(self, config: BotConfig):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.client = OpenFrontClient()
        self.guild_contexts: Dict[int, GuildContext] = {}
        self.guild_data_dir = Path("guild_data")
        self.guild_data_dir.mkdir(parents=True, exist_ok=True)
        init_central_db(config.central_database_path)
        self.sync_queue: asyncio.Queue[int] = asyncio.Queue()
        self.role_queue: asyncio.Queue[Any] = asyncio.Queue()
        self.sync_worker_tasks: list[asyncio.Task[None]] = []
        self.role_worker_task: asyncio.Task[None] | None = None
        self.scheduler_task: asyncio.Task[None] | None = None
        self.audit_cleanup_task: asyncio.Task[None] | None = None

    def guild_db_path(self, guild_id: int) -> str:
        return str(self.guild_data_dir / f"guild_{guild_id}.db")

    def get_guild_context(self, guild_id: int) -> Optional[GuildContext]:
        return self.guild_contexts.get(guild_id)

    async def close(self) -> None:
        if self.scheduler_task:
            self.scheduler_task.cancel()
        if self.audit_cleanup_task:
            self.audit_cleanup_task.cancel()
        if self.role_worker_task:
            self.role_worker_task.cancel()
        for task in self.sync_worker_tasks:
            task.cancel()
        for task in self.sync_worker_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self.role_worker_task:
            try:
                await self.role_worker_task
            except asyncio.CancelledError:
                pass
        if self.scheduler_task:
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        if self.audit_cleanup_task:
            try:
                await self.audit_cleanup_task
            except asyncio.CancelledError:
                pass
        for ctx in list(self.guild_contexts.values()):
            ctx.models.db.close()
        await super().close()
        await self.client.close()

    async def setup_hook(self) -> None:
        await self.tree.sync()
        await self._start_workers()

    async def _start_workers(self):
        if self.scheduler_task:
            return
        self.role_worker_task = self.loop.create_task(self._role_worker())
        self.sync_worker_tasks = [
            self.loop.create_task(self._sync_worker())
            for _ in range(self.MAX_CONCURRENT_GUILD_SYNCS)
        ]
        self.scheduler_task = self.loop.create_task(self._scheduler_loop())
        self.audit_cleanup_task = self.loop.create_task(self._audit_cleanup_loop())

    async def _sync_commands_for_guild(self, guild: discord.Guild):
        try:
            await self.tree.sync(guild=guild)
            LOGGER.info(
                "Synced application commands for guild %s (%s)", guild.name, guild.id
            )
        except Exception as exc:
            LOGGER.warning(
                "Failed to sync commands for guild %s (%s): %s",
                guild.name,
                guild.id,
                exc,
            )

    async def _sync_commands_for_all_guilds(self):
        for guild in self.guilds:
            await self._sync_commands_for_guild(guild)

    async def on_ready(self):
        LOGGER.info("Bot ready as %s", self.user)
        await self._bootstrap_guilds_on_ready()
        await self._sync_commands_for_all_guilds()

    async def on_guild_join(self, guild: discord.Guild):
        LOGGER.info("New guild joined: %s (%s)", guild.name, guild.id)
        await self._ensure_guild_registered(guild)
        await self._sync_commands_for_guild(guild)
        self.sync_queue.put_nowait(guild.id)

    async def on_guild_remove(self, guild: discord.Guild):
        LOGGER.info("Removed from guild %s (%s); deleting data", guild.name, guild.id)
        await self._delete_guild_data(guild.id)

    async def _bootstrap_guilds_on_ready(self):
        active_entries: Dict[int, Any] = {}
        for entry in list_active_guilds():
            guild_key = int(cast(Any, entry.guild_id))
            active_entries[guild_key] = entry
        for guild in self.guilds:
            try:
                entry = active_entries.get(guild.id)
                entry_path = str(entry.database_path) if entry else None
                await self._ensure_guild_registered(guild, db_path=entry_path)
            except Exception as exc:
                LOGGER.exception("Failed to initialize guild %s: %s", guild.id, exc)

        for guild_id, entry in active_entries.items():
            if not self.get_guild(guild_id):
                LOGGER.info(
                    "Stale guild %s present in central DB but bot not in guild; deleting",
                    guild_id,
                )
                await self._delete_guild_data(int(guild_id), str(entry.database_path))
        for guild in self.guilds:
            self.sync_queue.put_nowait(guild.id)

    def _load_admin_role_ids(self, models: GuildModels) -> Set[int]:
        return {row.role_id for row in models.GuildAdminRole.select()}

    def _member_is_admin(self, member: discord.Member, ctx: GuildContext) -> bool:
        perms = member.guild_permissions
        if perms.administrator or perms.manage_guild:
            return True
        return any(role.id in ctx.admin_role_ids for role in member.roles)

    async def _ensure_guild_registered(
        self, guild: discord.Guild, db_path: Optional[str] = None
    ) -> GuildContext:
        if guild.id in self.guild_contexts:
            return self.guild_contexts[guild.id]

        database_path = db_path or self.guild_db_path(guild.id)
        db_was_present = Path(database_path).exists()
        register_guild(guild.id, database_path)
        if not db_was_present:
            LOGGER.info("Creating database for guild %s at %s", guild.id, database_path)
        models = init_guild_db(database_path, guild.id)
        seed_admin_roles(models, admin_role_ids_from_permissions(guild))
        admin_role_ids = self._load_admin_role_ids(models)
        thresholds = list(models.RoleThreshold.select())
        for threshold in thresholds:
            if not guild.get_role(threshold.role_id):
                LOGGER.warning(
                    "Guild %s missing configured threshold role %s (wins=%s)",
                    guild.id,
                    threshold.role_id,
                    threshold.wins,
                )
        ctx = GuildContext(
            guild_id=guild.id,
            database_path=database_path,
            models=models,
            admin_role_ids=admin_role_ids,
            sync_lock=asyncio.Lock(),
        )
        self.guild_contexts[guild.id] = ctx
        return ctx

    async def _delete_guild_data(self, guild_id: int, db_path: Optional[str] = None):
        ctx = self.guild_contexts.pop(guild_id, None)
        if ctx:
            try:
                ctx.models.db.close()
            except Exception as exc:
                LOGGER.warning("Failed to close DB for guild %s: %s", guild_id, exc)
            if db_path is None:
                db_path = ctx.database_path
        elif db_path is None:
            entry = get_guild_entry(guild_id)
            if entry:
                db_path = str(entry.database_path)
        if db_path:
            try:
                Path(db_path).unlink(missing_ok=True)
            except Exception as exc:
                LOGGER.warning("Failed to delete guild DB %s: %s", db_path, exc)
        removed = remove_guild(guild_id)
        if not removed:
            LOGGER.info("Guild %s was not present in central DB", guild_id)

    async def _scheduler_loop(self):
        await self.wait_until_ready()
        base_interval = self.config.sync_interval_hours * 60 * 60
        while not self.is_closed():
            guilds = list(self.guilds)
            random.shuffle(guilds)
            for guild in guilds:
                await self.sync_queue.put(guild.id)
                jitter_seconds = max(1, int(base_interval * 0.01))
                await asyncio.sleep(random.uniform(0, jitter_seconds))
            jitter = min(base_interval * 0.1, 300)
            sleep_time = max(5, base_interval + random.uniform(-jitter, jitter))
            await asyncio.sleep(sleep_time)

    async def _sync_worker(self):
        await self.wait_until_ready()
        while not self.is_closed():
            guild_id = await self.sync_queue.get()
            ctx = self.get_guild_context(guild_id)
            if not ctx:
                continue
            try:
                await self.run_sync(ctx)
            except Exception as exc:
                LOGGER.exception("Sync worker failed for guild %s: %s", guild_id, exc)

    async def _role_worker(self):
        await self.wait_until_ready()
        retry_delay_default = 5
        while not self.is_closed():
            job = await self.role_queue.get()
            try:
                role_id = await apply_roles(
                    job["member"], job["thresholds"], job["wins"]
                )
                job["future"].set_result(role_id)
            except discord.HTTPException as exc:
                if exc.status == 429:
                    retry_after = getattr(exc, "retry_after", None)
                    delay = (retry_after or retry_delay_default) + 1
                    LOGGER.warning(
                        "Role update rate limited (429). Backing off for %ss", delay
                    )
                    await asyncio.sleep(delay)
                    try:
                        role_id = await apply_roles(
                            job["member"], job["thresholds"], job["wins"]
                        )
                        job["future"].set_result(role_id)
                    except Exception as exc_inner:
                        LOGGER.warning(
                            "Role update failed after backoff for user %s: %s",
                            user_label(job["member"].id, job["member"]),
                            exc_inner,
                        )
                        job["future"].set_exception(exc_inner)
                else:
                    job["future"].set_exception(exc)
            except Exception as exc:
                job["future"].set_exception(exc)

    async def _audit_cleanup_loop(self):
        await self.wait_until_ready()
        while not self.is_closed():
            cutoff = utcnow_naive() - timedelta(days=90)
            for ctx in list(self.guild_contexts.values()):
                try:
                    ctx.models.Audit.delete().where(
                        ctx.models.Audit.created_at < cutoff
                    ).execute()
                except Exception as exc:
                    LOGGER.warning(
                        "Audit cleanup failed for guild %s: %s", ctx.guild_id, exc
                    )
            await asyncio.sleep(24 * 60 * 60)

    async def run_sync(self, ctx: GuildContext, manual: bool = False) -> str:
        if ctx.sync_lock.locked():
            return "Sync already running"
        async with ctx.sync_lock:
            guild = self.get_guild(ctx.guild_id)
            if not guild:
                return "Guild unavailable"

            settings = ctx.models.Settings.get_by_id(1)
            now = utcnow_naive()
            if settings.backoff_until and settings.backoff_until > now:
                msg = f"In backoff until {settings.backoff_until.isoformat()}"
                LOGGER.warning(
                    "Skipping sync for guild %s: %s",
                    ctx.guild_id,
                    settings.backoff_until,
                )
                return msg
            thresholds = list(ctx.models.RoleThreshold.select())
            clan_tags = [ct.tag_text for ct in ctx.models.ClanTag.select()]
            users = list(ctx.models.User.select())
            for threshold in thresholds:
                if not guild.get_role(threshold.role_id):
                    LOGGER.warning(
                        "Guild %s missing configured threshold role %s (wins=%s)",
                        guild.id,
                        threshold.role_id,
                        threshold.wins,
                    )

            processed = 0
            failures = 0
            openfront_failure = False
            disabled_count = 0
            warnings: list[str] = []
            for user in users:
                if user.disabled and not manual:
                    disabled_count += 1
                    continue
                member = guild.get_member(user.discord_user_id)
                if not member:
                    try:
                        member = await guild.fetch_member(user.discord_user_id)
                    except Exception:
                        member = None
                if not member:
                    LOGGER.warning(
                        "User %s not in guild %s, skipping",
                        user_label(user.discord_user_id, models=ctx.models),
                        guild.id,
                    )
                    continue
                previous_role_id = user.last_role_id
                try:
                    win_count = await self._compute_wins(
                        user, settings.counting_mode, clan_tags
                    )
                    user.last_win_count = win_count
                    user.consecutive_404 = 0
                    user.disabled = 0
                    user.last_error_reason = None
                    target_role_id = await self.apply_roles_with_queue(
                        member, thresholds, win_count
                    )
                    user.last_role_id = target_role_id
                    user.last_username = getattr(member, "display_name", None)
                    user.save()
                    role_action = (
                        "unchanged" if target_role_id == previous_role_id else "updated"
                    )
                    LOGGER.debug(
                        "Sync user guild=%s user=%s player=%s mode=%s wins=%s role=%s prev_role=%s action=%s",
                        guild.id,
                        user_label(user.discord_user_id, member, ctx.models),
                        user.player_id,
                        settings.counting_mode,
                        win_count,
                        target_role_id,
                        previous_role_id,
                        role_action,
                    )
                    processed += 1
                except Exception as exc:
                    failures += 1
                    if isinstance(exc, OpenFrontError):
                        status = getattr(exc, "status", None)
                        if status == 404:
                            user.consecutive_404 += 1
                            user.last_error_reason = "404:player_not_found"
                            if user.consecutive_404 >= 3:
                                user.disabled = 1
                                disabled_count += 1
                                warning_msg = (
                                    f"User {user_label(user.discord_user_id, member, ctx.models)} "
                                    "disabled after 3x 404 player not found."
                                )
                                warnings.append(warning_msg)
                                LOGGER.warning(warning_msg)
                        else:
                            openfront_failure = True
                            user.last_error_reason = str(exc)
                        user.save()
                    LOGGER.exception(
                        "Failed syncing user %s in guild %s: %s",
                        user_label(user.discord_user_id, member, ctx.models),
                        guild.id,
                        exc,
                    )
            if openfront_failure:
                backoff_target = utcnow_naive() + timedelta(minutes=5)
                settings.backoff_until = backoff_target
                LOGGER.warning(
                    "Possible OpenFront rate limiting; backing off guild %s until %s",
                    guild.id,
                    backoff_target,
                )
            else:
                settings.backoff_until = None
            settings.last_sync_at = utcnow_naive()
            settings.save()
            summary = f"Processed {processed} users, failures: {failures}, disabled: {disabled_count}"
            guild_label = f"{guild.name} ({guild.id})" if guild else "unknown-guild"
            LOGGER.info("Guild %s sync: %s", guild_label, summary)
            return summary

    async def _compute_wins(self, user, mode: str, clan_tags: List[str]) -> int:
        player_id = user.player_id
        if mode == "total":
            return await compute_wins_total(self.client, player_id)
        if mode == "sessions_since_link":
            return await compute_wins_sessions_since_link(
                self.client, player_id, user.linked_at
            )
        if mode == "sessions_with_clan":
            return await compute_wins_sessions_with_clan(
                self.client, player_id, clan_tags
            )
        raise ValueError(f"Unknown counting mode {mode}")

    def trigger_sync(self, ctx: GuildContext):
        self.sync_queue.put_nowait(ctx.guild_id)

    async def apply_roles_with_queue(
        self, member: Any, thresholds: Iterable[Threshold], win_count: int
    ) -> int | None:
        future: asyncio.Future[int | None] = self.loop.create_future()
        job = {
            "member": member,
            "thresholds": thresholds,
            "wins": win_count,
            "future": future,
        }
        await self.role_queue.put(job)
        return await future


def _member_from_interaction(
    interaction: discord.Interaction,
) -> Optional[discord.Member]:
    member = interaction.user
    if not isinstance(member, discord.Member):
        return None
    return member


# Command registrations
async def setup_commands(bot: CountingBot):
    tree = bot.tree

    async def resolve_context(
        interaction: discord.Interaction,
    ) -> Optional[GuildContext]:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Commands must be used inside a guild.", ephemeral=True
            )
            return None
        ctx = bot.get_guild_context(guild.id)
        if not ctx:
            await interaction.response.send_message(
                "This guild is not registered. Re-invite the bot to initialize it.",
                ephemeral=True,
            )
            return None
        return ctx

    async def require_admin(
        interaction: discord.Interaction,
    ) -> Optional[tuple[GuildContext, discord.Member]]:
        ctx = await resolve_context(interaction)
        if not ctx:
            return None
        member = _member_from_interaction(interaction)
        if not member:
            await interaction.response.send_message(
                "Could not resolve guild member.", ephemeral=True
            )
            return None
        if not bot._member_is_admin(member, ctx):
            await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
            return None
        return ctx, member

    @bot.listen("on_interaction")
    async def log_app_command(interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.application_command:
            return
        cmd = interaction.command
        data = getattr(interaction, "namespace", None)
        try:
            payload = vars(data) if data else {}
        except Exception:
            payload = str(data)
        guild = interaction.guild
        guild_label = f"{guild.name} ({guild.id})" if guild else "unknown-guild"
        uid = int(getattr(interaction.user, "id", 0) or 0)
        LOGGER.info(
            "Slash command %s by %s in %s with options %s",
            cmd.qualified_name if cmd else "unknown",
            user_label(uid, interaction.user),
            guild_label,
            payload,
        )

    @tree.error
    async def on_app_command_error(
        interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.CheckFailure):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "You do not have permission to use this command.",
                    ephemeral=True,
                )
            return
        LOGGER.exception("App command error: %s", error)
        message = f"Command failed: {error}"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as exc:
            LOGGER.warning("Failed sending error response for command: %s", exc)

    @tree.command(
        name="link", description="Link your Discord user to an OpenFront player ID"
    )
    async def link(interaction: discord.Interaction, player_id: str):
        ctx = await resolve_context(interaction)
        if not ctx:
            return
        LOGGER.info(
            "Link request guild=%s user=%s player=%s",
            ctx.guild_id,
            user_label(interaction.user.id, interaction.user, ctx.models),
            player_id,
        )
        await interaction.response.defer(ephemeral=True, thinking=True)
        username = await last_session_username(bot.client, player_id)
        now = utcnow_naive()
        ctx.models.User.insert(
            discord_user_id=interaction.user.id,
            player_id=player_id,
            linked_at=now,
            last_win_count=0,
            last_username=getattr(interaction.user, "display_name", None),
        ).on_conflict_replace().execute()
        win_count = None
        try:
            settings = ctx.models.Settings.get_by_id(1)
            clan_tags = [ct.tag_text for ct in ctx.models.ClanTag.select()]
            record = ctx.models.User.get_by_id(interaction.user.id)
            win_count = await bot._compute_wins(
                record, settings.counting_mode, clan_tags
            )
            record.last_win_count = win_count
            guild = interaction.guild
            member: Optional[discord.Member] = None
            if isinstance(interaction.user, discord.Member):
                member = interaction.user
            elif guild:
                member = guild.get_member(record.discord_user_id)
            thresholds = list(ctx.models.RoleThreshold.select())
            if member:
                record.last_role_id = await bot.apply_roles_with_queue(
                    member, thresholds, win_count
                )
            record.save()
        except Exception as exc:
            LOGGER.warning(
                "Immediate sync after link failed for %s in guild %s: %s",
                interaction.user.id,
                ctx.guild_id,
                exc,
            )
        record_audit(ctx.models, interaction.user.id, "link", {"player_id": player_id})
        lines = [
            f"Linked to player `{player_id}`. Last session username: `{username or 'unknown'}`"
        ]
        if win_count is not None:
            lines.append(f"Current wins: `{win_count}` (roles refreshed)")
        else:
            lines.append("Could not fetch wins immediately; will update on next sync.")
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @tree.command(name="unlink", description="Remove your link")
    async def unlink(interaction: discord.Interaction):
        ctx = await resolve_context(interaction)
        if not ctx:
            return
        LOGGER.info(
            "Unlink request guild=%s user=%s",
            ctx.guild_id,
            user_label(interaction.user.id, interaction.user, ctx.models),
        )
        ctx.models.User.delete().where(
            ctx.models.User.discord_user_id == interaction.user.id
        ).execute()
        record_audit(ctx.models, interaction.user.id, "unlink", {})
        await interaction.response.send_message("Unlinked.", ephemeral=True)

    @tree.command(name="status", description="Show link status")
    @app_commands.describe(user="(Admin only) check another user")
    async def status(
        interaction: discord.Interaction, user: Optional[discord.Member] = None
    ):
        ctx = await resolve_context(interaction)
        if not ctx:
            return
        target = user or interaction.user
        if user:
            requester = _member_from_interaction(interaction)
            if not requester or not bot._member_is_admin(requester, ctx):
                await interaction.response.send_message("Admin only.", ephemeral=True)
                return
        record = ctx.models.User.get_or_none(
            ctx.models.User.discord_user_id == target.id
        )
        settings = ctx.models.Settings.get_by_id(1)
        if not record:
            await interaction.response.send_message("Not linked.", ephemeral=True)
            return
        if record.disabled:
            await interaction.response.send_message(
                "Sync disabled for this user (player not found after multiple attempts). Please re-link.",
                ephemeral=True,
            )
            return
        role_line = "Last role: none"
        if record.last_role_id:
            role = (
                interaction.guild.get_role(record.last_role_id)
                if interaction.guild
                else None
            )
            if role:
                role_line = f"Last role: <@&{role.id}>"
        counting_mode = settings.counting_mode
        clans_line = ""
        if counting_mode == "sessions_with_clan":
            clan_tags = [ct.tag_text for ct in ctx.models.ClanTag.select()]
            clans_line = f" (tags: {', '.join(clan_tags) if clan_tags else 'none'})"
        linked_str = (
            record.linked_at.strftime("%Y-%m-%d %H:%M UTC")
            if record.linked_at
            else "unknown"
        )
        last_sync_str = (
            settings.last_sync_at.strftime("%Y-%m-%d %H:%M UTC")
            if settings.last_sync_at
            else "never"
        )
        mode_descriptions = {
            "total": "Total wins",
            "sessions_since_link": "Wins since you linked",
            "sessions_with_clan": "Wins in sessions with clan tags",
        }
        mode_label = mode_descriptions.get(counting_mode, counting_mode)
        msg = (
            f"Player ID: `{record.player_id}`\n"
            f"Linked: {linked_str}\n"
            f"Last wins: {record.last_win_count}\n"
            f"Counting mode: {mode_label}{clans_line}\n"
            f"{role_line}\n"
            f"Last sync: {last_sync_str}"
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @tree.command(
        name="sync",
        description="Trigger immediate sync (optionally for a single user)",
    )
    @app_commands.describe(user="Optional user; if omitted, sync all linked users")
    async def sync(
        interaction: discord.Interaction, user: Optional[discord.Member] = None
    ):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        await interaction.response.defer(ephemeral=True, thinking=True)
        if user:
            record = ctx.models.User.get_or_none(
                ctx.models.User.discord_user_id == user.id
            )
            if not record:
                await interaction.followup.send("User not linked.", ephemeral=True)
                return
            if record.disabled:
                await interaction.followup.send(
                    "Sync disabled for this user (player not found). Ask them to re-link.",
                    ephemeral=True,
                )
                return
            settings = ctx.models.Settings.get_by_id(1)
            clan_tags = [ct.tag_text for ct in ctx.models.ClanTag.select()]
            win_count = await bot._compute_wins(
                record, settings.counting_mode, clan_tags
            )
            record.last_win_count = win_count
            thresholds = list(ctx.models.RoleThreshold.select())
            record.last_role_id = await bot.apply_roles_with_queue(
                user, thresholds, win_count
            )
            record.last_username = getattr(user, "display_name", None)
            record.save()
            record_audit(
                ctx.models, interaction.user.id, "sync_user", {"user": user.id}
            )
            await interaction.followup.send(
                f"Synced {user.display_name}: {win_count} wins", ephemeral=True
            )
            return
        summary = await bot.run_sync(ctx, manual=True)
        record_audit(ctx.models, interaction.user.id, "sync", {"scope": "all"})
        await interaction.followup.send(summary, ephemeral=True)

    @tree.command(name="set_mode", description="Set counting mode")
    @app_commands.describe(mode="total | sessions_since_link | sessions_with_clan")
    async def set_mode(interaction: discord.Interaction, mode: str):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        if mode not in COUNTING_MODES:
            await interaction.response.send_message("Invalid mode", ephemeral=True)
            return
        settings = ctx.models.Settings.get_by_id(1)
        settings.counting_mode = mode
        settings.save()
        LOGGER.info(
            "Counting mode updated guild=%s actor=%s mode=%s",
            ctx.guild_id,
            user_label(interaction.user.id, interaction.user, ctx.models),
            mode,
        )
        record_audit(ctx.models, interaction.user.id, "set_mode", {"mode": mode})
        await interaction.response.send_message(
            f"Counting mode set to {mode}", ephemeral=True
        )

    @tree.command(name="get_mode", description="Show current counting mode")
    async def get_mode(interaction: discord.Interaction):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        settings = ctx.models.Settings.get_by_id(1)
        await interaction.response.send_message(
            f"Current counting mode: {settings.counting_mode}", ephemeral=True
        )

    @tree.command(name="roles_add", description="Add or update a threshold role")
    async def roles_add(
        interaction: discord.Interaction,
        wins: int,
        role: discord.Role,
    ):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        try:
            upsert_role_threshold(ctx.models, wins, role.id)
        except RoleThresholdExistsError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        LOGGER.info(
            "Role threshold saved guild=%s actor=%s wins=%s role_id=%s",
            ctx.guild_id,
            user_label(interaction.user.id, interaction.user, ctx.models),
            wins,
            role.id,
        )
        record_audit(
            ctx.models,
            interaction.user.id,
            "roles_add",
            {"wins": wins, "role_id": role.id},
        )
        await interaction.response.send_message("Role threshold saved.", ephemeral=True)

    @tree.command(name="roles_remove", description="Remove a threshold role")
    async def roles_remove(
        interaction: discord.Interaction,
        wins: Optional[int] = None,
        role: Optional[discord.Role] = None,
    ):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        if wins is None and role is None:
            await interaction.response.send_message(
                "Provide wins or role.", ephemeral=True
            )
            return
        actor_label = user_label(interaction.user.id, interaction.user, ctx.models)
        query = ctx.models.RoleThreshold.delete()
        if wins is not None:
            query = query.where(ctx.models.RoleThreshold.wins == wins)
        if role is not None:
            query = query.where(ctx.models.RoleThreshold.role_id == role.id)
        deleted = query.execute()
        LOGGER.info(
            "Role threshold removal guild=%s actor=%s wins=%s role_id=%s deleted=%s",
            ctx.guild_id,
            actor_label,
            wins,
            role.id if role else None,
            deleted,
        )
        record_audit(
            ctx.models,
            interaction.user.id,
            "roles_remove",
            {"wins": wins, "role": role.id if role else None},
        )
        await interaction.response.send_message(
            f"Removed {deleted} entries.", ephemeral=True
        )

    @tree.command(name="roles", description="List role thresholds")
    async def roles(interaction: discord.Interaction):
        ctx = await resolve_context(interaction)
        if not ctx:
            return
        rows = ctx.models.RoleThreshold.select().order_by(ctx.models.RoleThreshold.wins)
        lines = []
        for row in rows:
            mention = f"<@&{row.role_id}>"
            lines.append(f"{row.wins} wins: {mention}")
        await interaction.response.send_message(
            "\n".join(lines) or "No roles configured", ephemeral=True
        )

    @tree.command(name="clan_tag_add", description="Add a clan tag")
    async def clan_tag_add(interaction: discord.Interaction, tag: str):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        actor_label = user_label(interaction.user.id, interaction.user, ctx.models)
        tag_norm = tag.upper()
        ctx.models.ClanTag.insert(tag_text=tag_norm).on_conflict_ignore().execute()
        LOGGER.info(
            "Clan tag add guild=%s actor=%s tag=%s",
            ctx.guild_id,
            actor_label,
            tag_norm,
        )
        record_audit(ctx.models, interaction.user.id, "clan_tag_add", {"tag": tag_norm})
        await interaction.response.send_message(
            f"Clan tag '{tag_norm}' added", ephemeral=True
        )

    @tree.command(name="clan_tag_remove", description="Remove a clan tag")
    async def clan_tag_remove(interaction: discord.Interaction, tag: str):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        actor_label = user_label(interaction.user.id, interaction.user, ctx.models)
        tag_norm = tag.upper()
        deleted = (
            ctx.models.ClanTag.delete().where(ctx.models.ClanTag.tag_text == tag_norm)
        ).execute()
        LOGGER.info(
            "Clan tag remove guild=%s actor=%s tag=%s deleted=%s",
            ctx.guild_id,
            actor_label,
            tag_norm,
            deleted,
        )
        record_audit(
            ctx.models, interaction.user.id, "clan_tag_remove", {"tag": tag_norm}
        )
        await interaction.response.send_message(
            f"Removed {deleted} entries", ephemeral=True
        )

    @tree.command(name="clans_list", description="List clan tags")
    async def clans_list(interaction: discord.Interaction):
        ctx = await resolve_context(interaction)
        if not ctx:
            return
        tags = [ct.tag_text for ct in ctx.models.ClanTag.select()]
        await interaction.response.send_message(
            ", ".join(tags) or "No clans configured", ephemeral=True
        )

    @tree.command(name="link_override", description="Admin override link")
    async def link_override(
        interaction: discord.Interaction, user: discord.Member, player_id: str
    ):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        now = utcnow_naive()
        ctx.models.User.insert(
            discord_user_id=user.id,
            player_id=player_id,
            linked_at=now,
            last_win_count=0,
            last_username=getattr(user, "display_name", None),
        ).on_conflict_replace().execute()
        LOGGER.info(
            "Link override guild=%s actor=%s target_user=%s player=%s",
            ctx.guild_id,
            interaction.user.id,
            user.id,
            player_id,
        )
        record_audit(
            ctx.models,
            interaction.user.id,
            "link_override",
            {"user": user.id, "player_id": player_id},
        )
        await interaction.response.send_message(
            f"Linked {user.display_name} to {player_id}", ephemeral=True
        )

    @tree.command(name="audit", description="Show recent audit events")
    async def audit(interaction: discord.Interaction, page: int = 1):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        page = max(1, page)
        limit = 20
        query = (
            ctx.models.Audit.select()
            .order_by(ctx.models.Audit.id.desc())
            .paginate(page, limit)
        )
        guild = interaction.guild
        member_lookup = guild.get_member if guild else None

        lines = [
            f"{row.id}: actor={user_label(row.actor_discord_id, member_lookup(row.actor_discord_id) if member_lookup else None, ctx.models)} action={row.action} payload={row.payload}"
            for row in query
        ]
        await interaction.response.send_message(
            "\n".join(lines) or "No audit entries", ephemeral=True
        )

    @tree.command(name="admin_role_add", description="Add an admin role for this guild")
    async def admin_role_add(interaction: discord.Interaction, role: discord.Role):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        actor_label = user_label(interaction.user.id, interaction.user, ctx.models)
        ctx.models.GuildAdminRole.insert(role_id=role.id).on_conflict_ignore().execute()
        ctx.admin_role_ids = bot._load_admin_role_ids(ctx.models)
        LOGGER.info(
            "Admin role add guild=%s actor=%s role_id=%s",
            ctx.guild_id,
            actor_label,
            role.id,
        )
        record_audit(
            ctx.models, interaction.user.id, "admin_role_add", {"role_id": role.id}
        )
        await interaction.response.send_message(
            f"Added admin role <@&{role.id}>", ephemeral=True
        )

    @tree.command(
        name="admin_role_remove", description="Remove an admin role for this guild"
    )
    async def admin_role_remove(interaction: discord.Interaction, role: discord.Role):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        actor_label = user_label(interaction.user.id, interaction.user, ctx.models)
        deleted = (
            ctx.models.GuildAdminRole.delete().where(
                ctx.models.GuildAdminRole.role_id == role.id
            )
        ).execute()
        ctx.admin_role_ids = bot._load_admin_role_ids(ctx.models)
        LOGGER.info(
            "Admin role remove guild=%s actor=%s role_id=%s deleted=%s",
            ctx.guild_id,
            actor_label,
            role.id,
            deleted,
        )
        record_audit(
            ctx.models, interaction.user.id, "admin_role_remove", {"role_id": role.id}
        )
        await interaction.response.send_message(
            f"Removed {deleted} entries for role <@&{role.id}>",
            ephemeral=True,
        )

    @tree.command(name="admin_roles", description="List admin roles for this guild")
    async def admin_roles(interaction: discord.Interaction):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        roles = list(ctx.models.GuildAdminRole.select())
        lines = []
        for row in roles:
            role_obj = (
                interaction.guild.get_role(row.role_id) if interaction.guild else None
            )
            label = role_obj.name if role_obj else "unknown role"
            lines.append(f"<@&{row.role_id}>")
        await interaction.response.send_message(
            "\n".join(lines) or "No admin roles configured.", ephemeral=True
        )

    @tree.command(
        name="guild_remove",
        description="Remove this guild from the bot and delete its data",
    )
    @app_commands.describe(confirm="Set to true to confirm deletion")
    async def guild_remove(interaction: discord.Interaction, confirm: bool = False):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, member = admin_ctx
        if not confirm:
            await interaction.response.send_message(
                "This will delete all data for this guild. Re-run with confirm=true to proceed.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "Removing guild data...", ephemeral=True
        )
        await bot._delete_guild_data(ctx.guild_id, ctx.database_path)
        LOGGER.info(
            "Guild %s data removed by %s (%s)",
            ctx.guild_id,
            member,
            member.id,
        )
        if interaction.guild:
            try:
                await interaction.guild.leave()
            except Exception as exc:
                LOGGER.warning(
                    "Failed to leave guild %s after removal: %s", ctx.guild_id, exc
                )


async def main():
    bot_config = load_config()
    logging.getLogger().setLevel(bot_config.log_level)
    LOGGER.setLevel(bot_config.log_level)
    bot = CountingBot(bot_config)
    await setup_commands(bot)
    await bot.start(bot_config.token)


if __name__ == "__main__":
    asyncio.run(main())
