from __future__ import annotations

import asyncio
import json
import logging
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from peewee import fn

from ..core.openfront import OpenFrontRateLimitEvent
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
TEAM_DISCOVERY_CONCURRENCY = 2


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


@dataclass(frozen=True)
class HydrationResult:
    outcome: str
    matched_guild_ids: set[int]


class CachePayloadError(ValueError):
    pass


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


def _sync_run_rate_limit_counters(run: BackfillRun) -> None:
    fresh = BackfillRun.get_by_id(run.id)
    run.openfront_rate_limit_hit_count = fresh.openfront_rate_limit_hit_count
    run.openfront_retry_after_count = fresh.openfront_retry_after_count
    run.openfront_cooldown_seconds_total = fresh.openfront_cooldown_seconds_total
    run.openfront_cooldown_seconds_max = fresh.openfront_cooldown_seconds_max


def _record_openfront_rate_limit(
    run_id: int,
    event: OpenFrontRateLimitEvent,
) -> None:
    if event.status != 429:
        return
    retry_after_count = 1 if event.source != "fallback" else 0
    (
        BackfillRun.update(
            openfront_rate_limit_hit_count=BackfillRun.openfront_rate_limit_hit_count + 1,
            openfront_retry_after_count=(
                BackfillRun.openfront_retry_after_count + retry_after_count
            ),
            openfront_cooldown_seconds_total=(
                BackfillRun.openfront_cooldown_seconds_total + event.cooldown_seconds
            ),
            openfront_cooldown_seconds_max=fn.MAX(
                BackfillRun.openfront_cooldown_seconds_max,
                event.cooldown_seconds,
            ),
        )
        .where(BackfillRun.id == run_id)
        .execute()
    )
    LOGGER.warning(
        "run=%s openfront_rate_limit status=%s retry_after=%s source=%s url=%s",
        run_id,
        event.status,
        event.cooldown_seconds,
        event.source,
        event.url,
    )


def _attach_rate_limit_observer(client: object, observer) -> object:
    add_observer = getattr(client, "add_rate_limit_observer", None)
    if callable(add_observer):
        return add_observer(observer)
    set_observer = getattr(client, "set_rate_limit_observer", None)
    if callable(set_observer):
        previous = set_observer(observer)

        def restore():
            set_observer(previous)

        return restore

    def noop():
        return None

    return noop


@contextmanager
def track_backfill_run_rate_limits(client: object, run_id: int):
    remover = _attach_rate_limit_observer(
        client,
        lambda event: _record_openfront_rate_limit(run_id, event),
    )
    try:
        yield
    finally:
        remover()


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


def _lookup_cache_entry(backfill_game: BackfillGame) -> CachedOpenFrontGame | None:
    cache_entry = backfill_game.cache_entry
    if cache_entry is None:
        cache_entry = CachedOpenFrontGame.get_or_none(
            CachedOpenFrontGame.openfront_game_id == backfill_game.openfront_game_id
        )
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
    cache_entry = _lookup_cache_entry(backfill_game)
    if cache_entry is None:
        return None, None
    try:
        if cache_entry.turn_payload_json:
            return cache_entry, json.loads(cache_entry.turn_payload_json)
        return cache_entry, json.loads(cache_entry.payload_json)
    except (TypeError, ValueError) as exc:
        raise CachePayloadError(
            f"Unreadable cached payload for {backfill_game.openfront_game_id}: {exc}"
        ) from exc


def _refresh_guild_batch(affected_guild_ids: set[int]) -> int:
    refreshed = 0
    for guild_id in sorted(affected_guild_ids):
        refresh_guild_player_aggregates(guild_id)
        refreshed += 1
    return refreshed


def _clear_failure_counter(run: BackfillRun, previous_status: str) -> None:
    if previous_status == "failed" and run.failed_count > 0:
        run.failed_count -= 1
    if previous_status == "cache_failed" and run.cache_failure_count > 0:
        run.cache_failure_count -= 1


def _record_skipped_known(run: BackfillRun, backfill_game: BackfillGame) -> None:
    _clear_failure_counter(run, backfill_game.status)
    if backfill_game.status != "skipped_known":
        run.skipped_known_count += 1
    backfill_game.status = "skipped_known"
    backfill_game.last_error = None
    backfill_game.matched_guild_count = 0
    backfill_game.save()


def _record_failure(
    run: BackfillRun,
    backfill_game: BackfillGame,
    error: str,
    *,
    cache_failure: bool = False,
) -> None:
    next_status = "cache_failed" if cache_failure else "failed"
    if backfill_game.status != next_status:
        _clear_failure_counter(run, backfill_game.status)
        if cache_failure:
            run.cache_failure_count += 1
        else:
            run.failed_count += 1
    backfill_game.status = next_status
    backfill_game.last_error = error
    backfill_game.matched_guild_count = 0
    backfill_game.save()


