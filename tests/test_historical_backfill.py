import asyncio
import json
from datetime import datetime

from peewee import InterfaceError, SqliteDatabase


def setup_shared_database(tmp_path):
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema

    database = SqliteDatabase(
        str(tmp_path / "historical-backfill.db"),
        check_same_thread=False,
    )
    shared_database.initialize(database)
    bootstrap_shared_schema(database)
    return database


def test_create_backfill_run_seeds_unique_team_and_ffa_cursors(tmp_path):
    from src.data.shared.models import BackfillCursor
    from src.services.guild_sites import provision_guild_site
    from src.services.historical_backfill import create_backfill_run

    setup_shared_database(tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU", "ALT"],
    )
    provision_guild_site(
        slug="deer",
        subdomain="deer",
        display_name="Deer",
        clan_tags=["ALT", "DEER"],
    )

    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )

    cursors = list(
        BackfillCursor.select()
        .where(BackfillCursor.run == run)
        .order_by(BackfillCursor.source_type, BackfillCursor.source_key)
    )

    assert [(cursor.source_type, cursor.source_key) for cursor in cursors] == [
        ("ffa", "global"),
        ("team", "ALT"),
        ("team", "DEER"),
        ("team", "NU"),
    ]


def test_discover_team_games_enqueues_unique_game_ids_from_clan_sessions(tmp_path):
    from src.data.shared.models import BackfillGame, BackfillRun
    from src.services.guild_sites import provision_guild_site
    from src.services.historical_backfill import create_backfill_run, discover_team_games

    setup_shared_database(tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU", "ALT"],
    )

    class FakeClient:
        async def fetch_clan_sessions(self, clan_tag, start=None, end=None):
            sessions = {
                "NU": [
                    {
                        "gameId": "team-1",
                        "gameStart": "2026-03-01T10:00:00Z",
                    },
                    {
                        "gameId": "shared-game",
                        "gameStart": "2026-03-02T10:00:00Z",
                    },
                ],
                "ALT": [
                    {
                        "gameId": "shared-game",
                        "gameStart": "2026-03-02T10:00:00Z",
                    },
                    {
                        "gameId": "team-2",
                        "gameStart": "2026-03-03T10:00:00Z",
                    },
                ],
            }
            return list(sessions.get(clan_tag, []))

    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )

    discovered = asyncio.run(discover_team_games(FakeClient(), run.id))
    queued = list(
        BackfillGame.select()
        .where(BackfillGame.run == BackfillRun.get_by_id(run.id))
        .order_by(BackfillGame.openfront_game_id)
    )

    assert discovered == 3
    assert [row.openfront_game_id for row in queued] == [
        "shared-game",
        "team-1",
        "team-2",
    ]


def test_discover_ffa_games_filters_to_ffa_and_game_start_range(tmp_path):
    from src.data.shared.models import BackfillGame, BackfillRun
    from src.services.historical_backfill import create_backfill_run, discover_ffa_games

    setup_shared_database(tmp_path)

    class FakeClient:
        async def fetch_public_games(self, start, end, limit=1000):
            return [
                {
                    "game": "ffa-in-range",
                    "mode": "Free For All",
                    "start": "2026-03-02T00:00:00Z",
                },
                {
                    "game": "team-in-range",
                    "mode": "Team",
                    "start": "2026-03-02T12:00:00Z",
                },
                {
                    "game": "ffa-out-of-range",
                    "mode": "Free For All",
                    "start": "2026-02-28T23:59:59Z",
                },
            ]

    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )

    discovered = asyncio.run(discover_ffa_games(FakeClient(), run.id))
    queued = list(
        BackfillGame.select()
        .where(BackfillGame.run == BackfillRun.get_by_id(run.id))
        .order_by(BackfillGame.openfront_game_id)
    )

    assert discovered == 1
    assert [row.openfront_game_id for row in queued] == ["ffa-in-range"]


