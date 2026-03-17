from datetime import datetime

from fastapi.testclient import TestClient
from peewee import SqliteDatabase


def setup_client(tmp_path):
    from src.apps.web.app import create_app
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import ingest_game_payload

    database = SqliteDatabase(
        str(tmp_path / "guild-engagement.db"),
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

    def ingest(payload):
        ingest_game_payload(payload)

    ingest(
        {
            "info": {
                "gameID": "duo-win-1",
                "config": {
                    "gameType": "Public",
                    "gameMode": "Team",
                    "gameMap": "Europe",
                    "playerTeams": "Duos",
                },
                "numTeams": 8,
                "start": 1763000000000,
                "end": 1763001000000,
                "duration": 1000,
                "winner": ["team", "Team 1", "a1", "a2"],
                "players": [
                    {"clientID": "a1", "username": "[NU] Ace", "clanTag": "NU"},
                    {"clientID": "a2", "username": "[NU] Bolt", "clanTag": "NU"},
                    {"clientID": "e1", "username": "Enemy1", "clanTag": "ZZ"},
                ],
            }
        }
    )
    ingest(
        {
            "info": {
                "gameID": "duo-win-2",
                "config": {
                    "gameType": "Public",
                    "gameMode": "Team",
                    "gameMap": "Europe",
                    "playerTeams": "Duos",
                },
                "numTeams": 8,
                "start": 1763086400000,
                "end": 1763087400000,
                "duration": 1000,
                "winner": ["team", "Team 1", "b1", "b2"],
                "players": [
                    {"clientID": "b1", "username": "[NU] Ace", "clanTag": "NU"},
                    {"clientID": "b2", "username": "[NU] Bolt", "clanTag": "NU"},
                    {"clientID": "e2", "username": "Enemy2", "clanTag": "ZZ"},
                ],
            }
        }
    )
    ingest(
        {
            "info": {
                "gameID": "duo-win-3",
                "config": {
                    "gameType": "Public",
                    "gameMode": "Team",
                    "gameMap": "Asia",
                    "playerTeams": "Duos",
                },
                "numTeams": 8,
                "start": 1763172800000,
                "end": 1763173800000,
                "duration": 1000,
                "winner": ["team", "Team 1", "c1", "c2"],
                "players": [
                    {"clientID": "c1", "username": "[NU] Ace", "clanTag": "NU"},
                    {"clientID": "c2", "username": "[NU] Bolt", "clanTag": "NU"},
                    {"clientID": "e3", "username": "Enemy3", "clanTag": "ZZ"},
                ],
            }
        }
    )
    ingest(
        {
            "info": {
                "gameID": "duo-win-4",
                "config": {
                    "gameType": "Public",
                    "gameMode": "Team",
                    "gameMap": "Asia",
                    "playerTeams": "Duos",
                },
                "numTeams": 8,
                "start": 1763259200000,
                "end": 1763260200000,
                "duration": 1000,
                "winner": ["team", "Team 1", "d1", "d2"],
                "players": [
                    {"clientID": "d1", "username": "[NU] Ace", "clanTag": "NU"},
                    {"clientID": "d2", "username": "[NU] Bolt", "clanTag": "NU"},
                    {"clientID": "e4", "username": "Enemy4", "clanTag": "ZZ"},
                ],
            }
        }
    )
    ingest(
        {
            "info": {
                "gameID": "duo-loss-5",
                "config": {
                    "gameType": "Public",
                    "gameMode": "Team",
                    "gameMap": "Africa",
                    "playerTeams": "Duos",
                },
                "numTeams": 8,
                "start": 1763345600000,
                "end": 1763346600000,
                "duration": 1000,
                "winner": ["team", "Team 2", "x1", "x2"],
                "players": [
                    {"clientID": "e5", "username": "[NU] Ace", "clanTag": "NU"},
                    {"clientID": "e6", "username": "[NU] Bolt", "clanTag": "NU"},
                    {"clientID": "x1", "username": "Enemy5", "clanTag": "ZZ"},
                    {"clientID": "x2", "username": "Enemy6", "clanTag": "ZZ"},
                ],
            }
        }
    )
    ingest(
        {
            "info": {
                "gameID": "duo-pending-1",
                "config": {
                    "gameType": "Public",
                    "gameMode": "Team",
                    "gameMap": "World",
                    "playerTeams": "Duos",
                },
                "numTeams": 6,
                "start": 1763432000000,
                "end": 1763433000000,
                "duration": 1000,
                "winner": ["team", "Team 1", "f1", "f2"],
                "players": [
                    {"clientID": "f1", "username": "[NU] Cedar", "clanTag": "NU"},
                    {"clientID": "f2", "username": "[NU] Drift", "clanTag": "NU"},
                    {"clientID": "x2", "username": "Enemy6", "clanTag": "ZZ"},
                ],
            }
        }
    )
    ingest(
        {
            "info": {
                "gameID": "mixed-duo-excluded",
                "config": {
                    "gameType": "Public",
                    "gameMode": "Team",
                    "gameMap": "World",
                    "playerTeams": "Duos",
                },
                "numTeams": 6,
                "start": 1763518400000,
                "end": 1763519400000,
                "duration": 1000,
                "winner": ["team", "Team 1", "g1", "g9"],
                "players": [
                    {"clientID": "g1", "username": "[NU] Ace", "clanTag": "NU"},
                    {"clientID": "g9", "username": "Random", "clanTag": "ZZ"},
                ],
            }
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
                "start": 1763604800000,
                "end": 1763605700000,
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


def test_engagement_apis_expose_home_combos_wins_profile_and_timeseries(tmp_path):
    guild, client = setup_client(tmp_path)
    host = {"host": f"{guild.subdomain}.example.test"}

    home = client.get("/api/home", headers=host)
    combos = client.get("/api/combos/duo", headers=host)
    combo_detail = client.get("/api/combos/duo/ace%7Cbolt", headers=host)
    wins = client.get("/api/results/recent", headers=host)
    profile = client.get("/api/players/ace", headers=host)
    timeseries = client.get("/api/players/ace/timeseries", headers=host)

    assert home.status_code == 200
    assert home.json()["guild"]["display_name"] == "North Guild"
    assert home.json()["combo_podiums"]["duo"][0]["roster_key"] == "ace|bolt"
    assert home.json()["pending_combo_teaser"]["counts"]["duo"] == 1
    assert home.json()["recent_badges"]

    assert combos.status_code == 200
    assert combos.json()["confirmed"][0]["roster_key"] == "ace|bolt"
    assert combos.json()["confirmed"][0]["games_together"] == 5
    assert combos.json()["confirmed"][0]["win_rate"] == 0.8
    assert combos.json()["pending"][0]["roster_key"] == "cedar|drift"
    assert all(row["roster_key"] != "ace" for row in combos.json()["confirmed"])

    assert combo_detail.status_code == 200
    assert combo_detail.json()["combo"]["status"] == "confirmed"
    assert len(combo_detail.json()["history"]) == 5

    assert wins.status_code == 200
    assert wins.json()["items"][0]["mode"] in {"Free For All", "Team"}
    assert wins.json()["items"][0]["replay_link"].endswith(
        wins.json()["items"][0]["openfront_game_id"]
    )
    assert {item["mode"] for item in wins.json()["items"]} == {"Team", "Free For All"}

    assert profile.status_code == 200
    assert profile.json()["badges"]
    assert profile.json()["best_partners"][0]["normalized_username"] == "bolt"
    assert profile.json()["combo_summaries"][0]["roster_key"] == "ace|bolt"

    assert timeseries.status_code == 200
    assert timeseries.json()["progression"]
    assert timeseries.json()["recent_form"]


def test_public_spa_routes_preserve_guild_scope(tmp_path):
    guild, client = setup_client(tmp_path)
    host = {"host": f"{guild.subdomain}.example.test"}

    home = client.get("/", headers=host)
    leaderboard = client.get("/leaderboard", headers=host)
    combos = client.get("/combos", headers=host)
    wins = client.get("/wins", headers=host)
    player = client.get("/players/ace", headers=host)

    assert home.status_code == 200
    assert "North Guild" in home.text
    assert "/leaderboard" in home.text
    assert "/combos" in home.text
    assert "/wins" in home.text

    assert leaderboard.status_code == 200
    assert combos.status_code == 200
    assert wins.status_code == 200
    assert player.status_code == 200
