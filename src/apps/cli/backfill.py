from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Sequence

from ...core.config import load_config
from ...core.openfront import OpenFrontClient
from ...data.database import close_shared_database, init_shared_database
from ...data.shared.models import BackfillCursor, BackfillRun
from ...data.shared.schema import bootstrap_shared_schema
from ...services.historical_backfill import (
    OpenFrontProbeSummary,
    create_backfill_run,
    discover_ffa_games,
    discover_team_games,
    hydrate_backfill_run,
    probe_openfront_profile,
    replay_backfill_run,
    reset_ingested_web_data,
    track_backfill_run_rate_limits,
)

BACKFILL_DEFAULT_OPENFRONT_MAX_IN_FLIGHT = 1
BACKFILL_DEFAULT_OPENFRONT_SUCCESS_DELAY_SECONDS = 2.2
BACKFILL_DEFAULT_OPENFRONT_MIN_RATE_LIMIT_COOLDOWN_SECONDS = 2.2
PROBE_DEFAULT_SAMPLE_SIZE = 100
PROBE_STOP_AFTER_RATE_LIMITS = 3
PROBE_STOP_ON_RETRY_AFTER_SECONDS = 30.0


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
        f"discovered={run.discovered_count} "
        f"discovery_skipped={run.discovery_skipped_known_count} "
        f"cached={run.cached_count} "
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


