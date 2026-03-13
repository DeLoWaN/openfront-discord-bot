from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..data.database import shared_database
from ..data.shared.models import (
    BackfillCursor,
    BackfillGame,
    BackfillRun,
    CachedOpenFrontGame,
    GameParticipant,
    GuildClanTag,
    GuildPlayerAggregate,
    ObservedGame,
)
from .openfront_ingestion import ingest_game_payload, refresh_guild_player_aggregates

LOGGER = logging.getLogger(__name__)
DISCOVERY_WINDOW = timedelta(days=2)


@dataclass(frozen=True)
class IngestedWebDataResetSummary:
    backfill_runs: int
    backfill_cursors: int
    backfill_games: int
    cached_openfront_games: int
    observed_games: int
    game_participants: int
    guild_player_aggregates: int

    @property
    def total_deleted(self) -> int:
        return (
            self.backfill_runs
            + self.backfill_cursors
            + self.backfill_games
            + self.cached_openfront_games
            + self.observed_games
            + self.game_participants
            + self.guild_player_aggregates
        )


def _parse_api_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _parse_payload_datetime(value: object) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc).replace(
            tzinfo=None
        )
    if isinstance(value, str):
        return _parse_api_datetime(value)
    return None


def _in_start_range(
    value: datetime | None,
    start: datetime,
    end: datetime,
) -> bool:
    if value is None:
        return False
    return start <= value <= end


def _cursor_window_end(
    window_start: datetime,
    requested_end: datetime,
    window_size: timedelta,
) -> datetime:
    return min(window_start + window_size, requested_end)


def _payload_info(payload: dict[str, object]) -> dict[str, object]:
    info = payload.get("info")
    if isinstance(info, dict):
        return info
    return payload


def _queue_game(
    run: BackfillRun,
    *,
    openfront_game_id: str,
    source_type: str,
    started_at: datetime | None,
) -> bool:
    _queued, created = BackfillGame.get_or_create(
        run=run,
        openfront_game_id=openfront_game_id,
        defaults={
            "source_type": source_type,
            "started_at": started_at,
            "status": "pending",
        },
    )
    return created


def _complete_or_advance_cursor(
    cursor: BackfillCursor,
    *,
    window_start: datetime,
    window_end: datetime,
    requested_end: datetime,
) -> None:
    cursor.cursor_started_at = window_start
    cursor.cursor_ended_at = window_end
    if window_end >= requested_end:
        cursor.status = "completed"
        cursor.next_started_at = requested_end
    else:
        cursor.status = "running"
        cursor.next_started_at = window_end
    cursor.next_offset = 0
    cursor.save()


def _cache_payload(
    openfront_game_id: str,
    payload: dict[str, object],
) -> CachedOpenFrontGame:
    info = _payload_info(payload)
    config = info.get("config")
    if not isinstance(config, dict):
        config = {}
    payload_without_turns = dict(payload)
    payload_without_turns.pop("turns", None)
    turn_payload_json = json.dumps(payload) if "turns" in payload else None
    cache_entry, created = CachedOpenFrontGame.get_or_create(
        openfront_game_id=openfront_game_id,
        defaults={
            "game_type": str(config.get("gameType") or info.get("gameType") or ""),
            "mode_name": str(config.get("gameMode") or info.get("gameMode") or ""),
            "started_at": _parse_payload_datetime(info.get("start")),
            "ended_at": _parse_payload_datetime(info.get("end")),
            "payload_json": json.dumps(payload_without_turns),
            "turn_payload_json": turn_payload_json,
        },
    )
    if not created:
        cache_entry.game_type = str(config.get("gameType") or info.get("gameType") or "")
        cache_entry.mode_name = str(config.get("gameMode") or info.get("gameMode") or "")
        cache_entry.started_at = _parse_payload_datetime(info.get("start"))
        cache_entry.ended_at = _parse_payload_datetime(info.get("end"))
        cache_entry.payload_json = json.dumps(payload_without_turns)
        cache_entry.turn_payload_json = turn_payload_json
        cache_entry.fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
        cache_entry.save()
    return cache_entry


def reset_ingested_web_data() -> IngestedWebDataResetSummary:
    with shared_database.atomic():
        game_participants = GameParticipant.delete().execute()
        guild_player_aggregates = GuildPlayerAggregate.delete().execute()
        backfill_games = BackfillGame.delete().execute()
        backfill_cursors = BackfillCursor.delete().execute()
        backfill_runs = BackfillRun.delete().execute()
        cached_openfront_games = CachedOpenFrontGame.delete().execute()
        observed_games = ObservedGame.delete().execute()

    return IngestedWebDataResetSummary(
        backfill_runs=backfill_runs,
        backfill_cursors=backfill_cursors,
        backfill_games=backfill_games,
        cached_openfront_games=cached_openfront_games,
        observed_games=observed_games,
        game_participants=game_participants,
        guild_player_aggregates=guild_player_aggregates,
    )


