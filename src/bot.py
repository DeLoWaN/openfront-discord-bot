from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    list_due_tracked_games,
    note_tracked_game_unexpected_failure,
    register_guild,
    remove_guild,
    remove_tracked_game,
    reschedule_tracked_game,
    reset_tracked_game_unexpected_failures,
    track_game,
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
    compute_wins_sessions_since_link_from_sessions,
    compute_wins_sessions_with_clan_from_sessions,
    compute_wins_total,
    last_session_username,
    last_session_username_from_sessions,
)

# Default to INFO until the configured level is applied at startup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
LOGGER = logging.getLogger(__name__)

COUNTING_MODES = ["total", "sessions_since_link", "sessions_with_clan"]
RESULTS_GAME_RETRY_SECONDS = 60
RESULTS_TRACKED_BATCH_LIMIT = 25
RESULTS_GAME_UNEXPECTED_FAILURE_LIMIT = 3
RESULTS_GAME_EXPECTED_STATUSES = {404, 429, 500, 502, 503, 504}
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


def build_openfront_username_index(models: GuildModels) -> Dict[str, List[int]]:
    index: Dict[str, List[int]] = {}
    for user in models.User.select():
        username = getattr(user, "last_openfront_username", None)
        if not username:
            continue
        index.setdefault(username, []).append(user.discord_user_id)
    return index


def extract_game_id(entry: Dict[str, Any]) -> Optional[str]:
    for key in ("game", "gameId", "gameID", "id"):
        value = entry.get(key)
        if value:
            return str(value)
    return None


def extract_lobby_game_id(entry: Dict[str, Any]) -> Optional[str]:
    for key in ("gameID", "gameId", "game", "id"):
        value = entry.get(key)
        if value:
            return str(value)
    return None


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def extract_winner_client_ids(
    info: Dict[str, Any], players: Iterable[Dict[str, Any]]
) -> Set[str]:
    winners_raw = info.get("winner")
    if not isinstance(winners_raw, list):
        return set()
    player_ids = {
        str(player.get("clientID")) for player in players if player.get("clientID")
    }
    return {str(item) for item in winners_raw if str(item) in player_ids}


def resolve_winning_clan_tags(
    winner_client_ids: Set[str], players: Iterable[Dict[str, Any]]
) -> Set[str]:
    tags = set()
    for player in players:
        client_id = player.get("clientID")
        if not client_id or str(client_id) not in winner_client_ids:
            continue
        tag = player.get("clanTag")
        if tag:
            tags.add(str(tag).upper())
    return tags


def parse_players_per_team(player_teams: Any) -> Optional[float]:
    if player_teams is None:
        return None
    if isinstance(player_teams, (int, float)):
        return None
    label = str(player_teams).strip().lower()
    if label == "":
        return None
    named_sizes = {"duos": 2, "trios": 3, "quads": 4}
    if label in named_sizes:
        return float(named_sizes[label])
    return None


def _compute_players_per_team(
    num_teams: Any, player_teams: Any, total_players: Any
) -> Optional[float]:
    if player_teams is None:
        return None
    if isinstance(player_teams, (int, float)):
        if total_players and int(player_teams) != 0:
            return float(total_players) / float(player_teams)
        return None
    label = str(player_teams).strip().lower()
    named_sizes = {"duos": 2, "trios": 3, "quads": 4}
    if label in named_sizes:
        return float(named_sizes[label])
    if label.isdigit():
        if total_players and int(label) != 0:
            return float(total_players) / float(label)
        return None
    return None


def format_team_mode(
    num_teams: Any, player_teams: Any, total_players: Any = None
) -> str:
    if num_teams is None or player_teams is None:
        return "Unknown mode"
    players_per_team = _compute_players_per_team(num_teams, player_teams, total_players)
    if players_per_team is None:
        return "Unknown mode"
    teams_label = str(num_teams)
    display = (
        str(int(players_per_team))
        if float(players_per_team).is_integer()
        else str(players_per_team)
    )
    label = str(player_teams).strip()
    base = f"{teams_label} teams of {display} players"
    if label and not label.isdigit():
        return f"{base} ({label})"
    return base