def test_probe_openfront_profile_stops_after_large_retry_after_without_writing_backfill_data(
    tmp_path,
):
    from src.data.shared.models import (
        BackfillGame,
        BackfillRun,
        CachedOpenFrontGame,
        GameParticipant,
        ObservedGame,
    )
    from src.openfront import OpenFrontError
    from src.services.historical_backfill import probe_openfront_profile

    setup_shared_database(tmp_path)

    class FakeClient:
        async def fetch_public_games(self, start, end, limit=1000):
            return [{"game": "g-1"}, {"game": "g-2"}, {"game": "g-3"}]

        async def fetch_game(self, game_id, include_turns=False, retry_on_429=True):
            assert include_turns is False
            assert retry_on_429 is False
            if game_id == "g-1":
                return {"info": {"gameID": game_id}}
            if game_id == "g-2":
                raise OpenFrontError("rate limited", status=429, retry_after=60.0)
            raise AssertionError(f"probe should have stopped before {game_id}")

    summary = asyncio.run(
        probe_openfront_profile(
            FakeClient(),
            start=datetime(2026, 3, 1),
            end=datetime(2026, 3, 2),
            sample_size=3,
            openfront_max_in_flight=1,
            openfront_success_delay_seconds=0.5,
            openfront_min_rate_limit_cooldown_seconds=1.0,
        )
    )

    assert summary.candidate_count == 3
    assert summary.sampled_count == 3
    assert summary.attempted_count == 2
    assert summary.success_count == 1
    assert summary.rate_limit_count == 1
    assert summary.zero_retry_after_count == 0
    assert summary.other_error_count == 0
    assert summary.retry_after_max == 60.0
    assert summary.stopped_early is True
    assert summary.stop_reason == "retry_after_ge_30s"

    assert BackfillRun.select().count() == 0
    assert BackfillGame.select().count() == 0
    assert CachedOpenFrontGame.select().count() == 0
    assert ObservedGame.select().count() == 0
    assert GameParticipant.select().count() == 0


def test_discover_team_games_skips_known_readable_history_before_queueing(tmp_path):
    from src.data.shared.models import BackfillGame, BackfillRun, CachedOpenFrontGame
    from src.services.guild_sites import provision_guild_site
    from src.services.historical_backfill import create_backfill_run, discover_team_games

    setup_shared_database(tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    previous_run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 2),
    )
    cache = CachedOpenFrontGame.create(
        openfront_game_id="known-team",
        game_type="PUBLIC",
        mode_name="Team",
        payload_json='{"info":{"gameID":"known-team"}}',
        turn_payload_json='{"info":{"gameID":"known-team"},"turns":[]}',
    )
    BackfillGame.create(
        run=previous_run,
        openfront_game_id="known-team",
        source_type="team",
        status="completed",
        cache_entry=cache,
    )

    class FakeClient:
        async def fetch_clan_sessions(self, clan_tag, start=None, end=None):
            return [
                {"gameId": "known-team", "gameStart": "2026-03-01T10:00:00Z"},
                {"gameId": "new-team", "gameStart": "2026-03-01T11:00:00Z"},
            ]

    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 2),
    )

    discovered = asyncio.run(discover_team_games(FakeClient(), run.id))
    run = BackfillRun.get_by_id(run.id)
    queued = list(
        BackfillGame.select()
        .where(BackfillGame.run == run)
        .order_by(BackfillGame.openfront_game_id)
    )

    assert discovered == 1
    assert run.discovered_count == 1
    assert run.discovery_skipped_known_count == 1
    assert [row.openfront_game_id for row in queued] == ["new-team"]


def test_discover_ffa_games_keeps_unreadable_known_cache_eligible_for_queueing(tmp_path):
    from src.data.shared.models import BackfillGame, BackfillRun, CachedOpenFrontGame
    from src.services.historical_backfill import create_backfill_run, discover_ffa_games

    setup_shared_database(tmp_path)

    previous_run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 2),
    )
    cache = CachedOpenFrontGame.create(
        openfront_game_id="repair-ffa",
        game_type="PUBLIC",
        mode_name="Free For All",
        payload_json='{"info":{"gameID":"repair-ffa"}',
    )
    BackfillGame.create(
        run=previous_run,
        openfront_game_id="repair-ffa",
        source_type="ffa",
        status="completed",
        cache_entry=cache,
    )

    class FakeClient:
        async def fetch_public_games(self, start, end, limit=1000):
            return [
                {
                    "game": "repair-ffa",
                    "mode": "Free For All",
                    "start": "2026-03-01T12:00:00Z",
                }
            ]

    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 2),
    )

    discovered = asyncio.run(discover_ffa_games(FakeClient(), run.id))
    run = BackfillRun.get_by_id(run.id)
    queued = list(
        BackfillGame.select()
        .where(BackfillGame.run == run)
        .order_by(BackfillGame.openfront_game_id)
    )

    assert discovered == 1
    assert run.discovered_count == 1
    assert run.discovery_skipped_known_count == 0
    assert [row.openfront_game_id for row in queued] == ["repair-ffa"]


