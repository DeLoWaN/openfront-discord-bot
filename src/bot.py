import asyncio
import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from .config import BotConfig, load_config
from .models import (
    DEFAULT_COUNTING_MODE,
    DEFAULT_SYNC_INTERVAL,
    Audit,
    ClanTag,
    RoleThreshold,
    Settings,
    User,
    database,
    init_db,
    record_audit,
    upsert_role_threshold,
)
from .openfront import OpenFrontClient
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


def is_admin(interaction: discord.Interaction, config: BotConfig) -> bool:
    member = interaction.user
    if not isinstance(member, discord.Member):
        return False
    return any(role.id in config.admin_role_ids for role in member.roles)


def get_guild(bot: commands.Bot) -> Optional[discord.Guild]:
    if bot.guilds:
        return bot.guilds[0]
    return None


async def determine_target_role(
    guild: discord.Guild,
    thresholds: List[RoleThreshold],
    win_count: int,
) -> Optional[discord.Role]:
    target_id = None
    for threshold in sorted(thresholds, key=lambda t: t.wins):
        if threshold.wins <= win_count and threshold.role_id:
            target_id = threshold.role_id
    if target_id:
        role = guild.get_role(target_id)
        return role
    return None


def threshold_role_ids(thresholds: Iterable[RoleThreshold]) -> List[int]:
    return [t.role_id for t in thresholds if t.role_id]


async def apply_roles(
    member: discord.Member,
    thresholds: List[RoleThreshold],
    win_count: int,
) -> Optional[int]:
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
            LOGGER.warning("Failed removing roles for %s: %s", member.id, exc)
    if target_role and target_role not in member.roles:
        try:
            await member.add_roles(target_role, reason="Updating win tier role")
            LOGGER.info(
                "Assigned role %s (%s) to user %s",
                target_role.name,
                target_role.id,
                member.id,
            )
        except Exception as exc:
            LOGGER.warning("Failed adding role for %s: %s", member.id, exc)
    if not target_role and threshold_ids:
        # Remove stale roles if user falls below minimum
        try:
            await member.remove_roles(
                *[r for r in member.roles if r.id in threshold_ids],
                reason="Clearing tier roles",
            )
        except Exception as exc:
            LOGGER.warning("Failed clearing roles for %s: %s", member.id, exc)
    return target_role_id