def resolve_game_start(
    client: OpenFrontClient,
    session: Optional[Dict[str, Any]],
    game_info: Dict[str, Any],
) -> Optional[datetime]:
    start_time = client.session_start_time(session) if session else None
    if start_time:
        return start_time
    info_start = game_info.get("start")
    if isinstance(info_start, (int, float)):
        return datetime.fromtimestamp(info_start / 1000, tz=timezone.utc).replace(
            tzinfo=None
        )
    return None


def resolve_game_end(game_info: Dict[str, Any]) -> Optional[datetime]:
    info_end = game_info.get("end")
    if isinstance(info_end, (int, float)):
        return datetime.fromtimestamp(info_end / 1000, tz=timezone.utc).replace(
            tzinfo=None
        )
    return None


def format_duration_seconds(duration_seconds: Optional[int]) -> str:
    if duration_seconds is None:
        return "unknown duration"
    total = max(int(duration_seconds), 0)
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


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
    MAX_CONCURRENT_RESULTS_POLLS = 2

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
        self.results_worker_tasks: list[asyncio.Task[None]] = []
        self.results_lobby_task: asyncio.Task[None] | None = None
        self.audit_cleanup_task: asyncio.Task[None] | None = None
        self.results_processing_lock = asyncio.Lock()
        self.results_wake_event = asyncio.Event()

    def guild_db_path(self, guild_id: int) -> str:
        return str(self.guild_data_dir / f"guild_{guild_id}.db")

    def get_guild_context(self, guild_id: int) -> Optional[GuildContext]:
        return self.guild_contexts.get(guild_id)

    async def close(self) -> None:
        if self.scheduler_task:
            self.scheduler_task.cancel()
        if self.results_lobby_task:
            self.results_lobby_task.cancel()
        if self.audit_cleanup_task:
            self.audit_cleanup_task.cancel()
        if self.role_worker_task:
            self.role_worker_task.cancel()
        for task in self.sync_worker_tasks:
            task.cancel()
        for task in self.results_worker_tasks:
            task.cancel()
        for task in self.sync_worker_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        for task in self.results_worker_tasks:
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
        if self.results_lobby_task:
            try:
                await self.results_lobby_task
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
        self.results_worker_tasks = [
            self.loop.create_task(self._results_worker())
            for _ in range(self.MAX_CONCURRENT_RESULTS_POLLS)
        ]
        self.scheduler_task = self.loop.create_task(self._scheduler_loop())
        self.results_lobby_task = self.loop.create_task(self._results_lobby_loop())
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
        first_cycle = True
        while not self.is_closed():
            if not first_cycle:
                guilds = list(self.guilds)
                random.shuffle(guilds)
                for guild in guilds:
                    await self.sync_queue.put(guild.id)
                    jitter_seconds = max(1, int(base_interval * 0.01))
                    await asyncio.sleep(random.uniform(0, jitter_seconds))
            first_cycle = False
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

    async def _results_lobby_loop(self):
        await self.wait_until_ready()
        while not self.is_closed():
            interval = max(1, int(self.config.results_lobby_poll_seconds or 2))
            try:
                lobbies = await self.client.fetch_public_lobbies()
            except OpenFrontError as exc:
                delay = interval
                if exc.status == 429 and exc.retry_after:
                    delay = max(delay, exc.retry_after)
                    LOGGER.warning(
                        "Lobby poll rate limited; backing off for %ss", delay
                    )
                else:
                    LOGGER.warning("Lobby poll failed: %s", exc)
                await asyncio.sleep(delay)
                continue

            try:
                self._record_public_lobbies(lobbies)
            except Exception as exc:
                LOGGER.exception("Lobby tracking failed: %s", exc)
                await asyncio.sleep(interval)
                continue
            await asyncio.sleep(interval)

    def _record_public_lobbies(self, lobbies: Iterable[Dict[str, Any]]) -> int:
        now = utcnow_naive()
        next_attempt_at = now + timedelta(seconds=RESULTS_GAME_RETRY_SECONDS)
        added = 0
        for entry in lobbies:
            if not isinstance(entry, dict):
                continue
            game_id = extract_lobby_game_id(entry)
            if not game_id:
                continue
            if track_game(game_id, next_attempt_at=next_attempt_at):
                LOGGER.info(
                    "Discovered new tracked game %s from public lobbies", game_id
                )
                added += 1
        if added:
            self.results_wake_event.set()
        return added

    async def _results_worker(self):
        await self.wait_until_ready()
        while not self.is_closed():
            if self.results_processing_lock.locked():
                await asyncio.sleep(0.5)
                continue
            async with self.results_processing_lock:
                try:
                    (
                        _posted,
                        _failures,
                        processed,
                    ) = await self._process_due_tracked_games()
                except Exception as exc:
                    processed = 0
                    LOGGER.exception("Results worker failed: %s", exc)
            if processed == 0:
                try:
                    await asyncio.wait_for(self.results_wake_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                self.results_wake_event.clear()

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
            results_cutoff = utcnow_naive() - timedelta(days=7)
            for ctx in list(self.guild_contexts.values()):
                try:
                    ctx.models.Audit.delete().where(
                        ctx.models.Audit.created_at < cutoff
                    ).execute()
                    ctx.models.PostedGame.delete().where(
                        ctx.models.PostedGame.posted_at < results_cutoff
                    ).execute()
                except Exception as exc:
                    LOGGER.warning(
                        "Audit cleanup failed for guild %s: %s", ctx.guild_id, exc
                    )
            await asyncio.sleep(24 * 60 * 60)

    async def _process_due_tracked_games(
        self, summary_guild_id: int | None = None
    ) -> tuple[int, int, int]:
        now = utcnow_naive()
        due_games = list_due_tracked_games(now, limit=RESULTS_TRACKED_BATCH_LIMIT)
        if not due_games:
            return 0, 0, 0
        posted_total = 0
        failures_total = 0
        for entry in due_games:
            posted, failures, _retry = await self._process_tracked_game(
                entry.game_id, summary_guild_id=summary_guild_id
            )
            posted_total += posted
            failures_total += failures
        return posted_total, failures_total, len(due_games)

    async def _process_tracked_game(
        self, game_id: str, summary_guild_id: int | None = None
    ) -> tuple[int, int, bool]:
        now = utcnow_naive()
        if not self.guild_contexts:
            reschedule_tracked_game(
                game_id, now + timedelta(seconds=RESULTS_GAME_RETRY_SECONDS)
            )
            return 0, 0, True
        try:
            payload = await self.client.fetch_game(game_id)
        except OpenFrontError as exc:
            retry_seconds = RESULTS_GAME_RETRY_SECONDS
            if exc.status == 429 and exc.retry_after:
                retry_seconds = max(int(exc.retry_after), 1)
            is_unexpected = (
                exc.status is not None
                and exc.status not in RESULTS_GAME_EXPECTED_STATUSES
            )
            if is_unexpected:
                marked_failed = note_tracked_game_unexpected_failure(
                    game_id, now, RESULTS_GAME_UNEXPECTED_FAILURE_LIMIT
                )
                if marked_failed:
                    LOGGER.warning(
                        "Game fetch failed for %s: %s (marked failed after %s unexpected errors)",
                        game_id,
                        exc,
                        RESULTS_GAME_UNEXPECTED_FAILURE_LIMIT,
                    )
                    LOGGER.warning(
                        "Skipping future results polls for %s after unexpected failures",
                        game_id,
                    )
                    failures = 1 if summary_guild_id is not None else 0
                    return 0, failures, False
            else:
                reset_tracked_game_unexpected_failures(game_id)
            reschedule_tracked_game(game_id, now + timedelta(seconds=retry_seconds))
            if exc.status != 404:
                LOGGER.warning("Game fetch failed for %s: %s", game_id, exc)
            failures = 1 if summary_guild_id is not None else 0
            return 0, failures, True

        if not isinstance(payload, dict):
            LOGGER.warning("Game payload invalid for %s: %s", game_id, payload)
            remove_tracked_game(game_id)
            LOGGER.info("Removed tracked game %s from central DB", game_id)
            return 0, 0, False

        reset_tracked_game_unexpected_failures(game_id)

        posted = 0
        failures = 0
        retry_needed = False
        for ctx in list(self.guild_contexts.values()):
            posted_game, failed = await self._post_game_results_for_guild(
                ctx, game_id, payload
            )
            if summary_guild_id is None or ctx.guild_id == summary_guild_id:
                if posted_game:
                    posted += 1
                if failed:
                    failures += 1
            if failed:
                retry_needed = True

        if retry_needed:
            reschedule_tracked_game(
                game_id, now + timedelta(seconds=RESULTS_GAME_RETRY_SECONDS)
            )
        else:
            remove_tracked_game(game_id)
            LOGGER.info("Removed tracked game %s from central DB", game_id)
        return posted, failures, retry_needed

    async def _post_game_results_for_guild(
        self, ctx: GuildContext, game_id: str, payload: Dict[str, Any]
    ) -> tuple[bool, bool]:
        guild = self.get_guild(ctx.guild_id)
        if not guild:
            return False, False

        settings = ctx.models.Settings.get_by_id(1)
        if not settings.results_enabled:
            return False, False
        if not settings.results_channel_id:
            return False, False

        channel = guild.get_channel(settings.results_channel_id)
        if not channel:
            LOGGER.warning(
                "Results channel %s not found for guild %s",
                settings.results_channel_id,
                ctx.guild_id,
            )
            return False, False

        if ctx.models.PostedGame.get_or_none(ctx.models.PostedGame.game_id == game_id):
            return False, False

        clan_tags = [ct.tag_text for ct in ctx.models.ClanTag.select()]
        if not clan_tags:
            return False, False
        normalized_tags = {str(tag).upper() for tag in clan_tags if tag}
        username_index = build_openfront_username_index(ctx.models)

        info = payload.get("info", {}) if isinstance(payload, dict) else {}
        if not isinstance(info, dict):
            return False, False
        config = info.get("config", {}) if isinstance(info, dict) else {}
        if not isinstance(config, dict):
            config = {}
        players = info.get("players", []) if isinstance(info, dict) else []
        if not isinstance(players, list):
            players = []

        game_mode = config.get("gameMode") or info.get("gameMode") or "Unknown mode"
        game_mode_label = str(game_mode)
        is_ffa = game_mode_label.strip().lower() == "free for all"
        num_teams = info.get("numTeams") or config.get("numTeams")
        player_teams = info.get("playerTeams") or config.get("playerTeams")
        total_player_count = info.get("totalPlayerCount")
        max_players = config.get("maxPlayers")
        if total_player_count is None and isinstance(max_players, (int, float)):
            total_player_count = max_players
        if num_teams is None and player_teams is not None:
            if isinstance(player_teams, (int, float)):
                num_teams = int(player_teams)
            else:
                label = str(player_teams).strip()
                if label.isdigit():
                    num_teams = int(label)
        if num_teams is None and total_player_count and player_teams is not None:
            players_per_team = parse_players_per_team(player_teams)
            if players_per_team and float(players_per_team).is_integer():
                if isinstance(total_player_count, (int, float)):
                    if total_player_count % players_per_team == 0:
                        num_teams = int(total_player_count / players_per_team)

        winner_client_ids = extract_winner_client_ids(info, players)
        if not winner_client_ids:
            return False, False
        winning_tags_all: Set[str] = set()
        winning_tags_configured: Set[str] = set()
        winners_lines: list[str] = []
        winners_tagged_count = 0
        opponent_players: Dict[str, list[str]] = {}
        if is_ffa:
            winning_tags_all = resolve_winning_clan_tags(winner_client_ids, players)
            winning_tags_configured = winning_tags_all & normalized_tags
            if not winning_tags_configured:
                return False, False
            for player in players:
                client_id = player.get("clientID")
                if not client_id:
                    continue
                username = player.get("username") or "Unknown"
                matches = username_index.get(username, [])
                if len(matches) == 1:
                    display = f"<@{matches[0]}>"
                else:
                    display = username
                if str(client_id) in winner_client_ids:
                    winners_lines.append(f"🎉 {display}")
                    winners_tagged_count += 1
                    continue
                tag = player.get("clanTag")
                if not tag:
                    continue
                tag_upper = str(tag).upper()
                if tag_upper in winning_tags_all:
                    continue
                opponent_players.setdefault(tag_upper, []).append(display)
        else:
            winning_tags_all = resolve_winning_clan_tags(winner_client_ids, players)
            winning_tags_configured = winning_tags_all & normalized_tags
            if not winning_tags_configured:
                return False, False
            for player in players:
                tag = player.get("clanTag")
                if not tag:
                    continue
                tag_upper = str(tag).upper()
                username = player.get("username") or "Unknown"
                matches = username_index.get(username, [])
                if len(matches) == 1:
                    display = f"<@{matches[0]}>"
                else:
                    display = username
                if tag_upper in winning_tags_configured:
                    winners_tagged_count += 1
                    is_winner = str(player.get("clientID")) in winner_client_ids
                    suffix = "" if is_winner else " - 💀 *died early*"
                    winners_lines.append(f"🎉 {display}{suffix}")
                elif tag_upper not in winning_tags_all:
                    opponent_players.setdefault(tag_upper, []).append(display)

            players_per_team = _compute_players_per_team(
                num_teams, player_teams, total_player_count
            )
            if players_per_team is None:
                players_per_team = parse_players_per_team(player_teams)
            if players_per_team and winners_tagged_count > 0:
                others_count = max(int(players_per_team) - winners_tagged_count, 0)
                if others_count > 0:
                    suffix = "player" if others_count == 1 else "players"
                    winners_lines.append(f"*+{others_count} other {suffix}*")

        opponent_lines = []
        for tag, names in sorted(
            opponent_players.items(),
            key=lambda item: (-len(item[1]), item[0]),
        ):
            count = len(names)
            suffix = "player" if count == 1 else "players"
            names_label = ", ".join(names)
            opponent_lines.append(f"⚔️ {tag}: {count} {suffix} ({names_label})")

        map_name = config.get("gameMap") or "Unknown"
        if not is_ffa and num_teams is not None and player_teams is not None:
            mode_text = format_team_mode(num_teams, player_teams, total_player_count)
        else:
            mode_text = game_mode_label
            if not is_ffa and player_teams:
                label = str(player_teams).strip()
                if label and not label.isdigit():
                    mode_text = f"{mode_text} ({player_teams})"
        replay_link = f"https://openfront.io/#join={game_id}"
        game_start = resolve_game_start(self.client, None, info)
        game_end = resolve_game_end(info)
        duration_seconds = None
        if isinstance(info.get("duration"), (int, float)):
            duration_seconds = int(info.get("duration"))
        elif game_start and game_end:
            duration_seconds = int((game_end - game_start).total_seconds())
        tag_label = ", ".join(sorted(winning_tags_configured)) or "Clan"
        ended_at_line = "Finished: unknown"
        if game_end:
            ended_at_line = f"Finished: <t:{int(game_end.replace(tzinfo=timezone.utc).timestamp())}:F>"
        duration_label = format_duration_seconds(duration_seconds)
        embed = discord.Embed(
            title=f"🏆 Victory for {tag_label}!",
            description=(
                f"Map: **{map_name}**\n"
                f"Mode: **{mode_text}**\n"
                f"{ended_at_line} ({duration_label})\n"
                f"Replay: {replay_link}"
            ),
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Winners",
            value="\n".join(winners_lines) if winners_lines else "Unknown",
            inline=False,
        )
        embed.add_field(
            name="Opponents",
            value="\n".join(opponent_lines) if opponent_lines else "None",
            inline=False,
        )
        try:
            await channel.send(embed=embed)
        except Exception as exc:
            LOGGER.warning(
                "Failed posting results for %s in guild %s: %s",
                game_id,
                ctx.guild_id,
                exc,
            )
            return False, True

        ctx.models.PostedGame.create(
            game_id=game_id,
            game_start=game_start,
            posted_at=utcnow_naive(),
            winning_tags=(
                json.dumps(sorted(winning_tags_configured))
                if winning_tags_configured
                else None
            ),
        )
        return True, False

    async def _seed_recent_results_games(self) -> int:
        now = utcnow_naive()
        start = now - timedelta(hours=2)
        try:
            public_games = await self.client.fetch_public_games(start, now)
        except OpenFrontError as exc:
            LOGGER.warning("Results test seed failed: %s", exc)
            return 0
        added = 0
        for entry in public_games:
            if not isinstance(entry, dict):
                continue
            game_id = extract_game_id(entry)
            if not game_id:
                continue
            if track_game(game_id, next_attempt_at=now):
                added += 1
        if added:
            self.results_wake_event.set()
        return added

    async def run_results_poll(self, ctx: GuildContext) -> str:
        guild = self.get_guild(ctx.guild_id)
        if not guild:
            return "Guild unavailable"
        settings = ctx.models.Settings.get_by_id(1)
        if not settings.results_enabled:
            return "Results disabled"
        if not settings.results_channel_id:
            return "Results channel not set"
        if self.results_processing_lock.locked():
            return "Results poll already running"
        async with self.results_processing_lock:
            posted, failures, _processed = await self._process_due_tracked_games(
                summary_guild_id=ctx.guild_id
            )
        summary = f"Posted {posted} games, failures: {failures}"
        LOGGER.info("Results poll guild=%s summary=%s", ctx.guild_id, summary)
        return summary

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
                    win_count, openfront_username = await self._compute_wins(
                        user, settings.counting_mode, clan_tags
                    )
                    user.last_win_count = win_count
                    user.consecutive_404 = 0
                    user.disabled = 0
                    user.last_error_reason = None
                    if openfront_username:
                        user.last_openfront_username = openfront_username
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

    async def _compute_wins(
        self, user, mode: str, clan_tags: List[str]
    ) -> tuple[int, Optional[str]]:
        player_id = user.player_id
        if mode == "total":
            return await compute_wins_total(self.client, player_id), None
        sessions = list(await self.client.fetch_sessions(player_id))
        last_username = last_session_username_from_sessions(self.client, sessions)
        if mode == "sessions_since_link":
            wins = compute_wins_sessions_since_link_from_sessions(
                self.client, sessions, user.linked_at
            )
            return wins, last_username
        if mode == "sessions_with_clan":
            wins = compute_wins_sessions_with_clan_from_sessions(
                self.client, sessions, clan_tags
            )
            return wins, last_username
        raise ValueError(f"Unknown counting mode {mode}")

    def trigger_sync(self, ctx: GuildContext):
        self.sync_queue.put_nowait(ctx.guild_id)

    def trigger_results_poll(self, ctx: GuildContext) -> bool:
        self.results_wake_event.set()
        return True

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
        openfront_username = await last_session_username(bot.client, player_id)
        now = utcnow_naive()
        ctx.models.User.insert(
            discord_user_id=interaction.user.id,
            player_id=player_id,
            linked_at=now,
            last_win_count=0,
            last_username=getattr(interaction.user, "display_name", None),
            last_openfront_username=openfront_username,
        ).on_conflict_replace().execute()
        win_count = None
        try:
            settings = ctx.models.Settings.get_by_id(1)
            clan_tags = [ct.tag_text for ct in ctx.models.ClanTag.select()]
            record = ctx.models.User.get_by_id(interaction.user.id)
            win_count, openfront_username_from_sync = await bot._compute_wins(
                record, settings.counting_mode, clan_tags
            )
            record.last_win_count = win_count
            if openfront_username_from_sync:
                record.last_openfront_username = openfront_username_from_sync
                openfront_username = openfront_username_from_sync
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
            f"Linked to player `{player_id}`. Last OpenFront username: `{openfront_username or 'unknown'}`"
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
                await interaction.response.send_message(
                    "Admins only: you need admin permissions to check another user.",
                    ephemeral=True,
                )
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
            f"Last OpenFront username: `{record.last_openfront_username or 'unknown'}`\n"
            f"Counting mode: {mode_label}{clans_line}\n"
            f"{role_line}\n"
            f"Last sync: {last_sync_str}"
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.default_permissions(manage_guild=True)
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
            win_count, openfront_username = await bot._compute_wins(
                record, settings.counting_mode, clan_tags
            )
            record.last_win_count = win_count
            if openfront_username:
                record.last_openfront_username = openfront_username
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

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="set_mode",
        description="Set counting mode",
    )
    @app_commands.describe(mode="total | sessions_since_link | sessions_with_clan")
    async def set_mode(interaction: discord.Interaction, mode: str):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        if mode not in COUNTING_MODES:
            await interaction.response.send_message(
                "Invalid mode. Choose one of total | sessions_since_link | sessions_with_clan.",
                ephemeral=True,
            )
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

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="get_mode",
        description="Show current counting mode",
    )
    async def get_mode(interaction: discord.Interaction):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        settings = ctx.models.Settings.get_by_id(1)
        await interaction.response.send_message(
            f"Current counting mode: {settings.counting_mode}", ephemeral=True
        )

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="roles_add",
        description="Add or update a threshold role",
    )
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
        await interaction.response.send_message(
            f"Saved threshold: {wins} wins -> <@&{role.id}>", ephemeral=True
        )

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="roles_remove",
        description="Remove a threshold role",
    )
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
                "Provide wins or role to remove.", ephemeral=True
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
            f"Removed {deleted} role threshold(s).", ephemeral=True
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

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="clan_tag_add",
        description="Add a clan tag",
    )
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

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="clan_tag_remove",
        description="Remove a clan tag",
    )
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
            f"Removed {deleted} clan tag(s) matching '{tag_norm}'", ephemeral=True
        )

    @tree.command(name="clans_list", description="List clan tags")
    async def clans_list(interaction: discord.Interaction):
        ctx = await resolve_context(interaction)
        if not ctx:
            return
        tags = [ct.tag_text for ct in ctx.models.ClanTag.select()]
        await interaction.response.send_message(
            ", ".join(tags) or "No clan tags configured.", ephemeral=True
        )

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="post_game_results_start",
        description="Start posting clan game results",
    )
    async def post_game_results_start(interaction: discord.Interaction):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        settings = ctx.models.Settings.get_by_id(1)
        settings.results_enabled = 1
        settings.save()
        if settings.results_channel_id:
            bot.trigger_results_poll(ctx)
        record_audit(ctx.models, interaction.user.id, "results_start", {})
        message = "Game results posting enabled."
        if not settings.results_channel_id:
            message += " Set a channel with /post_game_results_channel."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="post_game_results_stop",
        description="Stop posting clan game results",
    )
    async def post_game_results_stop(interaction: discord.Interaction):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        settings = ctx.models.Settings.get_by_id(1)
        settings.results_enabled = 0
        settings.save()
        record_audit(ctx.models, interaction.user.id, "results_stop", {})
        await interaction.response.send_message(
            "Game results posting disabled.", ephemeral=True
        )

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="post_game_results_channel",
        description="Set the channel for game results posts",
    )
    async def post_game_results_channel(
        interaction: discord.Interaction, channel: discord.TextChannel
    ):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        settings = ctx.models.Settings.get_by_id(1)
        settings.results_channel_id = channel.id
        settings.save()
        record_audit(
            ctx.models,
            interaction.user.id,
            "results_channel",
            {"channel_id": channel.id},
        )
        if settings.results_enabled:
            bot.trigger_results_poll(ctx)
        await interaction.response.send_message(
            f"Results will be posted in <#{channel.id}>.", ephemeral=True
        )

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="post_game_results_test",
        description="Seed recent finished games for results testing",
    )
    async def post_game_results_test(interaction: discord.Interaction):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        await interaction.response.defer(ephemeral=True, thinking=True)
        added = await bot._seed_recent_results_games()
        record_audit(ctx.models, interaction.user.id, "results_test", {"added": added})
        await interaction.followup.send(
            f"Seeded {added} game(s) for results processing.",
            ephemeral=True,
        )

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="link_override",
        description="Admin override link",
    )
    async def link_override(
        interaction: discord.Interaction, user: discord.Member, player_id: str
    ):
        admin_ctx = await require_admin(interaction)
        if not admin_ctx:
            return
        ctx, _member = admin_ctx
        now = utcnow_naive()
        openfront_username = await last_session_username(bot.client, player_id)
        ctx.models.User.insert(
            discord_user_id=user.id,
            player_id=player_id,
            linked_at=now,
            last_win_count=0,
            last_username=getattr(user, "display_name", None),
            last_openfront_username=openfront_username,
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

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="audit",
        description="Show recent audit events",
    )
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

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="admin_role_add",
        description="Add an admin role for this guild",
    )
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
        message = f"Added admin permission to role <@&{role.id}>"
        try:
            await interaction.response.send_message(message, ephemeral=True)
        except Exception as exc:
            LOGGER.warning("Failed sending response for admin_role_add: %s", exc)
        if interaction.guild:
            sync_failed = False
            try:
                await bot._sync_commands_for_guild(interaction.guild)
            except Exception as exc:
                sync_failed = True
                LOGGER.warning(
                    "Failed to sync commands after admin role add in guild %s: %s",
                    interaction.guild.id,
                    exc,
                )
            if sync_failed:
                try:
                    await interaction.followup.send(
                        "Commands will refresh soon; sync failed.",
                        ephemeral=True,
                    )
                except Exception:
                    LOGGER.debug("Followup after sync failure suppressed.")

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="admin_role_remove",
        description="Remove an admin role for this guild",
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
        message = f"Removed admin permissions from role <@&{role.id}>"
        try:
            await interaction.response.send_message(
                message,
                ephemeral=True,
            )
        except Exception as exc:
            LOGGER.warning("Failed sending response for admin_role_remove: %s", exc)
        if interaction.guild:
            sync_failed = False
            try:
                await bot._sync_commands_for_guild(interaction.guild)
            except Exception as exc:
                sync_failed = True
                LOGGER.warning(
                    "Failed to sync commands after admin role remove in guild %s: %s",
                    interaction.guild.id,
                    exc,
                )
            if sync_failed:
                try:
                    await interaction.followup.send(
                        "Commands will refresh soon; sync failed.",
                        ephemeral=True,
                    )
                except Exception:
                    LOGGER.debug("Followup after sync failure suppressed.")

    @app_commands.default_permissions(manage_guild=True)
    @tree.command(
        name="admin_roles",
        description="List admin roles for this guild",
    )
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

    @app_commands.default_permissions(manage_guild=True)
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