def _get_payload_from_cache(
    backfill_game: BackfillGame,
) -> tuple[CachedOpenFrontGame | None, dict[str, object] | None]:
    cache_entry = backfill_game.cache_entry
    if cache_entry is None:
        cache_entry = CachedOpenFrontGame.get_or_none(
            CachedOpenFrontGame.openfront_game_id == backfill_game.openfront_game_id
        )
    if cache_entry is None:
        return None, None
    if cache_entry.turn_payload_json:
        return cache_entry, json.loads(cache_entry.turn_payload_json)
    return cache_entry, json.loads(cache_entry.payload_json)


def _refresh_guild_batch(affected_guild_ids: set[int]) -> int:
    refreshed = 0
    for guild_id in sorted(affected_guild_ids):
        refresh_guild_player_aggregates(guild_id)
        refreshed += 1
    return refreshed


async def _fetch_game_payload(
    client: object,
    game_id: str,
    *,
    include_turns: bool,
):
    try:
        return await client.fetch_game(game_id, include_turns=include_turns)
    except TypeError:
        return await client.fetch_game(game_id)


def create_backfill_run(
    *,
    start: datetime,
    end: datetime,
) -> BackfillRun:
    if end < start:
        raise ValueError("end must not be earlier than start")

    run = BackfillRun.create(
        requested_start=start,
        requested_end=end,
        status="pending",
    )
    BackfillCursor.create(
        run=run,
        source_type="ffa",
        source_key="global",
        next_started_at=start,
        status="pending",
    )
    tags = sorted({row.tag_text.upper() for row in GuildClanTag.select()})
    for tag in tags:
        BackfillCursor.create(
            run=run,
            source_type="team",
            source_key=tag,
            next_started_at=start,
            status="pending",
        )
    return run


async def discover_team_games(
    client: object,
    run_id: int,
    *,
    window_size: timedelta = DISCOVERY_WINDOW,
) -> int:
    run = BackfillRun.get_by_id(run_id)
    discovered_count = 0
    cursors = (
        BackfillCursor.select()
        .where(
            (BackfillCursor.run == run)
            & (BackfillCursor.source_type == "team")
            & (BackfillCursor.status != "completed")
        )
        .order_by(BackfillCursor.source_key)
    )
    for cursor in cursors:
        window_start = cursor.next_started_at or run.requested_start
        while window_start <= run.requested_end:
            window_end = _cursor_window_end(
                window_start,
                run.requested_end,
                window_size,
            )
            LOGGER.info(
                "run=%s source=team key=%s window_start=%s window_end=%s",
                run.id,
                cursor.source_key,
                window_start.isoformat(),
                window_end.isoformat(),
            )
            sessions = await client.fetch_clan_sessions(
                cursor.source_key,
                start=window_start,
                end=window_end,
            )
            for session in sessions:
                game_id = str(session.get("gameId") or "").strip()
                if not game_id:
                    continue
                started_at = _parse_api_datetime(session.get("gameStart"))
                if not _in_start_range(started_at, run.requested_start, run.requested_end):
                    continue
                if _queue_game(
                    run,
                    openfront_game_id=game_id,
                    source_type="team",
                    started_at=started_at,
                ):
                    discovered_count += 1
            _complete_or_advance_cursor(
                cursor,
                window_start=window_start,
                window_end=window_end,
                requested_end=run.requested_end,
            )
            if cursor.status == "completed":
                break
            window_start = cursor.next_started_at or run.requested_start
    if discovered_count:
        run.discovered_count += discovered_count
        run.save()
    LOGGER.info("run=%s source=team discovered=%s", run.id, discovered_count)
    return discovered_count


async def discover_ffa_games(
    client: object,
    run_id: int,
    *,
    window_size: timedelta = DISCOVERY_WINDOW,
) -> int:
    run = BackfillRun.get_by_id(run_id)
    cursor = BackfillCursor.get(
        (BackfillCursor.run == run) & (BackfillCursor.source_type == "ffa")
    )
    discovered_count = 0
    window_start = cursor.next_started_at or run.requested_start
    while window_start <= run.requested_end and cursor.status != "completed":
        window_end = _cursor_window_end(
            window_start,
            run.requested_end,
            window_size,
        )
        LOGGER.info(
            "run=%s source=ffa key=%s window_start=%s window_end=%s",
            run.id,
            cursor.source_key,
            window_start.isoformat(),
            window_end.isoformat(),
        )
        games = await client.fetch_public_games(window_start, window_end)
        for game in games:
            if str(game.get("mode") or "") != "Free For All":
                continue
            game_id = str(game.get("game") or "").strip()
            if not game_id:
                continue
            started_at = _parse_api_datetime(game.get("start"))
            if not _in_start_range(started_at, run.requested_start, run.requested_end):
                continue
            if _queue_game(
                run,
                openfront_game_id=game_id,
                source_type="ffa",
                started_at=started_at,
            ):
                discovered_count += 1
        _complete_or_advance_cursor(
            cursor,
            window_start=window_start,
            window_end=window_end,
            requested_end=run.requested_end,
        )
        if cursor.status == "completed":
            break
        window_start = cursor.next_started_at or run.requested_start
    if discovered_count:
        run.discovered_count += discovered_count
        run.save()
    LOGGER.info("run=%s source=ffa discovered=%s", run.id, discovered_count)
    return discovered_count


