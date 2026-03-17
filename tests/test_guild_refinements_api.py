from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from peewee import SqliteDatabase


def _epoch_millis(value: datetime) -> int:
    return int(value.replace(tzinfo=timezone.utc).timestamp() * 1000)


def _week_start(reference: datetime) -> datetime:
    return (reference - timedelta(days=reference.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def setup_client(tmp_path):
    from src.apps.web.app import create_app
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import ingest_game_payload

    database = SqliteDatabase(
        str(tmp_path / "guild-refinements.db"),
        check_same_thread=False,
    )
    shared_database.initialize(database)
    bootstrap_shared_schema(database)

    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North Guild",
        clan_tags=["NU"],
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    current_week = _week_start(now)
    previous_week = current_week - timedelta(days=7)

    def ingest(payload):
        ingest_game_payload(payload)

    team_payloads = [
        ("duo-win-1", previous_week + timedelta(days=1, hours=2), True),
        ("duo-win-2", previous_week + timedelta(days=2, hours=2), True),
        ("duo-win-3", previous_week + timedelta(days=3, hours=2), True),
        ("duo-win-4", current_week + timedelta(hours=10), True),
        ("duo-loss-5", current_week + timedelta(days=1, hours=10), False),
    ]
    for game_id, ended_at, did_win in team_payloads:
        winner = ["team", "Team 1", "a1", "a2"] if did_win else ["team", "Team 2", "x1", "x2"]
        players = [
            {
                "clientID": "a1",
                "username": "[NU] Ace",
                "clanTag": "NU",
                "stats": {"gold": ["25000"], "attacks": ["1200"], "conquests": ["1", "0", "0"]},
            },
            {
                "clientID": "a2",
                "username": "[NU] Bolt",
                "clanTag": "NU",
                "stats": {"gold": ["22000"], "attacks": ["950"], "conquests": ["1", "0", "0"]},
            },
            {"clientID": "x1", "username": "Enemy5", "clanTag": "ZZ"},
            {"clientID": "x2", "username": "Enemy6", "clanTag": "ZZ"},
        ]
        ingest(
            {
                "info": {
                    "gameID": game_id,
                    "config": {
                        "gameType": "Public",
                        "gameMode": "Team",
                        "gameMap": "Europe" if did_win else "Africa",
                        "playerTeams": "Duos",
                        "maxPlayers": 12,
                    },
                    "numTeams": 6,
                    "totalPlayerCount": 12,
                    "start": _epoch_millis(ended_at - timedelta(minutes=12)),
                    "end": _epoch_millis(ended_at),
                    "duration": 720,
                    "winner": winner,
                    "players": players,
                },
                "turns": [
                    {
                        "intents": [
                            {"clientID": "a1", "type": "attack", "troops": 1200},
                            {"clientID": "a2", "type": "attack", "troops": 950},
                        ]
                    }
                ],
            }
        )

    ingest(
        {
            "info": {
                "gameID": "overflow-duo",
                "config": {
                    "gameType": "Public",
                    "gameMode": "Team",
                    "gameMap": "World",
                    "playerTeams": "Duos",
                    "maxPlayers": 12,
                },
                "numTeams": 6,
                "totalPlayerCount": 12,
                "start": _epoch_millis(current_week + timedelta(days=2, hours=11)),
                "end": _epoch_millis(current_week + timedelta(days=2, hours=11, minutes=12)),
                "duration": 720,
                "winner": ["team", "Team 1", "c1", "c2"],
                "players": [
                    {
                        "clientID": "c1",
                        "username": "[NU] Cedar",
                        "clanTag": "NU",
                        "stats": {"gold": ["25000"], "attacks": ["1200"], "conquests": ["1", "0", "0"]},
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
                        {"clientID": "c1", "type": "donate_troops", "troops": 500},
                        {"clientID": "c2", "type": "attack", "troops": 600},
                    ]
                }
            ],
        }
    )

    ingest(
        {
            "info": {
                "gameID": "ffa-win-1",
                "config": {
                    "gameType": "Public",
                    "gameMode": "Free For All",
                    "gameMap": "Oceania",
                },
                "totalPlayerCount": 12,
                "start": _epoch_millis(current_week + timedelta(days=3, hours=14)),
                "end": _epoch_millis(current_week + timedelta(days=3, hours=14, minutes=15)),
                "duration": 900,
                "winner": ["player", "h1"],
                "players": [
                    {"clientID": "h1", "username": "[NU] Ace", "clanTag": "NU"},
                    {"clientID": "h2", "username": "Enemy7", "clanTag": "ZZ"},
                ],
            }
        }
    )

    return guild, TestClient(create_app())


def test_refined_engagement_apis_expose_rosters_games_profiles_and_weekly(tmp_path):
    guild, client = setup_client(tmp_path)
    host = {"host": f"{guild.subdomain}.example.test"}

    home = client.get("/api/home", headers=host)
    rosters = client.get("/api/rosters/duo", headers=host)
    combos_alias = client.get("/api/combos/duo", headers=host)
    recent_games = client.get("/api/results/recent", headers=host)
    profile = client.get("/api/players/ace", headers=host)
    ghost_profile = client.get("/api/players/ghost", headers=host)
    timeseries = client.get("/api/players/ace/timeseries", headers=host)
    ghost_timeseries = client.get("/api/players/ghost/timeseries", headers=host)
    weekly = client.get("/api/weekly?scope=team&weeks=6", headers=host)

    assert home.status_code == 200
    assert home.json()["competitive_pulse"]["leaders"][0]["rank"] == 1
    assert home.json()["latest_games_preview"][0]["result"] in {"win", "loss"}
    assert "team_distribution" in home.json()["latest_games_preview"][0]
    assert home.json()["weekly_pulse"]["scope"] == "team"
    assert len(home.json()["competitive_pulse"]["support_spotlight"]) == 1
    assert all(
        row["support_bonus"] > 0
        for row in home.json()["competitive_pulse"]["support_spotlight"]
    )

    assert rosters.status_code == 200
    assert rosters.json()["confirmed"][0]["roster_key"] == "ace|bolt"
    assert rosters.json()["pending"][0]["roster_key"] == "cedar|drift"
    assert combos_alias.status_code == 200

    assert recent_games.status_code == 200
    assert {item["result"] for item in recent_games.json()["items"]} >= {"win", "loss"}
    assert recent_games.json()["items"][0]["replay_link"].startswith("https://openfront.io/w")
    assert any(
        "teams of" in item["team_distribution"] for item in recent_games.json()["items"]
    )
    assert "winner_players" in recent_games.json()["items"][0]
    assert recent_games.json()["items"][0]["map_thumbnail_url"] is not None

    assert profile.status_code == 200
    assert profile.json()["badge_catalog"]
    assert profile.json()["weekly_summary"]["scope"] == "team"
    assert profile.json()["sections"]["team"]["score_note_label"] == "Wins / Games"
    assert ghost_profile.status_code == 200
    assert ghost_profile.json()["sections"]["team"]["games"] == 1
    assert ghost_profile.json()["sections"]["team"]["score"] == 0
    assert ghost_profile.json()["weekly_summary"]["rank"] is None

    assert timeseries.status_code == 200
    assert timeseries.json()["daily_progression"]
    assert timeseries.json()["daily_benchmarks"]
    assert timeseries.json()["recent_performance"]
    assert timeseries.json()["weekly_scores"]
    assert ghost_timeseries.status_code == 200
    assert ghost_timeseries.json()["weekly_scores"][-1]["team"] == 0
    assert ghost_timeseries.json()["weekly_scores"][-1]["support"] == 0

    assert weekly.status_code == 200
    assert weekly.json()["scope"] == "team"
    assert weekly.json()["rows"]
    assert "movement" in weekly.json()["rows"][0]
    assert all(row["score"] > 0 for row in weekly.json()["rows"])
    assert all(row["normalized_username"] != "ghost" for row in weekly.json()["rows"])


def test_public_spa_routes_expose_canonical_rosters_games_and_weekly_pages(tmp_path):
    guild, client = setup_client(tmp_path)
    host = {"host": f"{guild.subdomain}.example.test"}

    home = client.get("/", headers=host)
    rosters = client.get("/rosters", headers=host)
    games = client.get("/games", headers=host)
    weekly = client.get("/weekly", headers=host)
    combos_alias = client.get("/combos", headers=host)
    wins_alias = client.get("/wins", headers=host)

    assert home.status_code == 200
    assert "/rosters" in home.text
    assert "/games" in home.text
    assert "/weekly" in home.text
    assert rosters.status_code == 200
    assert games.status_code == 200
    assert weekly.status_code == 200
    assert combos_alias.status_code in {200, 307, 308}
    assert wins_alias.status_code in {200, 307, 308}
