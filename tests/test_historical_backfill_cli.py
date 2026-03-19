import os

from peewee import SqliteDatabase


def patch_backfill_cli_runtime(monkeypatch, tmp_path):
    from src.core.config import BotConfig, MariaDBConfig
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema
    from src.apps.cli import backfill as backfill_cli

    database = SqliteDatabase(
        str(tmp_path / "historical-backfill-cli.db"),
        check_same_thread=False,
    )

    def fake_load_config(path=None):
        return BotConfig(
            token="test-token",
            log_level="INFO",
            central_database_path="central.db",
            sync_interval_hours=24,
            results_lobby_poll_seconds=2,
            mariadb=MariaDBConfig(
                database="openfront",
                user="openfront",
                password="change-me",
            ),
        )

    def fake_init_shared_database(_config, *, connect=True):
        shared_database.initialize(database)
        bootstrap_shared_schema(database)
        if connect:
            database.connect(reuse_if_open=True)
        return database

    monkeypatch.setattr(backfill_cli, "load_config", fake_load_config)
    monkeypatch.setattr(backfill_cli, "init_shared_database", fake_init_shared_database)
    backfill_cli._bootstrap_database()
    return backfill_cli


def test_historical_backfill_cli_runs_start_status_resume_and_replay(
    monkeypatch,
    tmp_path,
    capsys,
):
    from src.data.shared.models import BackfillGame, CachedOpenFrontGame
    from src.services.guild_sites import provision_guild_site
    from src.services.historical_backfill import create_backfill_run

    backfill_cli = patch_backfill_cli_runtime(monkeypatch, tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    class FakeClient:
        async def fetch_clan_sessions(self, clan_tag, start=None, end=None):
            return [{"gameId": "team-1", "gameStart": "2026-03-01T10:00:00Z"}]

        async def fetch_public_games(self, start, end, limit=1000):
            return [
                {
                    "game": "ffa-1",
                    "mode": "Free For All",
                    "start": "2026-03-02T10:00:00Z",
                }
            ]

        async def fetch_game(self, game_id):
            if game_id == "team-1":
                return {
                    "info": {
                        "gameID": game_id,
                        "config": {"gameType": "Public", "gameMode": "Team"},
                        "winner": ["team", "Team 1", "c1"],
                        "players": [
                            {"clientID": "c1", "username": "[NU] Ace", "clanTag": None}
                        ],
                    }
                }
            return {
                "info": {
                    "gameID": game_id,
                    "config": {"gameType": "Public", "gameMode": "Free For All"},
                    "winner": ["player", "c1"],
                    "players": [
                        {"clientID": "c1", "username": "[NU] Ace", "clanTag": None}
                    ],
                }
            }

        async def close(self):
            return None

    monkeypatch.setattr(backfill_cli, "OpenFrontClient", lambda: FakeClient())

    assert (
        backfill_cli.main(["start", "--start", "2026-03-01", "--end", "2026-03-03"])
        == 0
    )
    start_output = capsys.readouterr().out
    assert "run_id=1" in start_output
    assert "status=completed" in start_output

    assert backfill_cli.main(["status", "--run-id", "1"]) == 0
    status_output = capsys.readouterr().out
    assert "discovered=2" in status_output
    assert "cursor source=ffa" in status_output
    assert "cursor source=team" in status_output

    resumed_run = create_backfill_run(
        start=backfill_cli._parse_cli_datetime("2026-03-01"),
        end=backfill_cli._parse_cli_datetime("2026-03-03"),
    )
    BackfillGame.create(
        run=resumed_run,
        openfront_game_id="resume-game",
        source_type="team",
        status="pending",
    )

    assert backfill_cli.main(["resume", "--run-id", str(resumed_run.id)]) == 0
    resume_output = capsys.readouterr().out
    assert f"run_id={resumed_run.id}" in resume_output
    assert "status=completed" in resume_output

    replay_run = create_backfill_run(
        start=backfill_cli._parse_cli_datetime("2026-03-01"),
        end=backfill_cli._parse_cli_datetime("2026-03-03"),
    )
    cache = CachedOpenFrontGame.create(
        openfront_game_id="cached-game",
        game_type="PUBLIC",
        mode_name="Team",
        payload_json='{"info":{"gameID":"cached-game","config":{"gameType":"Public","gameMode":"Team"},"winner":["team","Team 1","c1"],"players":[{"clientID":"c1","username":"[NU] Ace","clanTag":null}]}}',
    )
    BackfillGame.create(
        run=replay_run,
        openfront_game_id="cached-game",
        source_type="team",
        status="pending",
        cache_entry=cache,
    )

    assert backfill_cli.main(["replay", "--run-id", str(replay_run.id)]) == 0
    replay_output = capsys.readouterr().out
    assert f"run_id={replay_run.id}" in replay_output
    assert "matched=1" in replay_output


def test_historical_backfill_cli_reports_invalid_inputs(monkeypatch, tmp_path, capsys):
    backfill_cli = patch_backfill_cli_runtime(monkeypatch, tmp_path)

    assert (
        backfill_cli.main(["start", "--start", "2026-03-03", "--end", "2026-03-01"])
        == 1
    )
    date_error = capsys.readouterr().err
    assert "earlier than start" in date_error

    assert backfill_cli.main(["status", "--run-id", "999"]) == 1
    missing_error = capsys.readouterr().err
    assert "not found" in missing_error.lower()


def test_historical_backfill_cli_can_reset_ingested_web_data(
    monkeypatch,
    tmp_path,
    capsys,
):
    from src.data.shared.models import (
        BackfillGame,
        CachedOpenFrontGame,
        GameParticipant,
        GuildDailyBenchmark,
        GuildPlayerAggregate,
        GuildRecentGameResult,
        ObservedGame,
    )
    from src.services.guild_sites import provision_guild_site
    from src.services.historical_backfill import create_backfill_run

    backfill_cli = patch_backfill_cli_runtime(monkeypatch, tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )
    observed_game = ObservedGame.create(
        openfront_game_id="game-1",
        game_type="PUBLIC",
    )
    GameParticipant.create(
        game=observed_game,
        guild=guild,
        raw_username="Ace",
        normalized_username="ace",
        raw_clan_tag="NU",
        effective_clan_tag="NU",
        clan_tag_source="api",
        client_id="client-1",
        did_win=1,
    )
    GuildPlayerAggregate.create(
        guild=guild,
        normalized_username="ace",
        display_username="Ace",
        win_count=1,
        game_count=1,
    )
    GuildDailyBenchmark.create(
        guild=guild,
        snapshot_date="2026-03-01",
        scope="team",
        median_score=8.0,
        leader_score=10.0,
    )
    GuildRecentGameResult.create(
        guild=guild,
        game=observed_game,
        openfront_game_id="game-1",
        mode="Team",
        result="win",
        format_label="Duos",
        replay_link="https://openfront.io/w0/game/game-1",
    )
    run = create_backfill_run(
        start=backfill_cli._parse_cli_datetime("2026-03-01"),
        end=backfill_cli._parse_cli_datetime("2026-03-03"),
    )
    cache = CachedOpenFrontGame.create(
        openfront_game_id="cached-game",
        game_type="PUBLIC",
        mode_name="Team",
        payload_json='{"info":{"gameID":"cached-game"}}',
    )
    BackfillGame.create(
        run=run,
        openfront_game_id="cached-game",
        source_type="team",
        status="pending",
        cache_entry=cache,
    )

    assert backfill_cli.main(["reset-data"]) == 1
    confirmation_error = capsys.readouterr().err
    assert "confirmation" in confirmation_error.lower()

    assert backfill_cli.main(["reset-data", "--confirm"]) == 0
    reset_output = capsys.readouterr().out
    assert "deleted_backfill_runs=1" in reset_output
    assert "deleted_observed_games=1" in reset_output
    assert "deleted_guild_player_aggregates=1" in reset_output
    assert "deleted_guild_daily_benchmarks=1" in reset_output
    assert "deleted_guild_recent_game_results=1" in reset_output


def test_historical_backfill_cli_start_reports_openfront_rate_limit_counters(
    monkeypatch,
    tmp_path,
    capsys,
):
    from src.core.openfront import OpenFrontRateLimitEvent
    from src.services.guild_sites import provision_guild_site

    backfill_cli = patch_backfill_cli_runtime(monkeypatch, tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    class FakeClient:
        def __init__(self):
            self._observer = None

        def set_rate_limit_observer(self, observer):
            previous = self._observer
            self._observer = observer
            return previous

        async def fetch_clan_sessions(self, clan_tag, start=None, end=None):
            return [{"gameId": "team-1", "gameStart": "2026-03-01T10:00:00Z"}]

        async def fetch_public_games(self, start, end, limit=1000):
            return []

        async def fetch_game(self, game_id, include_turns=False):
            assert self._observer is not None
            self._observer(
                OpenFrontRateLimitEvent(
                    status=429,
                    cooldown_seconds=4.0,
                    source="retry-after",
                    url=f"/public/game/{game_id}",
                )
            )
            return {
                "info": {
                    "gameID": game_id,
                    "config": {"gameType": "Public", "gameMode": "Team"},
                    "winner": ["team", "Team 1", "c1"],
                    "players": [
                        {"clientID": "c1", "username": "[NU] Ace", "clanTag": None}
                    ],
                },
                "turns": [],
            }

        async def close(self):
            return None

    monkeypatch.setattr(backfill_cli, "OpenFrontClient", lambda: FakeClient())

    assert (
        backfill_cli.main(["start", "--start", "2026-03-01", "--end", "2026-03-03"])
        == 0
    )
    output = capsys.readouterr().out

    assert "status=completed" in output
    assert "openfront_rate_limits=1" in output
    assert "openfront_retry_after=1" in output
    assert "openfront_cooldown_total=4.0" in output
    assert "openfront_cooldown_max=4.0" in output


def test_historical_backfill_cli_status_reports_overlap_and_cache_counters(
    monkeypatch,
    tmp_path,
    capsys,
):
    from src.data.shared.models import BackfillRun

    backfill_cli = patch_backfill_cli_runtime(monkeypatch, tmp_path)
    run = BackfillRun.create(
        requested_start=backfill_cli._parse_cli_datetime("2026-03-01"),
        requested_end=backfill_cli._parse_cli_datetime("2026-03-03"),
        status="completed_with_failures",
        discovered_count=12,
        discovery_skipped_known_count=5,
        cached_count=7,
        ingested_count=7,
        matched_count=3,
        failed_count=2,
        refreshed_guild_count=5,
        skipped_known_count=4,
        replayed_count=6,
        cache_failure_count=1,
        openfront_rate_limit_hit_count=3,
        openfront_retry_after_count=2,
        openfront_cooldown_seconds_total=15.5,
        openfront_cooldown_seconds_max=9.0,
    )

    assert backfill_cli.main(["status", "--run-id", str(run.id)]) == 0
    output = capsys.readouterr().out

    assert "status=completed_with_failures" in output
    assert "discovery_skipped=5" in output
    assert "skipped=4" in output
    assert "replayed=6" in output
    assert "cache_failed=1" in output
    assert "aggregate_refreshes=5" in output
    assert "openfront_rate_limits=3" in output
    assert "openfront_retry_after=2" in output
    assert "openfront_cooldown_total=15.5" in output
    assert "openfront_cooldown_max=9.0" in output


def test_historical_backfill_cli_start_uses_safe_openfront_profile_defaults(
    monkeypatch,
    tmp_path,
    capsys,
):
    from src.services.guild_sites import provision_guild_site

    backfill_cli = patch_backfill_cli_runtime(monkeypatch, tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )
    seen_profiles = []

    class FakeClient:
        async def fetch_clan_sessions(self, clan_tag, start=None, end=None):
            return [{"gameId": "team-1", "gameStart": "2026-03-01T10:00:00Z"}]

        async def fetch_public_games(self, start, end, limit=1000):
            return []

        async def fetch_game(self, game_id, include_turns=False, retry_on_429=True):
            seen_profiles.append(
                (
                    os.environ.get("OPENFRONT_MAX_IN_FLIGHT"),
                    os.environ.get("OPENFRONT_SUCCESS_DELAY_SECONDS"),
                    os.environ.get("OPENFRONT_MIN_RATE_LIMIT_COOLDOWN_SECONDS"),
                )
            )
            return {
                "info": {
                    "gameID": game_id,
                    "config": {"gameType": "Public", "gameMode": "Team"},
                    "winner": ["team", "Team 1", "c1"],
                    "players": [
                        {"clientID": "c1", "username": "[NU] Ace", "clanTag": None}
                    ],
                },
                "turns": [],
            }

        async def close(self):
            return None

    monkeypatch.setattr(backfill_cli, "OpenFrontClient", lambda: FakeClient())

    assert (
        backfill_cli.main(["start", "--start", "2026-03-01", "--end", "2026-03-03"])
        == 0
    )
    _output = capsys.readouterr().out

    assert seen_profiles
    assert seen_profiles[0] == ("1", "2.2", "2.2")


def test_historical_backfill_cli_resume_accepts_openfront_profile_overrides(
    monkeypatch,
    tmp_path,
    capsys,
):
    from src.data.shared.models import BackfillRun

    backfill_cli = patch_backfill_cli_runtime(monkeypatch, tmp_path)
    run = BackfillRun.create(
        requested_start=backfill_cli._parse_cli_datetime("2026-03-01"),
        requested_end=backfill_cli._parse_cli_datetime("2026-03-03"),
        status="pending",
    )
    captured = {}

    async def fake_execute_run(
        run_id,
        *,
        concurrency,
        refresh_batch_size,
        progress_every,
        openfront_max_in_flight,
        openfront_success_delay_seconds,
        openfront_min_rate_limit_cooldown_seconds,
    ):
        captured.update(
            run_id=run_id,
            concurrency=concurrency,
            refresh_batch_size=refresh_batch_size,
            progress_every=progress_every,
            openfront_max_in_flight=openfront_max_in_flight,
            openfront_success_delay_seconds=openfront_success_delay_seconds,
            openfront_min_rate_limit_cooldown_seconds=openfront_min_rate_limit_cooldown_seconds,
        )
        run.status = "completed"
        run.save()
        return run

    monkeypatch.setattr(backfill_cli, "_execute_run", fake_execute_run)

    assert (
        backfill_cli.main(
            [
                "resume",
                "--run-id",
                str(run.id),
                "--openfront-max-in-flight",
                "2",
                "--openfront-success-delay-seconds",
                "1.5",
                "--openfront-min-rate-limit-cooldown-seconds",
                "2.0",
            ]
        )
        == 0
    )
    _output = capsys.readouterr().out

    assert captured["run_id"] == run.id
    assert captured["openfront_max_in_flight"] == 2
    assert captured["openfront_success_delay_seconds"] == 1.5
    assert captured["openfront_min_rate_limit_cooldown_seconds"] == 2.0


def test_historical_backfill_cli_probe_openfront_reports_summary_without_backfill_writes(
    monkeypatch,
    tmp_path,
    capsys,
):
    from src.data.shared.models import BackfillGame, BackfillRun, CachedOpenFrontGame
    from src.services.historical_backfill import OpenFrontProbeSummary

    backfill_cli = patch_backfill_cli_runtime(monkeypatch, tmp_path)
    captured = {}

    async def fake_probe_openfront_profile(
        client,
        *,
        start,
        end,
        sample_size,
        seed,
        openfront_max_in_flight,
        openfront_success_delay_seconds,
        openfront_min_rate_limit_cooldown_seconds,
        stop_after_rate_limits,
        stop_on_retry_after_seconds,
    ):
        captured.update(
            sample_size=sample_size,
            seed=seed,
            openfront_max_in_flight=openfront_max_in_flight,
            openfront_success_delay_seconds=openfront_success_delay_seconds,
            openfront_min_rate_limit_cooldown_seconds=openfront_min_rate_limit_cooldown_seconds,
            stop_after_rate_limits=stop_after_rate_limits,
            stop_on_retry_after_seconds=stop_on_retry_after_seconds,
        )
        return OpenFrontProbeSummary(
            candidate_count=120,
            sampled_count=25,
            attempted_count=7,
            success_count=5,
            rate_limit_count=2,
            zero_retry_after_count=1,
            other_error_count=0,
            retry_after_max=60.0,
            retry_after_distribution={"0s": 1, ">=30s": 1},
            latency_p50_seconds=0.4,
            latency_p95_seconds=0.8,
            throughput_per_second=2.5,
            openfront_max_in_flight=openfront_max_in_flight,
            openfront_success_delay_seconds=openfront_success_delay_seconds,
            openfront_min_rate_limit_cooldown_seconds=openfront_min_rate_limit_cooldown_seconds,
            stopped_early=True,
            stop_reason="retry_after_ge_30s",
        )

    class FakeClient:
        async def close(self):
            return None

    monkeypatch.setattr(backfill_cli, "OpenFrontClient", lambda: FakeClient())
    monkeypatch.setattr(backfill_cli, "probe_openfront_profile", fake_probe_openfront_profile)

    assert (
        backfill_cli.main(
            [
                "probe-openfront",
                "--start",
                "2026-03-01",
                "--end",
                "2026-03-03",
                "--sample-size",
                "25",
                "--seed",
                "7",
                "--openfront-max-in-flight",
                "2",
                "--openfront-success-delay-seconds",
                "1.5",
                "--openfront-min-rate-limit-cooldown-seconds",
                "2.0",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out

    assert "attempted=7" in output
    assert "rate_limits=2" in output
    assert "retry_after_distribution=0s:1,>=30s:1" in output
    assert captured["sample_size"] == 25
    assert captured["seed"] == 7
    assert captured["openfront_max_in_flight"] == 2
    assert captured["openfront_success_delay_seconds"] == 1.5
    assert captured["openfront_min_rate_limit_cooldown_seconds"] == 2.0
    assert BackfillRun.select().count() == 0
    assert BackfillGame.select().count() == 0
    assert CachedOpenFrontGame.select().count() == 0
