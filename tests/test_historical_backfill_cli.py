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
        GuildPlayerAggregate,
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
        cached_count=7,
        ingested_count=7,
        matched_count=3,
        failed_count=2,
        refreshed_guild_count=5,
        skipped_known_count=4,
        replayed_count=6,
        cache_failure_count=1,
    )

    assert backfill_cli.main(["status", "--run-id", str(run.id)]) == 0
    output = capsys.readouterr().out

    assert "status=completed_with_failures" in output
    assert "skipped=4" in output
    assert "replayed=6" in output
    assert "cache_failed=1" in output
    assert "aggregate_refreshes=5" in output