def _record_success(
    run: BackfillRun,
    backfill_game: BackfillGame,
    cache_entry: CachedOpenFrontGame,
    matched_guild_ids: set[int],
    *,
    replay: bool = False,
) -> None:
    _clear_failure_counter(run, backfill_game.status)
    backfill_game.cache_entry = cache_entry
    backfill_game.status = "completed"
    backfill_game.last_error = None
    backfill_game.matched_guild_count = len(matched_guild_ids)
    backfill_game.save()
    run.cached_count += 1
    run.ingested_count += 1
    if matched_guild_ids:
        run.matched_count += 1
    if replay:
        run.replayed_count += 1


def _has_prior_successful_hydration(backfill_game: BackfillGame) -> bool:
    return (
        BackfillGame.select()
        .where(
            (BackfillGame.openfront_game_id == backfill_game.openfront_game_id)
            & (BackfillGame.run != backfill_game.run)
            & (BackfillGame.status == "completed")
        )
        .exists()
    )


def _should_skip_known_history(backfill_game: BackfillGame) -> bool:
    if not _has_prior_successful_hydration(backfill_game):
        return False
    try:
        cache_entry, payload = _get_payload_from_cache(backfill_game)
    except CachePayloadError:
        return False
    return cache_entry is not None and payload is not None


def _stored_guild_ids_for_game(openfront_game_id: str) -> set[int]:
    query = (
        GameParticipant.select(GameParticipant.guild_id)
        .join(ObservedGame)
        .where(ObservedGame.openfront_game_id == openfront_game_id)
        .distinct()
    )
    return {int(row.guild_id) for row in query}


def _finalize_run(run: BackfillRun) -> None:
    _sync_run_rate_limit_counters(run)
    remaining = (
        BackfillGame.select()
        .where((BackfillGame.run == run) & (BackfillGame.status == "pending"))
        .count()
    )
    if remaining == 0:
        run.status = (
            "completed_with_failures"
            if run.failed_count or run.cache_failure_count
            else "completed"
        )
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    run.save()


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


async def _discover_team_cursor_games(
    client: object,
    run: BackfillRun,
    cursor_id: int,
    *,
    window_size: timedelta,
) -> int:
    cursor = BackfillCursor.get_by_id(cursor_id)
    discovered_count = 0
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
    return discovered_count


async def discover_team_games(
    client: object,
    run_id: int,
    *,
    window_size: timedelta = DISCOVERY_WINDOW,
    concurrency: int = TEAM_DISCOVERY_CONCURRENCY,
) -> int:
    run = BackfillRun.get_by_id(run_id)
    cursors = (
        BackfillCursor.select()
        .where(
            (BackfillCursor.run == run)
            & (BackfillCursor.source_type == "team")
            & (BackfillCursor.status != "completed")
        )
        .order_by(BackfillCursor.source_key)
    )
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def discover_cursor(cursor_id: int) -> int:
        async with semaphore:
            return await _discover_team_cursor_games(
                client,
                run,
                cursor_id,
                window_size=window_size,
            )

    discovered_count = sum(
        await asyncio.gather(*(discover_cursor(cursor.id) for cursor in cursors))
    )
    if discovered_count:
        (
            BackfillRun.update(
                discovered_count=BackfillRun.discovered_count + discovered_count
            )
            .where(BackfillRun.id == run.id)
            .execute()
        )
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
        (
            BackfillRun.update(
                discovered_count=BackfillRun.discovered_count + discovered_count
            )
            .where(BackfillRun.id == run.id)
            .execute()
        )
    LOGGER.info("run=%s source=ffa discovered=%s", run.id, discovered_count)
    return discovered_count