def test_hydrate_backfill_run_caches_payloads_and_ingests_matching_games(tmp_path):
    from src.data.shared.models import (
        BackfillGame,
        BackfillRun,
        CachedOpenFrontGame,
        GameParticipant,
        ObservedGame,
    )
    from src.services.guild_sites import provision_guild_site
    from src.services.historical_backfill import create_backfill_run, hydrate_backfill_run

    setup_shared_database(tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    class FakeClient:
        def __init__(self):
            self.calls = []

        async def fetch_game(self, game_id):
            self.calls.append(game_id)
            if game_id == "matching-game":
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
                    "config": {"gameType": "Public", "gameMode": "Team"},
                    "winner": ["team", "Team 2", "c9"],
                    "players": [
                        {"clientID": "c9", "username": "Enemy", "clanTag": "XYZ"}
                    ],
                }
            }

    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    BackfillGame.create(
        run=run,
        openfront_game_id="matching-game",
        source_type="team",
        status="pending",
    )
    BackfillGame.create(
        run=run,
        openfront_game_id="irrelevant-game",
        source_type="ffa",
        status="pending",
    )

    hydrated = asyncio.run(hydrate_backfill_run(FakeClient(), run.id))
    queued = list(
        BackfillGame.select()
        .where(BackfillGame.run == BackfillRun.get_by_id(run.id))
        .order_by(BackfillGame.openfront_game_id)
    )

    assert hydrated.cached_count == 2
    assert hydrated.ingested_count == 2
    assert hydrated.matched_count == 1
    assert CachedOpenFrontGame.select().count() == 2
    assert ObservedGame.select().count() == 1
    assert GameParticipant.select().count() == 1
    assert [row.status for row in queued] == ["completed", "completed"]


def test_replay_backfill_run_uses_cached_payloads_without_refetching(tmp_path):
    from src.data.shared.models import BackfillGame, CachedOpenFrontGame, ObservedGame
    from src.services.guild_sites import provision_guild_site
    from src.services.historical_backfill import create_backfill_run, replay_backfill_run

    setup_shared_database(tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    cache = CachedOpenFrontGame.create(
        openfront_game_id="cached-game",
        game_type="PUBLIC",
        mode_name="Team",
        started_at=datetime(2026, 3, 2),
        payload_json=json.dumps(
            {
                "info": {
                    "gameID": "cached-game",
                    "config": {"gameType": "Public", "gameMode": "Team"},
                    "winner": ["team", "Team 1", "c1"],
                    "players": [
                        {"clientID": "c1", "username": "[NU] Ace", "clanTag": None}
                    ],
                }
            }
        ),
    )
    BackfillGame.create(
        run=run,
        openfront_game_id="cached-game",
        source_type="team",
        status="pending",
        cache_entry=cache,
    )

    replayed = replay_backfill_run(run.id)

    assert replayed.matched_count == 1
    assert ObservedGame.select().count() == 1


def test_hydrate_backfill_run_refreshes_affected_guilds_after_hydration_completes(
    tmp_path,
    monkeypatch,
):
    from src.data.shared.models import BackfillGame
    from src.services.guild_sites import provision_guild_site
    from src.services import historical_backfill

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    class FakeClient:
        async def fetch_game(self, game_id):
            events.append(f"fetch:{game_id}")
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

    events = []

    def fake_refresh(guild_id):
        events.append(f"refresh:{guild_id}")
        return []

    monkeypatch.setattr(
        historical_backfill,
        "refresh_guild_player_aggregates",
        fake_refresh,
    )

    run = historical_backfill.create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    BackfillGame.create(
        run=run,
        openfront_game_id="game-1",
        source_type="team",
        status="pending",
    )
    BackfillGame.create(
        run=run,
        openfront_game_id="game-2",
        source_type="team",
        status="pending",
    )

    asyncio.run(
        historical_backfill.hydrate_backfill_run(
            FakeClient(),
            run.id,
            refresh_batch_size=1,
            progress_every=1,
        )
    )

    assert events == [
        "fetch:game-1",
        "fetch:game-2",
        f"refresh:{guild.id}",
    ]


def test_hydrate_backfill_run_skips_aggregate_refresh_when_no_guilds_match(
    tmp_path,
    monkeypatch,
):
    from src.data.shared.models import BackfillGame
    from src.services import historical_backfill

    setup_shared_database(tmp_path)

    class FakeClient:
        async def fetch_game(self, game_id):
            return {
                "info": {
                    "gameID": game_id,
                    "config": {"gameType": "Public", "gameMode": "Team"},
                    "winner": ["team", "Team 2", "c9"],
                    "players": [
                        {"clientID": "c9", "username": "Enemy", "clanTag": "XYZ"}
                    ],
                }
            }

    refreshed = []

    def fake_refresh(guild_id):
        refreshed.append(guild_id)
        return []

    monkeypatch.setattr(
        historical_backfill,
        "refresh_guild_player_aggregates",
        fake_refresh,
    )

    run = historical_backfill.create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    BackfillGame.create(
        run=run,
        openfront_game_id="irrelevant-game",
        source_type="team",
        status="pending",
    )

    hydrated = asyncio.run(
        historical_backfill.hydrate_backfill_run(
            FakeClient(),
            run.id,
            refresh_batch_size=1,
            progress_every=1,
        )
    )

    assert hydrated.refreshed_guild_count == 0
    assert refreshed == []


def test_worker_runtime_backfill_and_resume_use_durable_runs(tmp_path):
    from src.apps.worker.app import WorkerRuntime
    from src.data.shared.models import BackfillGame
    from src.services.guild_sites import provision_guild_site
    from src.services.historical_backfill import create_backfill_run

    setup_shared_database(tmp_path)
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
            return []

        async def fetch_game(self, game_id):
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

        async def close(self):
            return None

    worker = WorkerRuntime(client=FakeClient())

    run = asyncio.run(
        worker.backfill(
            start=datetime(2026, 3, 1),
            end=datetime(2026, 3, 3),
        )
    )

    assert run.status == "completed"
    assert run.discovered_count == 1
    assert run.matched_count == 1

    resumed_run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 3),
    )
    BackfillGame.create(
        run=resumed_run,
        openfront_game_id="resume-game",
        source_type="team",
        status="pending",
    )

    resumed_run = asyncio.run(worker.resume_backfill(resumed_run.id))

    assert resumed_run.status == "completed"
    assert resumed_run.ingested_count == 1
    assert resumed_run.discovery_skipped_known_count == 1
    assert resumed_run.skipped_known_count == 0


