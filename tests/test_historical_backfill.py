import asyncio
import json
from datetime import datetime

from peewee import SqliteDatabase


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


def test_hydrate_backfill_run_refreshes_affected_guilds_in_batches(
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
            refresh_batch_size=10,
        )
    )

    assert refreshed == [guild.id]


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
    assert resumed_run.ingested_count == 2


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


def test_reset_ingested_web_data_clears_ingestion_tables_only(tmp_path):
    from src.data.shared.models import (
        BackfillCursor,
        BackfillGame,
        BackfillRun,
        CachedOpenFrontGame,
        GameParticipant,
        Guild,
        GuildClanTag,
        GuildPlayerAggregate,
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
    assert summary.total_deleted >= 7

    assert BackfillRun.select().count() == 0
    assert BackfillCursor.select().count() == 0
    assert BackfillGame.select().count() == 0
    assert CachedOpenFrontGame.select().count() == 0
    assert ObservedGame.select().count() == 0
    assert GameParticipant.select().count() == 0
    assert GuildPlayerAggregate.select().count() == 0

    assert Guild.select().count() == 1
    assert GuildClanTag.select().count() == 1
    assert SiteUser.select().count() == 1
    assert Player.select().count() == 1
    assert PlayerAlias.select().count() == 1
    assert PlayerLink.select().count() == 1
