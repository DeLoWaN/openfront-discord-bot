from datetime import datetime, timezone

from peewee import SqliteDatabase


def setup_shared_database(tmp_path):
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema

    database = SqliteDatabase(
        str(tmp_path / "weekly-rankings.db"),
        check_same_thread=False,
    )
    shared_database.initialize(database)
    bootstrap_shared_schema(database)
    return database


def _epoch_millis(value: datetime) -> int:
    return int(value.replace(tzinfo=timezone.utc).timestamp() * 1000)


def test_week_start_uses_monday_midnight_utc():
    from src.services.guild_weekly_rankings import utc_week_start

    assert utc_week_start(datetime(2026, 3, 17, 15, 42, 10)) == datetime(
        2026, 3, 16, 0, 0, 0
    )
    assert utc_week_start(datetime(2026, 3, 22, 23, 59, 59)) == datetime(
        2026, 3, 16, 0, 0, 0
    )


def test_openfront_replay_link_uses_prod_worker_path():
    from src.services.openfront_links import build_openfront_replay_link

    assert build_openfront_replay_link("fP9C9Yuv") == "https://openfront.io/w17/game/fP9C9Yuv"


def test_collect_valid_combo_events_filters_non_spawned_overflow_players(tmp_path):
    from src.services.guild_combo_service import collect_valid_combo_events
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import ingest_game_payload

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North Guild",
        clan_tags=["NU"],
    )

    ingest_game_payload(
        {
            "info": {
                "gameID": "overflow-duo",
                "config": {
                    "gameType": "Public",
                    "gameMode": "Team",
                    "gameMap": "Europe",
                    "playerTeams": "Duos",
                    "maxPlayers": 12,
                },
                "numTeams": 6,
                "totalPlayerCount": 12,
                "start": _epoch_millis(datetime(2026, 3, 16, 10, 0, 0)),
                "end": _epoch_millis(datetime(2026, 3, 16, 10, 12, 0)),
                "duration": 720,
                "winner": ["team", "Team 1", "c1", "c2"],
                "players": [
                    {
                        "clientID": "c1",
                        "username": "[NU] Cedar",
                        "clanTag": "NU",
                        "stats": {"gold": ["25000"], "attacks": ["1000"], "conquests": ["1", "0", "0"]},
                    },
                    {
                        "clientID": "c2",
                        "username": "[NU] Drift",
                        "clanTag": "NU",
                        "stats": {"gold": ["22000"], "attacks": ["900"], "conquests": ["1", "0", "0"]},
                    },
                    {
                        "clientID": "c3",
                        "username": "[NU] Ghost",
                        "clanTag": "NU",
                        "stats": {"gold": ["0"], "attacks": ["0"], "conquests": ["0", "0", "0"]},
                    },
                    {"clientID": "e1", "username": "Enemy1", "clanTag": "ZZ"},
                    {"clientID": "e2", "username": "Enemy2", "clanTag": "ZZ"},
                ],
            },
            "turns": [
                {
                    "intents": [
                        {"clientID": "c1", "type": "attack", "troops": 1200},
                        {"clientID": "c2", "type": "attack", "troops": 900},
                    ]
                }
            ],
        }
    )

    events = collect_valid_combo_events(guild)

    assert any(event.roster_key == "cedar|drift" for event in events)