async def hydrate_backfill_run(
    client: object,
    run_id: int,
    *,
    concurrency: int = 4,
    refresh_batch_size: int = 100,
    progress_every: int = 100,
    track_rate_limits: bool = True,
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
            & (BackfillGame.status.in_(("pending", "failed", "cache_failed")))
        )
        .order_by(BackfillGame.id)
    )
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def process_game(game_id: int):
        async with semaphore:
            backfill_game = BackfillGame.get_by_id(game_id)
            if _should_skip_known_history(backfill_game):
                matched_guild_ids = _stored_guild_ids_for_game(
                    backfill_game.openfront_game_id
                )
                _record_skipped_known(run, backfill_game)
                return HydrationResult("skipped_known", matched_guild_ids)
            backfill_game.attempts += 1
            backfill_game.save()
            try:
                cache_entry, payload = _get_payload_from_cache(backfill_game)
            except CachePayloadError as exc:
                LOGGER.warning(
                    "run=%s cache_repair game=%s reason=%s",
                    run.id,
                    backfill_game.openfront_game_id,
                    exc,
                )
                cache_entry = None
                payload = None
            if payload is None:
                include_turns = backfill_game.source_type == "team"
                payload = await _fetch_game_payload(
                    client,
                    backfill_game.openfront_game_id,
                    include_turns=include_turns,
                )
                cache_entry = _cache_payload(backfill_game.openfront_game_id, payload)
            assert cache_entry is not None
            summary = ingest_game_payload(payload, refresh_aggregates=False)
            _record_success(run, backfill_game, cache_entry, summary.matched_guild_ids)
            return HydrationResult("completed", summary.matched_guild_ids)

    context = (
        track_backfill_run_rate_limits(client, run.id)
        if track_rate_limits
        else nullcontext()
    )
    with context:
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
                    try:
                        _record_failure(run, backfill_game, str(result))
                    except Exception as record_exc:
                        LOGGER.warning(
                            "run=%s failed to persist failure for game=%s original=%s persistence=%s",
                            run.id,
                            backfill_game.openfront_game_id,
                            result,
                            record_exc,
                        )
                    continue
                if result.matched_guild_ids:
                    affected_guild_ids.update(result.matched_guild_ids)
                if result.outcome == "skipped_known":
                    continue
                processed_successes += 1
                if (
                    processed_successes % max(1, refresh_batch_size) == 0
                    and affected_guild_ids
                ):
                    run.refreshed_guild_count += _refresh_guild_batch(affected_guild_ids)
                    affected_guild_ids.clear()
            _sync_run_rate_limit_counters(run)
            run.save()
            LOGGER.info(
                "run=%s hydration_progress processed=%s total=%s cached=%s ingested=%s matched=%s skipped=%s failed=%s cache_failed=%s aggregate_refreshes=%s openfront_rate_limits=%s openfront_retry_after=%s openfront_cooldown_total=%s openfront_cooldown_max=%s",
                run.id,
                min(offset + len(batch), len(pending_games)),
                len(pending_games),
                run.cached_count,
                run.ingested_count,
                run.matched_count,
                run.skipped_known_count,
                run.failed_count,
                run.cache_failure_count,
                run.refreshed_guild_count,
                run.openfront_rate_limit_hit_count,
                run.openfront_retry_after_count,
                run.openfront_cooldown_seconds_total,
                run.openfront_cooldown_seconds_max,
            )

        if affected_guild_ids:
            run.refreshed_guild_count += _refresh_guild_batch(affected_guild_ids)
        _finalize_run(run)
        LOGGER.info(
            "run=%s hydration_complete status=%s cached=%s ingested=%s matched=%s skipped=%s failed=%s cache_failed=%s aggregate_refreshes=%s openfront_rate_limits=%s openfront_retry_after=%s openfront_cooldown_total=%s openfront_cooldown_max=%s",
            run.id,
            run.status,
            run.cached_count,
            run.ingested_count,
            run.matched_count,
            run.skipped_known_count,
            run.failed_count,
            run.cache_failure_count,
            run.refreshed_guild_count,
            run.openfront_rate_limit_hit_count,
            run.openfront_retry_after_count,
            run.openfront_cooldown_seconds_total,
            run.openfront_cooldown_seconds_max,
        )
    return BackfillRun.get_by_id(run_id)


def replay_backfill_run(
    run_id: int,
    *,
    refresh_batch_size: int = 100,
) -> BackfillRun:
    run = BackfillRun.get_by_id(run_id)
    run.status = "running"
    if run.started_at is None:
        run.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    run.save()
    affected_guild_ids: set[int] = set()
    processed = 0
    queued_games = list(
        BackfillGame.select()
        .where(BackfillGame.run == run)
        .order_by(BackfillGame.id)
    )
    if queued_games and not any(_lookup_cache_entry(game) is not None for game in queued_games):
        raise ValueError(f"No cached payload available for backfill run {run_id}")
    for backfill_game in queued_games:
        cache_entry = _lookup_cache_entry(backfill_game)
        if cache_entry is None:
            _record_failure(
                run,
                backfill_game,
                f"No cached payload available for {backfill_game.openfront_game_id}",
                cache_failure=True,
            )
            continue
        try:
            _cache_entry, payload = _get_payload_from_cache(backfill_game)
        except CachePayloadError as exc:
            _record_failure(run, backfill_game, str(exc), cache_failure=True)
            continue
        assert _cache_entry is not None
        summary = ingest_game_payload(payload, refresh_aggregates=False)
        _record_success(
            run,
            backfill_game,
            _cache_entry,
            summary.matched_guild_ids,
            replay=True,
        )
        if summary.matched_guild_ids:
            affected_guild_ids.update(summary.matched_guild_ids)
        processed += 1
        if processed % max(1, refresh_batch_size) == 0 and affected_guild_ids:
            run.refreshed_guild_count += _refresh_guild_batch(affected_guild_ids)
            affected_guild_ids.clear()

    if affected_guild_ids:
        run.refreshed_guild_count += _refresh_guild_batch(affected_guild_ids)
    _finalize_run(run)
    return BackfillRun.get_by_id(run_id)