def test_worker_runtime_backfill_runs_team_and_ffa_discovery_concurrently(tmp_path):
    from src.apps.worker.app import WorkerRuntime
    from src.services.guild_sites import provision_guild_site

    setup_shared_database(tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    class FakeClient:
        def __init__(self):
            self.team_saw_ffa = False
            self.ffa_saw_team = False
            self.team_started = asyncio.Event()
            self.ffa_started = asyncio.Event()

        async def fetch_clan_sessions(self, clan_tag, start=None, end=None):
            self.team_started.set()
            try:
                await asyncio.wait_for(self.ffa_started.wait(), timeout=0.05)
                self.team_saw_ffa = True
            except TimeoutError:
                self.team_saw_ffa = False
            return []

        async def fetch_public_games(self, start, end, limit=1000):
            self.ffa_started.set()
            try:
                await asyncio.wait_for(self.team_started.wait(), timeout=0.05)
                self.ffa_saw_team = True
            except TimeoutError:
                self.ffa_saw_team = False
            return []

        async def close(self):
            return None

    client = FakeClient()
    worker = WorkerRuntime(client=client)

    run = asyncio.run(
        worker.backfill(
            start=datetime(2026, 3, 1),
            end=datetime(2026, 3, 3),
        )
    )

    assert run.status == "completed"
    assert client.team_saw_ffa is True
    assert client.ffa_saw_team is True


def test_hydrate_backfill_run_emits_progress_logs(tmp_path, caplog):
    from src.data.shared.models import BackfillGame
    from src.services.guild_sites import provision_guild_site
    from src.services.historical_backfill import create_backfill_run, hydrate_backfill_run

    setup_shared_database(tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    class FakeClient:
        async def fetch_game(self, game_id):
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

    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 3),
    )
    run.discovery_skipped_known_count = 2
    run.save()
    BackfillGame.create(
        run=run,
        openfront_game_id="log-game",
        source_type="team",
        status="pending",
    )

    with caplog.at_level("INFO"):
        asyncio.run(
            hydrate_backfill_run(
                FakeClient(),
                run.id,
                progress_every=1,
            )
        )

    messages = [record.message for record in caplog.records]
    assert any("hydration_progress" in message for message in messages)
    assert any("hydration_complete" in message for message in messages)
    assert any("discovery_skipped=2" in message for message in messages)
    assert any("skipped=0" in message for message in messages)
    assert any("cache_failed=0" in message for message in messages)
    assert any("aggregate_refreshes=" in message for message in messages)