async def hydrate_backfill_run(
    client: object,
    run_id: int,
    *,
    concurrency: int = 4,
    refresh_batch_size: int = 100,
    progress_every: int = 100,
) -> BackfillRun:
    run = BackfillRun.get_by_id(run_id)
    run.status = "running"
    if run.started_at is None:
        run.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    run.save()

    pending_games = list(
        BackfillGame.select()
        .where(
            (BackfillGame.run == run)
            & (BackfillGame.status.in_(("pending", "failed")))
        )
        .order_by(BackfillGame.id)
    )
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def process_game(game_id: int):
        async with semaphore:
            backfill_game = BackfillGame.get_by_id(game_id)
            backfill_game.attempts += 1
            cache_entry, payload = _get_payload_from_cache(backfill_game)
            if payload is None:
                include_turns = backfill_game.source_type == "team"
                payload = await _fetch_game_payload(
                    client,
                    backfill_game.openfront_game_id,
                    include_turns=include_turns,
                )
                cache_entry = _cache_payload(backfill_game.openfront_game_id, payload)
            assert cache_entry is not None
            summary = ingest_game_payload(payload)
            backfill_game.cache_entry = cache_entry
            backfill_game.status = "completed"
            backfill_game.last_error = None
            backfill_game.save()
            return summary.matched_guild_ids

    affected_guild_ids: set[int] = set()
    processed_successes = 0
    batch_size = max(1, progress_every)
    for offset in range(0, len(pending_games), batch_size):
        batch = pending_games[offset : offset + batch_size]
        results = await asyncio.gather(
            *(process_game(game.id) for game in batch),
            return_exceptions=True,
        )
        for backfill_game, result in zip(batch, results):
            if isinstance(result, Exception):
                failed_game = BackfillGame.get_by_id(backfill_game.id)
                failed_game.status = "failed"
                failed_game.last_error = str(result)
                failed_game.save()
                run.failed_count += 1
                continue
            run.cached_count += 1
            run.ingested_count += 1
            if result:
                run.matched_count += 1
                affected_guild_ids.update(result)
            processed_successes += 1
            if (
                processed_successes % max(1, refresh_batch_size) == 0
                and affected_guild_ids
            ):
                run.refreshed_guild_count += _refresh_guild_batch(affected_guild_ids)
                affected_guild_ids.clear()
        LOGGER.info(
            "run=%s hydration_progress processed=%s total=%s cached=%s ingested=%s matched=%s failed=%s",
            run.id,
            min(offset + len(batch), len(pending_games)),
            len(pending_games),
            run.cached_count,
            run.ingested_count,
            run.matched_count,
            run.failed_count,
        )

    if affected_guild_ids:
        run.refreshed_guild_count += _refresh_guild_batch(affected_guild_ids)

    remaining = (
        BackfillGame.select()
        .where((BackfillGame.run == run) & (BackfillGame.status == "pending"))
        .count()
    )
    if remaining == 0:
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    run.save()
    LOGGER.info(
        "run=%s hydration_complete status=%s cached=%s ingested=%s matched=%s failed=%s refreshed=%s",
        run.id,
        run.status,
        run.cached_count,
        run.ingested_count,
        run.matched_count,
        run.failed_count,
        run.refreshed_guild_count,
    )
    return BackfillRun.get_by_id(run_id)


def replay_backfill_run(
    run_id: int,
    *,
    refresh_batch_size: int = 100,
) -> BackfillRun:
    run = BackfillRun.get_by_id(run_id)
    affected_guild_ids: set[int] = set()
    processed = 0
    queued_games = (
        BackfillGame.select()
        .where(BackfillGame.run == run)
        .order_by(BackfillGame.id)
    )
    for backfill_game in queued_games:
        cache_entry, payload = _get_payload_from_cache(backfill_game)
        if cache_entry is None or payload is None:
            raise ValueError(
                f"No cached payload available for {backfill_game.openfront_game_id}"
            )
        summary = ingest_game_payload(payload)
        backfill_game.cache_entry = cache_entry
        backfill_game.status = "completed"
        backfill_game.last_error = None
        backfill_game.save()
        run.cached_count += 1
        run.ingested_count += 1
        if summary.matched_guild_ids:
            run.matched_count += 1
            affected_guild_ids.update(summary.matched_guild_ids)
        processed += 1
        if processed % max(1, refresh_batch_size) == 0 and affected_guild_ids:
            run.refreshed_guild_count += _refresh_guild_batch(affected_guild_ids)
            affected_guild_ids.clear()

    if affected_guild_ids:
        run.refreshed_guild_count += _refresh_guild_batch(affected_guild_ids)
    run.save()
    return BackfillRun.get_by_id(run_id)