class CountingBot(commands.Bot):
    def __init__(self, config: BotConfig):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.client = OpenFrontClient()
        self._sync_lock = asyncio.Lock()
        self._sync_event = asyncio.Event()

    async def on_ready(self):
        guild = get_guild(self)
        if not guild:
            LOGGER.warning("Bot is not in a guild yet.")
            return
        LOGGER.info("Bot ready in guild %s (%s)", guild.name, guild.id)
        try:
            settings = Settings.get_by_id(1)
            LOGGER.info("Counting mode: %s", settings.counting_mode)
        except Exception as exc:
            LOGGER.warning("Could not load counting mode: %s", exc)
        missing = []
        for rt in RoleThreshold.select():
            if rt.role_id and not guild.get_role(rt.role_id):
                missing.append(rt.role_id)
        if missing:
            LOGGER.warning("Role IDs not found in guild: %s", missing)

    async def setup_hook(self) -> None:
        await self.tree.sync()
        self.loop.create_task(self._sync_loop())

    async def close(self) -> None:
        await super().close()
        await self.client.close()

    async def _sync_loop(self):
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                await self.run_sync()
            except Exception as exc:
                LOGGER.exception("Background sync failed: %s", exc)
            settings = Settings.get_by_id(1)
            sleep_task = asyncio.create_task(
                asyncio.sleep(settings.sync_interval_minutes * 60)
            )
            event_task = asyncio.create_task(self._sync_event.wait())
            done, pending = await asyncio.wait(
                {sleep_task, event_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            self._sync_event.clear()

    async def run_sync(self, manual: bool = False) -> str:
        if self._sync_lock.locked():
            return "Sync already running"
        async with self._sync_lock:
            guild = get_guild(self)
            if not guild:
                return "No guild available"

            settings = Settings.get_by_id(1)
            thresholds = list(RoleThreshold.select())
            clan_tags = [ct.tag_text for ct in ClanTag.select()]
            users = list(User.select())

            processed = 0
            failures = 0
            for user in users:
                member = guild.get_member(user.discord_user_id)
                if not member:
                    LOGGER.info("User %s not in guild, skipping", user.discord_user_id)
                    continue
                try:
                    win_count = await self._compute_wins(
                        user, settings.counting_mode, clan_tags
                    )
                    user.last_win_count = win_count
                    target_role_id = await apply_roles(member, thresholds, win_count)
                    user.last_role_id = target_role_id
                    user.save()
                    processed += 1
                except Exception as exc:
                    failures += 1
                    LOGGER.exception(
                        "Failed syncing user %s: %s", user.discord_user_id, exc
                    )
            settings.last_sync_at = datetime.utcnow()
            settings.save()
            summary = f"Processed {processed} users, failures: {failures}"
            LOGGER.info(summary)
            return summary

    async def _compute_wins(self, user: User, mode: str, clan_tags: List[str]) -> int:
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


bot_config: Optional[BotConfig] = None
bot_instance: Optional[CountingBot] = None


async def admin_check(interaction: discord.Interaction) -> bool:
    assert bot_config is not None
    if not is_admin(interaction, bot_config):
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )
        return False
    return True


def admin_required():
    async def predicate(interaction: discord.Interaction) -> bool:
        return await admin_check(interaction)

    return app_commands.check(predicate)


# Command registrations
async def setup_commands(bot: CountingBot):
    tree = bot.tree

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
        LOGGER.info(
            "Slash command %s by %s (%s) with options %s",
            cmd.qualified_name if cmd else "unknown",
            interaction.user,
            getattr(interaction.user, "id", "unknown"),
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

    @tree.command(
        name="link", description="Link your Discord user to an OpenFront player ID"
    )
    async def link(interaction: discord.Interaction, player_id: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        username = await last_session_username(bot.client, player_id)
        now = datetime.utcnow()
        User.insert(
            discord_user_id=interaction.user.id,
            player_id=player_id,
            linked_at=now,
            last_win_count=0,
        ).on_conflict_replace().execute()
        win_count = None
        try:
            settings = Settings.get_by_id(1)
            clan_tags = [ct.tag_text for ct in ClanTag.select()]
            record = User.get_by_id(interaction.user.id)
            win_count = await bot._compute_wins(
                record, settings.counting_mode, clan_tags
            )
            record.last_win_count = win_count
            guild = get_guild(bot)
            member: Optional[discord.Member] = None
            if isinstance(interaction.user, discord.Member):
                member = interaction.user
            elif guild:
                member = guild.get_member(record.discord_user_id)
            thresholds = list(RoleThreshold.select())
            if member:
                record.last_role_id = await apply_roles(member, thresholds, win_count)
            record.save()
        except Exception as exc:
            LOGGER.warning(
                "Immediate sync after link failed for %s: %s", interaction.user.id, exc
            )
        record_audit(interaction.user.id, "link", {"player_id": player_id})
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
        User.delete().where(User.discord_user_id == interaction.user.id).execute()
        record_audit(interaction.user.id, "unlink", {})
        await interaction.response.send_message("Unlinked.", ephemeral=True)

    @tree.command(name="status", description="Show link status")
    @app_commands.describe(user="(Admin only) check another user")
    async def status(
        interaction: discord.Interaction, user: Optional[discord.Member] = None
    ):
        target = user or interaction.user
        if user and not is_admin(interaction, bot_config):
            await interaction.response.send_message("Admin only.", ephemeral=True)
            return
        record = User.get_or_none(User.discord_user_id == target.id)
        settings = Settings.get_by_id(1)
        if not record:
            await interaction.response.send_message("Not linked.", ephemeral=True)
            return
        msg = (
            f"Player ID: `{record.player_id}`\n"
            f"Linked at: {record.linked_at.isoformat()}\n"
            f"Last wins: {record.last_win_count}\n"
            f"Last sync: {settings.last_sync_at.isoformat() if settings.last_sync_at else 'never'}"
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @tree.command(name="recompute", description="Force recompute for a user or all")
    @admin_required()
    @app_commands.describe(user="Optional user; if omitted, recompute all")
    async def recompute(
        interaction: discord.Interaction, user: Optional[discord.Member] = None
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if user:
            record = User.get_or_none(User.discord_user_id == user.id)
            if not record:
                await interaction.followup.send("User not linked.", ephemeral=True)
                return
            settings = Settings.get_by_id(1)
            clan_tags = [ct.tag_text for ct in ClanTag.select()]
            win_count = await bot._compute_wins(
                record, settings.counting_mode, clan_tags
            )
            record.last_win_count = win_count
            member = user
            thresholds = list(RoleThreshold.select())
            record.last_role_id = await apply_roles(member, thresholds, win_count)
            record.save()
            record_audit(interaction.user.id, "recompute_user", {"user": user.id})
            await interaction.followup.send(
                f"Recomputed {user.display_name}: {win_count} wins", ephemeral=True
            )
        else:
            summary = await bot.run_sync(manual=True)
            record_audit(interaction.user.id, "recompute_all", {})
            await interaction.followup.send(summary, ephemeral=True)

    @tree.command(name="sync", description="Trigger immediate sync")
    @admin_required()
    async def sync(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        summary = await bot.run_sync(manual=True)
        record_audit(interaction.user.id, "sync", {})
        await interaction.followup.send(summary, ephemeral=True)

    @tree.command(name="set_mode", description="Set counting mode")
    @admin_required()
    @app_commands.describe(mode="total | sessions_since_link | sessions_with_clan")
    async def set_mode(interaction: discord.Interaction, mode: str):
        if mode not in COUNTING_MODES:
            await interaction.response.send_message("Invalid mode", ephemeral=True)
            return
        settings = Settings.get_by_id(1)
        settings.counting_mode = mode
        settings.save()
        record_audit(interaction.user.id, "set_mode", {"mode": mode})
        await interaction.response.send_message(
            f"Counting mode set to {mode}", ephemeral=True
        )

    @tree.command(name="set_interval", description="Set sync interval (minutes)")
    @admin_required()
    async def set_interval(interaction: discord.Interaction, minutes: int):
        minutes = max(5, min(24 * 60, minutes))
        settings = Settings.get_by_id(1)
        settings.sync_interval_minutes = minutes
        settings.save()
        record_audit(interaction.user.id, "set_interval", {"minutes": minutes})
        await interaction.response.send_message(
            f"Sync interval set to {minutes} minutes", ephemeral=True
        )

    @tree.command(name="add_role", description="Add or update a threshold role")
    @admin_required()
    async def add_role(
        interaction: discord.Interaction,
        wins: int,
        role: discord.Role,
        role_name: str,
    ):
        upsert_role_threshold(wins, role.id, role_name)
        record_audit(
            interaction.user.id, "add_role", {"wins": wins, "role_id": role.id}
        )
        await interaction.response.send_message("Role threshold saved.", ephemeral=True)

    @tree.command(name="remove_role", description="Remove a threshold role")
    @admin_required()
    async def remove_role(
        interaction: discord.Interaction,
        wins: Optional[int] = None,
        role: Optional[discord.Role] = None,
    ):
        if wins is None and role is None:
            await interaction.response.send_message(
                "Provide wins or role.", ephemeral=True
            )
            return
        query = RoleThreshold.delete()
        if wins is not None:
            query = query.where(RoleThreshold.wins == wins)
        if role is not None:
            query = query.where(RoleThreshold.role_id == role.id)
        deleted = query.execute()
        record_audit(
            interaction.user.id,
            "remove_role",
            {"wins": wins, "role": role.id if role else None},
        )
        await interaction.response.send_message(
            f"Removed {deleted} entries.", ephemeral=True
        )

    @tree.command(name="list_roles", description="List role thresholds")
    async def list_roles(interaction: discord.Interaction):
        rows = RoleThreshold.select().order_by(RoleThreshold.wins)
        lines = [
            f"{row.wins}: {row.role_name} (role id: {row.role_id})" for row in rows
        ]
        await interaction.response.send_message(
            "\n".join(lines) or "No roles configured", ephemeral=True
        )

    @tree.command(name="clan_tag_add", description="Add a clan tag")
    @admin_required()
    async def clan_tag_add(interaction: discord.Interaction, tag: str):
        tag_norm = tag.upper()
        ClanTag.insert(tag_text=tag_norm).on_conflict_ignore().execute()
        record_audit(interaction.user.id, "clan_tag_add", {"tag": tag_norm})
        await interaction.response.send_message(
            f"Clan tag '{tag_norm}' added", ephemeral=True
        )

    @tree.command(name="clan_tag_remove", description="Remove a clan tag")
    @admin_required()
    async def clan_tag_remove(interaction: discord.Interaction, tag: str):
        tag_norm = tag.lower()
        deleted = ClanTag.delete().where(ClanTag.tag_text == tag_norm).execute()
        record_audit(interaction.user.id, "clan_tag_remove", {"tag": tag_norm})
        await interaction.response.send_message(
            f"Removed {deleted} entries", ephemeral=True
        )

    @tree.command(name="list_clans", description="List clan tags")
    async def list_clans(interaction: discord.Interaction):
        tags = [ct.tag_text for ct in ClanTag.select()]
        await interaction.response.send_message(
            ", ".join(tags) or "No clans configured", ephemeral=True
        )

    @tree.command(name="link_override", description="Admin override link")
    @admin_required()
    async def link_override(
        interaction: discord.Interaction, user: discord.Member, player_id: str
    ):
        now = datetime.utcnow()
        User.insert(
            discord_user_id=user.id,
            player_id=player_id,
            linked_at=now,
            last_win_count=0,
        ).on_conflict_replace().execute()
        record_audit(
            interaction.user.id,
            "link_override",
            {"user": user.id, "player_id": player_id},
        )
        await interaction.response.send_message(
            f"Linked {user.display_name} to {player_id}", ephemeral=True
        )

    @tree.command(name="audit", description="Show recent audit events")
    @admin_required()
    async def audit(interaction: discord.Interaction, page: int = 1):
        page = max(1, page)
        limit = 20
        query = Audit.select().order_by(Audit.id.desc()).paginate(page, limit)
        lines = [
            f"{row.id}: actor={row.actor_discord_id} action={row.action} payload={row.payload}"
            for row in query
        ]
        await interaction.response.send_message(
            "\n".join(lines) or "No audit entries", ephemeral=True
        )


async def main():
    global bot_config, bot_instance
    bot_config = load_config()
    # Apply log level from config
    logging.getLogger().setLevel(bot_config.log_level)
    LOGGER.setLevel(bot_config.log_level)
    init_db(bot_config.database_path)
    bot_instance = CountingBot(bot_config)
    await setup_commands(bot_instance)
    await bot_instance.start(bot_config.token)


if __name__ == "__main__":
    asyncio.run(main())