def test_hydrate_backfill_run_tracks_openfront_rate_limits(tmp_path, caplog):
    from src.core.openfront import OpenFrontRateLimitEvent
    from src.data.shared.models import BackfillGame
    from src.services.historical_backfill import create_backfill_run, hydrate_backfill_run

    setup_shared_database(tmp_path)

    class FakeClient:
        def __init__(self):
            self.on_rate_limit = None

        def set_rate_limit_observer(self, observer):
            previous = self.on_rate_limit
            self.on_rate_limit = observer
            return previous

        async def fetch_game(self, game_id, include_turns=False):
            assert self.on_rate_limit is not None
            self.on_rate_limit(
                OpenFrontRateLimitEvent(
                    status=429,
                    cooldown_seconds=7.0,
                    source="retry-after",
                    url=f"/public/game/{game_id}",
                )
            )
            return {
                "info": {
                    "gameID": game_id,
                    "config": {"gameType": "Public", "gameMode": "Team"},
                    "winner": ["team", "Team 2", "c9"],
                    "players": [
                        {"clientID": "c9", "username": "Enemy", "clanTag": "XYZ"}
                    ],
                }
            }

    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 3),
    )
    BackfillGame.create(
        run=run,
        openfront_game_id="throttled-game",
        source_type="team",
        status="pending",
    )

    with caplog.at_level("WARNING"):
        hydrated = asyncio.run(
            hydrate_backfill_run(
                FakeClient(),
                run.id,
                progress_every=1,
            )
        )

    assert hydrated.openfront_rate_limit_hit_count == 1
    assert hydrated.openfront_retry_after_count == 1
    assert hydrated.openfront_cooldown_seconds_total == 7.0
    assert hydrated.openfront_cooldown_seconds_max == 7.0
    messages = [record.message for record in caplog.records]
    assert any("status=429" in message for message in messages)
    assert any("retry_after=7.0" in message for message in messages)
    assert any("source=retry-after" in message for message in messages)


def test_record_openfront_rate_limit_uses_portable_max_expression(tmp_path):
    from src.core.openfront import OpenFrontRateLimitEvent
    from src.data.shared.models import BackfillRun
    from src.services import historical_backfill

    setup_shared_database(tmp_path)

    query = BackfillRun.update(
        openfront_cooldown_seconds_max=historical_backfill.Case(
            None,
            (
                (
                    BackfillRun.openfront_cooldown_seconds_max < 43.0,
                    43.0,
                ),
            ),
            BackfillRun.openfront_cooldown_seconds_max,
        )
    ).where(BackfillRun.id == 1)
    sql, _params = query.sql()

    assert "CASE" in sql.upper()
    assert "MAX(" not in sql.upper()

    run = BackfillRun.create(
        requested_start=datetime(2026, 3, 1),
        requested_end=datetime(2026, 3, 2),
    )

    historical_backfill._record_openfront_rate_limit(
        run.id,
        OpenFrontRateLimitEvent(
            status=429,
            cooldown_seconds=43.0,
            source="retry-after",
            url="/public/game/test-1",
        ),
    )
    historical_backfill._record_openfront_rate_limit(
        run.id,
        OpenFrontRateLimitEvent(
            status=429,
            cooldown_seconds=11.0,
            source="fallback",
            url="/public/game/test-2",
        ),
    )

    run = BackfillRun.get_by_id(run.id)

    assert run.openfront_rate_limit_hit_count == 2
    assert run.openfront_retry_after_count == 1
    assert run.openfront_cooldown_seconds_total == 54.0
    assert run.openfront_cooldown_seconds_max == 43.0