def _probe_summary(summary: OpenFrontProbeSummary) -> str:
    latency_p50 = (
        f"{summary.latency_p50_seconds:.3f}" if summary.latency_p50_seconds is not None else "-"
    )
    latency_p95 = (
        f"{summary.latency_p95_seconds:.3f}" if summary.latency_p95_seconds is not None else "-"
    )
    throughput = (
        f"{summary.throughput_per_second:.3f}"
        if summary.throughput_per_second is not None
        else "-"
    )
    retry_after_distribution = ",".join(
        f"{bucket}:{count}"
        for bucket, count in sorted(summary.retry_after_distribution.items())
    ) or "-"
    return (
        f"candidates={summary.candidate_count} sampled={summary.sampled_count} "
        f"attempted={summary.attempted_count} success={summary.success_count} "
        f"rate_limits={summary.rate_limit_count} "
        f"zero_retry_after={summary.zero_retry_after_count} "
        f"other_errors={summary.other_error_count} "
        f"retry_after_max={summary.retry_after_max} "
        f"retry_after_distribution={retry_after_distribution} "
        f"latency_p50={latency_p50} latency_p95={latency_p95} "
        f"throughput={throughput} "
        f"profile_max_in_flight={summary.openfront_max_in_flight} "
        f"profile_success_delay={summary.openfront_success_delay_seconds} "
        "profile_min_rate_limit_cooldown="
        f"{summary.openfront_min_rate_limit_cooldown_seconds} "
        f"stopped_early={summary.stopped_early} "
        f"stop_reason={summary.stop_reason or '-'}"
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


@contextmanager
def _openfront_profile(
    *,
    max_in_flight: int,
    success_delay_seconds: float,
    min_rate_limit_cooldown_seconds: float,
):
    updates = {
        "OPENFRONT_MAX_IN_FLIGHT": str(max_in_flight),
        "OPENFRONT_SUCCESS_DELAY_SECONDS": str(success_delay_seconds),
        "OPENFRONT_MIN_RATE_LIMIT_COOLDOWN_SECONDS": str(
            min_rate_limit_cooldown_seconds
        ),
    }
    previous = {name: os.environ.get(name) for name in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for name, original_value in previous.items():
            if original_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = original_value


async def _execute_run(
    run_id: int,
    *,
    concurrency: int,
    refresh_batch_size: int,
    progress_every: int,
    openfront_max_in_flight: int,
    openfront_success_delay_seconds: float,
    openfront_min_rate_limit_cooldown_seconds: float,
) -> BackfillRun:
    with _openfront_profile(
        max_in_flight=openfront_max_in_flight,
        success_delay_seconds=openfront_success_delay_seconds,
        min_rate_limit_cooldown_seconds=openfront_min_rate_limit_cooldown_seconds,
    ):
        client = OpenFrontClient()
        config = load_config()
        if config.openfront is not None:
            client = OpenFrontClient(bypass_config=config.openfront)
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
                "Completed backfill run %s status=%s discovered=%s discovery_skipped=%s cached=%s ingested=%s matched=%s skipped=%s replayed=%s failed=%s cache_failed=%s aggregate_refreshes=%s openfront_rate_limits=%s openfront_retry_after=%s openfront_cooldown_total=%s openfront_cooldown_max=%s",
                run.id,
                run.status,
                run.discovered_count,
                run.discovery_skipped_known_count,
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


async def _execute_probe(
    *,
    start: datetime,
    end: datetime,
    sample_size: int,
    seed: int | None,
    openfront_max_in_flight: int,
    openfront_success_delay_seconds: float,
    openfront_min_rate_limit_cooldown_seconds: float,
) -> OpenFrontProbeSummary:
    with _openfront_profile(
        max_in_flight=openfront_max_in_flight,
        success_delay_seconds=openfront_success_delay_seconds,
        min_rate_limit_cooldown_seconds=openfront_min_rate_limit_cooldown_seconds,
    ):
        config = load_config()
        client = (
            OpenFrontClient(bypass_config=config.openfront)
            if config.openfront is not None
            else OpenFrontClient()
        )
        try:
            return await probe_openfront_profile(
                client,
                start=start,
                end=end,
                sample_size=sample_size,
                seed=seed,
                openfront_max_in_flight=openfront_max_in_flight,
                openfront_success_delay_seconds=openfront_success_delay_seconds,
                openfront_min_rate_limit_cooldown_seconds=openfront_min_rate_limit_cooldown_seconds,
                stop_after_rate_limits=PROBE_STOP_AFTER_RATE_LIMITS,
                stop_on_retry_after_seconds=PROBE_STOP_ON_RETRY_AFTER_SECONDS,
            )
        finally:
            await client.close()


def _add_openfront_profile_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--openfront-max-in-flight",
        type=int,
        default=BACKFILL_DEFAULT_OPENFRONT_MAX_IN_FLIGHT,
    )
    parser.add_argument(
        "--openfront-success-delay-seconds",
        type=float,
        default=BACKFILL_DEFAULT_OPENFRONT_SUCCESS_DELAY_SECONDS,
    )
    parser.add_argument(
        "--openfront-min-rate-limit-cooldown-seconds",
        type=float,
        default=BACKFILL_DEFAULT_OPENFRONT_MIN_RATE_LIMIT_COOLDOWN_SECONDS,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="historical-backfill")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--start", required=True)
    start_parser.add_argument("--end", required=True)
    start_parser.add_argument("--concurrency", type=int, default=4)
    start_parser.add_argument("--refresh-batch-size", type=int, default=100)
    start_parser.add_argument("--progress-every", type=int, default=100)
    _add_openfront_profile_arguments(start_parser)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--run-id", type=int, required=True)

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--run-id", type=int, required=True)
    resume_parser.add_argument("--concurrency", type=int, default=4)
    resume_parser.add_argument("--refresh-batch-size", type=int, default=100)
    resume_parser.add_argument("--progress-every", type=int, default=100)
    _add_openfront_profile_arguments(resume_parser)

    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--run-id", type=int, required=True)
    replay_parser.add_argument("--refresh-batch-size", type=int, default=100)

    probe_parser = subparsers.add_parser("probe-openfront")
    probe_parser.add_argument("--start", required=True)
    probe_parser.add_argument("--end", required=True)
    probe_parser.add_argument("--sample-size", type=int, default=PROBE_DEFAULT_SAMPLE_SIZE)
    probe_parser.add_argument("--seed", type=int)
    _add_openfront_profile_arguments(probe_parser)

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
                openfront_max_in_flight=args.openfront_max_in_flight,
                openfront_success_delay_seconds=args.openfront_success_delay_seconds,
                openfront_min_rate_limit_cooldown_seconds=args.openfront_min_rate_limit_cooldown_seconds,
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
                openfront_max_in_flight=args.openfront_max_in_flight,
                openfront_success_delay_seconds=args.openfront_success_delay_seconds,
                openfront_min_rate_limit_cooldown_seconds=args.openfront_min_rate_limit_cooldown_seconds,
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

    if args.command == "probe-openfront":
        summary = asyncio.run(
            _execute_probe(
                start=_parse_cli_datetime(args.start),
                end=_parse_cli_datetime(args.end),
                sample_size=args.sample_size,
                seed=args.seed,
                openfront_max_in_flight=args.openfront_max_in_flight,
                openfront_success_delay_seconds=args.openfront_success_delay_seconds,
                openfront_min_rate_limit_cooldown_seconds=args.openfront_min_rate_limit_cooldown_seconds,
            )
        )
        print(_probe_summary(summary))
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
                    "deleted_guild_player_daily_snapshots="
                    f"{summary.guild_player_daily_snapshots}",
                    "deleted_guild_daily_benchmarks="
                    f"{summary.guild_daily_benchmarks}",
                    "deleted_guild_weekly_player_scores="
                    f"{summary.guild_weekly_player_scores}",
                    "deleted_guild_recent_game_results="
                    f"{summary.guild_recent_game_results}",
                    "deleted_guild_combo_aggregates="
                    f"{summary.guild_combo_aggregates}",
                    "deleted_guild_combo_members="
                    f"{summary.guild_combo_members}",
                    "deleted_guild_player_badges="
                    f"{summary.guild_player_badges}",
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
