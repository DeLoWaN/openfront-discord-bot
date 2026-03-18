from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import Sequence

from ...core.config import load_config
from ...core.openfront import OpenFrontClient
from ...data.database import close_shared_database, init_shared_database
from ...data.shared.models import BackfillCursor, BackfillRun
from ...data.shared.schema import bootstrap_shared_schema
from ...services.historical_backfill import (
    create_backfill_run,
    discover_ffa_games,
    discover_team_games,
    hydrate_backfill_run,
    replay_backfill_run,
    reset_ingested_web_data,
    track_backfill_run_rate_limits,
)


def _parse_cli_datetime(value: str) -> datetime:
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _configure_logging(level_name: str) -> None:
    level = getattr(logging, str(level_name or "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        force=True,
    )


def _run_summary(run: BackfillRun) -> str:
    return (
        f"run_id={run.id} status={run.status} "
        f"requested_start={run.requested_start.isoformat()} "
        f"requested_end={run.requested_end.isoformat()} "
        f"discovered={run.discovered_count} cached={run.cached_count} "
        f"ingested={run.ingested_count} matched={run.matched_count} "
        f"skipped={run.skipped_known_count} replayed={run.replayed_count} "
        f"failed={run.failed_count} cache_failed={run.cache_failure_count} "
        f"aggregate_refreshes={run.refreshed_guild_count} "
        f"openfront_rate_limits={run.openfront_rate_limit_hit_count} "
        f"openfront_retry_after={run.openfront_retry_after_count} "
        f"openfront_cooldown_total={run.openfront_cooldown_seconds_total} "
        f"openfront_cooldown_max={run.openfront_cooldown_seconds_max}"
    )


def _cursor_summary(cursor: BackfillCursor) -> str:
    current_window = "-"
    if cursor.cursor_started_at or cursor.cursor_ended_at:
        current_window = (
            f"{cursor.cursor_started_at.isoformat() if cursor.cursor_started_at else '-'}"
            f"..{cursor.cursor_ended_at.isoformat() if cursor.cursor_ended_at else '-'}"
        )
    next_started = cursor.next_started_at.isoformat() if cursor.next_started_at else "-"
    return (
        f"cursor source={cursor.source_type} key={cursor.source_key} "
        f"status={cursor.status} next_started_at={next_started} "
        f"window={current_window} offset={cursor.next_offset}"
    )


def _print_run_status(run_id: int) -> None:
    run = BackfillRun.get_or_none(BackfillRun.id == run_id)
    if run is None:
        raise ValueError(f"Backfill run {run_id} not found")
    print(_run_summary(run))
    cursors = (
        BackfillCursor.select()
        .where(BackfillCursor.run == run)
        .order_by(BackfillCursor.source_type, BackfillCursor.source_key)
    )
    for cursor in cursors:
        print(_cursor_summary(cursor))


async def _execute_run(
    run_id: int,
    *,
    concurrency: int,
    refresh_batch_size: int,
    progress_every: int,
) -> BackfillRun:
    client = OpenFrontClient()
    try:
        logging.info("Starting backfill run %s", run_id)
        with track_backfill_run_rate_limits(client, run_id):
            await asyncio.gather(
                discover_team_games(client, run_id),
                discover_ffa_games(client, run_id),
            )
            run = await hydrate_backfill_run(
                client,
                run_id,
                concurrency=concurrency,
                refresh_batch_size=refresh_batch_size,
                progress_every=progress_every,
                track_rate_limits=False,
            )
        logging.info(
            "Completed backfill run %s status=%s discovered=%s cached=%s ingested=%s matched=%s skipped=%s replayed=%s failed=%s cache_failed=%s aggregate_refreshes=%s openfront_rate_limits=%s openfront_retry_after=%s openfront_cooldown_total=%s openfront_cooldown_max=%s",
            run.id,
            run.status,
            run.discovered_count,
            run.cached_count,
            run.ingested_count,
            run.matched_count,
            run.skipped_known_count,
            run.replayed_count,
            run.failed_count,
            run.cache_failure_count,
            run.refreshed_guild_count,
            run.openfront_rate_limit_hit_count,
            run.openfront_retry_after_count,
            run.openfront_cooldown_seconds_total,
            run.openfront_cooldown_seconds_max,
        )
        return run
    finally:
        await client.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="historical-backfill")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--start", required=True)
    start_parser.add_argument("--end", required=True)
    start_parser.add_argument("--concurrency", type=int, default=4)
    start_parser.add_argument("--refresh-batch-size", type=int, default=100)
    start_parser.add_argument("--progress-every", type=int, default=100)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--run-id", type=int, required=True)

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--run-id", type=int, required=True)
    resume_parser.add_argument("--concurrency", type=int, default=4)
    resume_parser.add_argument("--refresh-batch-size", type=int, default=100)
    resume_parser.add_argument("--progress-every", type=int, default=100)

    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--run-id", type=int, required=True)
    replay_parser.add_argument("--refresh-batch-size", type=int, default=100)

    reset_parser = subparsers.add_parser("reset-data")
    reset_parser.add_argument("--confirm", action="store_true")

    return parser


def _bootstrap_database() -> None:
    config = load_config()
    _configure_logging(config.log_level)
    if config.mariadb is None:
        raise ValueError("mariadb must be configured to manage historical backfills")
    database = init_shared_database(config.mariadb)
    bootstrap_shared_schema(database)


def run_command(args: argparse.Namespace) -> int:
    if args.command == "start":
        run = create_backfill_run(
            start=_parse_cli_datetime(args.start),
            end=_parse_cli_datetime(args.end),
        )
        run = asyncio.run(
            _execute_run(
                run.id,
                concurrency=args.concurrency,
                refresh_batch_size=args.refresh_batch_size,
                progress_every=args.progress_every,
            )
        )
        _print_run_status(run.id)
        return 0

    if args.command == "status":
        _print_run_status(args.run_id)
        return 0

    if args.command == "resume":
        if BackfillRun.get_or_none(BackfillRun.id == args.run_id) is None:
            raise ValueError(f"Backfill run {args.run_id} not found")
        run = asyncio.run(
            _execute_run(
                args.run_id,
                concurrency=args.concurrency,
                refresh_batch_size=args.refresh_batch_size,
                progress_every=args.progress_every,
            )
        )
        _print_run_status(run.id)
        return 0

    if args.command == "replay":
        if BackfillRun.get_or_none(BackfillRun.id == args.run_id) is None:
            raise ValueError(f"Backfill run {args.run_id} not found")
        run = replay_backfill_run(
            args.run_id,
            refresh_batch_size=args.refresh_batch_size,
        )
        _print_run_status(run.id)
        return 0

    if args.command == "reset-data":
        if not args.confirm:
            raise ValueError(
                "Reset confirmation required to wipe ingested web data"
            )
        summary = reset_ingested_web_data()
        print(
            " ".join(
                (
                    f"deleted_backfill_runs={summary.backfill_runs}",
                    f"deleted_backfill_cursors={summary.backfill_cursors}",
                    f"deleted_backfill_games={summary.backfill_games}",
                    "deleted_cached_openfront_games="
                    f"{summary.cached_openfront_games}",
                    f"deleted_observed_games={summary.observed_games}",
                    f"deleted_game_participants={summary.game_participants}",
                    "deleted_guild_player_aggregates="
                    f"{summary.guild_player_aggregates}",
                    f"deleted_total={summary.total_deleted}",
                )
            )
        )
        return 0

    raise ValueError(f"Unknown command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code)

    try:
        _bootstrap_database()
        return run_command(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        close_shared_database()


if __name__ == "__main__":
    raise SystemExit(main())