def test_hydrate_backfill_run_skips_games_completed_in_earlier_runs(tmp_path):
    from src.data.shared.models import BackfillGame, CachedOpenFrontGame
    from src.services.historical_backfill import create_backfill_run, hydrate_backfill_run

    setup_shared_database(tmp_path)

    previous_run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    cache = CachedOpenFrontGame.create(
        openfront_game_id="known-game",
        game_type="PUBLIC",
        mode_name="Team",
        payload_json='{"info":{"gameID":"known-game","config":{"gameType":"Public","gameMode":"Team"},"winner":["team","Team 1","c1"],"players":[{"clientID":"c1","username":"Ace","clanTag":"XYZ"}]}}',
        turn_payload_json='{"info":{"gameID":"known-game","config":{"gameType":"Public","gameMode":"Team"},"winner":["team","Team 1","c1"],"players":[{"clientID":"c1","username":"Ace","clanTag":"XYZ"}]},"turns":[]}',
    )
    BackfillGame.create(
        run=previous_run,
        openfront_game_id="known-game",
        source_type="team",
        status="completed",
        cache_entry=cache,
    )
    current_run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    queued = BackfillGame.create(
        run=current_run,
        openfront_game_id="known-game",
        source_type="team",
        status="pending",
    )

    class FakeClient:
        async def fetch_game(self, game_id):
            raise AssertionError(f"should not fetch {game_id}")

    hydrated = asyncio.run(hydrate_backfill_run(FakeClient(), current_run.id))
    queued = BackfillGame.get_by_id(queued.id)

    assert hydrated.status == "completed"
    assert hydrated.ingested_count == 0
    assert hydrated.skipped_known_count == 1
    assert queued.status == "skipped_known"


def test_hydrate_backfill_run_refreshes_guilds_for_skipped_known_games(tmp_path, monkeypatch):
    from src.data.shared.models import (
        BackfillGame,
        CachedOpenFrontGame,
        GameParticipant,
        ObservedGame,
    )
    from src.services import historical_backfill
    from src.services.guild_sites import provision_guild_site

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )
    observed = ObservedGame.create(
        openfront_game_id="known-game",
        game_type="PUBLIC",
        mode_name="Team",
    )
    GameParticipant.create(
        game=observed,
        guild=guild,
        raw_username="[NU] Ace",
        normalized_username="ace",
        raw_clan_tag="NU",
        effective_clan_tag="NU",
        clan_tag_source="api",
        client_id="c1",
        did_win=1,
    )

    previous_run = historical_backfill.create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    cache = CachedOpenFrontGame.create(
        openfront_game_id="known-game",
        game_type="PUBLIC",
        mode_name="Team",
        payload_json='{"info":{"gameID":"known-game","config":{"gameType":"Public","gameMode":"Team"},"winner":["team","Team 1","c1"],"players":[{"clientID":"c1","username":"[NU] Ace","clanTag":"NU"}]}}',
        turn_payload_json='{"info":{"gameID":"known-game","config":{"gameType":"Public","gameMode":"Team"},"winner":["team","Team 1","c1"],"players":[{"clientID":"c1","username":"[NU] Ace","clanTag":"NU"}]},"turns":[]}',
    )
    BackfillGame.create(
        run=previous_run,
        openfront_game_id="known-game",
        source_type="team",
        status="completed",
        cache_entry=cache,
    )
    current_run = historical_backfill.create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    queued = BackfillGame.create(
        run=current_run,
        openfront_game_id="known-game",
        source_type="team",
        status="pending",
    )

    refreshed = []

    def fake_refresh(guild_id):
        refreshed.append(guild_id)
        return []

    monkeypatch.setattr(
        historical_backfill,
        "refresh_guild_player_aggregates",
        fake_refresh,
    )

    class FakeClient:
        async def fetch_game(self, game_id):
            raise AssertionError(f"should not fetch {game_id}")

    hydrated = asyncio.run(historical_backfill.hydrate_backfill_run(FakeClient(), current_run.id))
    queued = BackfillGame.get_by_id(queued.id)

    assert hydrated.status == "completed"
    assert hydrated.ingested_count == 0
    assert hydrated.skipped_known_count == 1
    assert queued.status == "skipped_known"
    assert refreshed == [guild.id]


def test_hydrate_backfill_run_repairs_invalid_cached_payloads(tmp_path):
    from src.data.shared.models import BackfillGame, CachedOpenFrontGame
    from src.services.guild_sites import provision_guild_site
    from src.services.historical_backfill import create_backfill_run, hydrate_backfill_run

    setup_shared_database(tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    previous_run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    cache = CachedOpenFrontGame.create(
        openfront_game_id="repair-game",
        game_type="PUBLIC",
        mode_name="Team",
        payload_json='{"info":{"gameID":"repair-game"}}',
        turn_payload_json='{"info": {"gameID":"repair-game"}, "turns": [',
    )
    BackfillGame.create(
        run=previous_run,
        openfront_game_id="repair-game",
        source_type="team",
        status="completed",
        cache_entry=cache,
    )
    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    queued = BackfillGame.create(
        run=run,
        openfront_game_id="repair-game",
        source_type="team",
        status="pending",
        cache_entry=cache,
    )

    class FakeClient:
        def __init__(self):
            self.calls = []

        async def fetch_game(self, game_id):
            self.calls.append(game_id)
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

    client = FakeClient()
    hydrated = asyncio.run(hydrate_backfill_run(client, run.id))
    queued = BackfillGame.get_by_id(queued.id)
    cache = CachedOpenFrontGame.get_by_id(cache.id)

    assert client.calls == ["repair-game"]
    assert hydrated.status == "completed"
    assert hydrated.cache_failure_count == 0
    assert queued.status == "completed"
    assert cache.turn_payload_json.endswith('"turns": []}')


def test_replay_backfill_run_reports_unreadable_cache_failures(tmp_path):
    from src.data.shared.models import BackfillGame, CachedOpenFrontGame
    from src.services.historical_backfill import create_backfill_run, replay_backfill_run

    setup_shared_database(tmp_path)

    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    cache = CachedOpenFrontGame.create(
        openfront_game_id="broken-cache",
        game_type="PUBLIC",
        mode_name="Team",
        payload_json='{"info":{"gameID":"broken-cache"}}',
        turn_payload_json='{"info":{"gameID":"broken-cache"}',
    )
    queued = BackfillGame.create(
        run=run,
        openfront_game_id="broken-cache",
        source_type="team",
        status="pending",
        cache_entry=cache,
    )

    replayed = replay_backfill_run(run.id)
    queued = BackfillGame.get_by_id(queued.id)

    assert replayed.status == "completed_with_failures"
    assert replayed.cache_failure_count == 1
    assert queued.status == "cache_failed"
    assert "cache" in queued.last_error.lower()


def test_reset_ingested_web_data_clears_ingestion_and_web_read_model_tables(tmp_path):
    from src.data.shared.models import (
        BackfillCursor,
        BackfillGame,
        BackfillRun,
        CachedOpenFrontGame,
        GameParticipant,
        Guild,
        GuildClanTag,
        GuildComboAggregate,
        GuildComboMember,
        GuildDailyBenchmark,
        GuildPlayerAggregate,
        GuildPlayerBadge,
        GuildPlayerDailySnapshot,
        GuildRecentGameResult,
        GuildWeeklyPlayerScore,
        ObservedGame,
        Player,
        PlayerAlias,
        PlayerLink,
        SiteUser,
    )
    from src.services.historical_backfill import (
        create_backfill_run,
        reset_ingested_web_data,
    )

    setup_shared_database(tmp_path)

    guild = Guild.create(
        slug="north",
        subdomain="north",
        display_name="North Guild",
    )
    GuildClanTag.create(guild=guild, tag_text="NU")
    site_user = SiteUser.create(discord_user_id=42, discord_username="damien")
    player = Player.create(
        openfront_player_id="player-1",
        canonical_username="Ace",
        canonical_normalized_username="ace",
        is_linked=1,
    )
    PlayerAlias.create(
        player=player,
        raw_username="Ace",
        normalized_username="ace",
        source="link",
    )
    PlayerLink.create(site_user=site_user, player=player)
    observed_game = ObservedGame.create(
        openfront_game_id="game-1",
        game_type="PUBLIC",
        mode_name="Team",
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
        player=player,
    )
    GuildPlayerAggregate.create(
        guild=guild,
        player=player,
        normalized_username="ace",
        display_username="Ace",
        win_count=1,
        game_count=1,
    )
    GuildPlayerDailySnapshot.create(
        guild=guild,
        player=player,
        normalized_username="ace",
        display_username="Ace",
        snapshot_date="2026-03-01",
        scope="team",
        score=10.0,
        wins=1,
        games=1,
        win_rate=1.0,
    )
    GuildDailyBenchmark.create(
        guild=guild,
        snapshot_date="2026-03-01",
        scope="team",
        median_score=8.0,
        leader_score=10.0,
    )
    GuildWeeklyPlayerScore.create(
        guild=guild,
        player=player,
        normalized_username="ace",
        display_username="Ace",
        week_start="2026-02-23",
        scope="team",
        score=12.0,
        wins=2,
        games=2,
        win_rate=1.0,
    )
    GuildRecentGameResult.create(
        guild=guild,
        game=observed_game,
        openfront_game_id="game-1",
        ended_at=datetime(2026, 3, 1, 12, 0, 0),
        mode="Team",
        result="win",
        map_name="World",
        format_label="Duos",
        team_distribution="2 teams of 2 players",
        replay_link="https://openfront.io/w0/game/game-1",
        map_thumbnail_url="https://openfront.io/maps/world/thumbnail.webp",
        guild_team_players_json='[{"display_username":"Ace"}]',
        winner_players_json='{"guild":[{"display_username":"Ace"}],"other":[]}',
    )
    combo = GuildComboAggregate.create(
        guild=guild,
        format_slug="duo",
        roster_key="ace|bolt",
        games_together=1,
        wins_together=1,
        win_rate=1.0,
        is_confirmed=0,
    )
    GuildComboMember.create(
        combo=combo,
        player=player,
        normalized_username="ace",
        display_username="Ace",
        slot_index=0,
    )
    GuildPlayerBadge.create(
        guild=guild,
        player=player,
        normalized_username="ace",
        badge_code="field-marshal",
        badge_level="bronze",
        earned_at=datetime(2026, 3, 1, 12, 0, 0),
    )
    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
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
        cache_entry=cache,
    )

    assert BackfillCursor.select().count() > 0

    summary = reset_ingested_web_data()

    assert summary.backfill_runs == 1
    assert summary.backfill_cursors >= 1
    assert summary.backfill_games == 1
    assert summary.cached_openfront_games == 1
    assert summary.observed_games == 1
    assert summary.game_participants == 1
    assert summary.guild_player_aggregates == 1
    assert summary.guild_player_daily_snapshots == 1
    assert summary.guild_daily_benchmarks == 1
    assert summary.guild_weekly_player_scores == 1
    assert summary.guild_recent_game_results == 1
    assert summary.guild_combo_aggregates == 1
    assert summary.guild_combo_members == 1
    assert summary.guild_player_badges == 1
    assert summary.total_deleted >= 14

    assert BackfillRun.select().count() == 0
    assert BackfillCursor.select().count() == 0
    assert BackfillGame.select().count() == 0
    assert CachedOpenFrontGame.select().count() == 0
    assert ObservedGame.select().count() == 0
    assert GameParticipant.select().count() == 0
    assert GuildPlayerAggregate.select().count() == 0
    assert GuildPlayerDailySnapshot.select().count() == 0
    assert GuildDailyBenchmark.select().count() == 0
    assert GuildWeeklyPlayerScore.select().count() == 0
    assert GuildRecentGameResult.select().count() == 0
    assert GuildComboAggregate.select().count() == 0
    assert GuildComboMember.select().count() == 0
    assert GuildPlayerBadge.select().count() == 0

    assert Guild.select().count() == 1
    assert GuildClanTag.select().count() == 1
    assert SiteUser.select().count() == 1
    assert Player.select().count() == 1
    assert PlayerAlias.select().count() == 1
    assert PlayerLink.select().count() == 1


def test_hydrate_backfill_run_avoids_reloading_each_backfill_row(
    tmp_path, monkeypatch
):
    from src.data.shared.models import BackfillGame
    from src.services.historical_backfill import create_backfill_run, hydrate_backfill_run

    setup_shared_database(tmp_path)

    run = create_backfill_run(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 5),
    )
    queued = BackfillGame.create(
        run=run,
        openfront_game_id="db-drop-game",
        source_type="team",
        status="pending",
    )

    class FakeClient:
        async def fetch_game(self, game_id, include_turns=False):
            return {
                "info": {
                    "gameID": game_id,
                    "config": {"gameType": "Public", "gameMode": "Team"},
                    "winner": ["team", "Team 2", "c9"],
                    "players": [
                        {"clientID": "c9", "username": "Enemy", "clanTag": "XYZ"}
                    ],
                }
            }

    def fail_get_by_id(cls, pk):
        raise AssertionError(f"unexpected BackfillGame.get_by_id({pk})")

    monkeypatch.setattr(BackfillGame, "get_by_id", classmethod(fail_get_by_id))

    hydrated = asyncio.run(
        hydrate_backfill_run(
            FakeClient(),
            run.id,
            progress_every=1,
        )
    )

    queued = BackfillGame.select().where(BackfillGame.id == queued.id).get()

    assert hydrated.status == "completed"
    assert hydrated.failed_count == 0
    assert queued.status == "completed"
