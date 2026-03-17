from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from peewee import SqliteDatabase

from src.core.config import BotConfig, DiscordOAuthConfig


def make_client(tmp_path):
    from src.apps.web.app import create_app
    from src.data.database import shared_database
    from src.data.shared.models import SiteUser
    from src.data.shared.schema import bootstrap_shared_schema
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import (
        ingest_game_payload,
        refresh_guild_player_aggregates,
    )

    database = SqliteDatabase(
        str(tmp_path / "auth-linking.db"),
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
    ingest_game_payload(
        {
            "info": {
                "gameID": "game-1",
                "config": {"gameType": "Public", "gameMode": "Team"},
                "winner": ["team", "Team 1", "c1"],
                "players": [
                    {"clientID": "c1", "username": "Ace", "clanTag": "NU"},
                    {"clientID": "c2", "username": "Acel", "clanTag": "NU"},
                ],
            }
        }
    )
    refresh_guild_player_aggregates(guild.id)

    class FakeDiscordOAuth:
        async def exchange_code(self, code):
            assert code == "oauth-code"
            return {"access_token": "discord-token"}

        async def fetch_user(self, access_token):
            assert access_token == "discord-token"
            return {
                "id": "42",
                "username": "damien",
                "global_name": "Damien",
                "avatar": "avatar-hash",
            }

    class FakeOpenFront:
        async def fetch_player(self, player_id):
            assert player_id == "player-1"
            return {
                "stats": {
                    "Public": {
                        "Free For All": {"Medium": {"wins": 3}},
                        "Team": {"Medium": {"wins": 6}},
                    }
                }
            }

        async def fetch_sessions(self, player_id):
            assert player_id == "player-1"
            return [
                {
                    "username": "Ace",
                    "clanTag": "NU",
                    "gameType": "Public",
                    "hasWon": True,
                    "gameStart": "2026-03-01T10:00:00Z",
                    "gameEnd": "2026-03-01T10:20:00Z",
                },
                {
                    "username": "AcePrime",
                    "clanTag": "",
                    "gameType": "Public",
                    "hasWon": True,
                    "gameStart": "2026-03-02T10:00:00Z",
                    "gameEnd": "2026-03-02T10:20:00Z",
                },
            ]

    app = create_app(
        config=BotConfig(
            token="token",
            log_level="INFO",
            central_database_path=str(tmp_path / "central.db"),
            sync_interval_hours=24,
            results_lobby_poll_seconds=2,
            discord_oauth=DiscordOAuthConfig(
                client_id="discord-client",
                client_secret="discord-secret",
                redirect_uri="https://north.example.test/auth/discord/callback",
                session_secret="session-secret",
            ),
        ),
        discord_oauth_client=FakeDiscordOAuth(),
        openfront_client=FakeOpenFront(),
    )
    return TestClient(app), SiteUser


def test_discord_oauth_login_and_callback_create_site_user_session(tmp_path):
    client, SiteUser = make_client(tmp_path)

    login = client.get(
        "/auth/discord/login",
        headers={"host": "north.example.test"},
        follow_redirects=False,
    )
    query = parse_qs(urlparse(login.headers["location"]).query)
    callback = client.get(
        "/auth/discord/callback",
        params={"code": "oauth-code", "state": query["state"][0]},
        headers={"host": "north.example.test"},
        follow_redirects=False,
    )
    account = client.get("/account", headers={"host": "north.example.test"})

    assert login.status_code in {302, 307}
    assert "discord.com/oauth2/authorize" in login.headers["location"]
    assert callback.status_code in {302, 307}
    assert callback.headers["location"] == "/account"
    assert SiteUser.select().count() == 1
    assert "damien" in account.text


def test_linking_player_id_marks_exact_alias_as_linked_and_shows_global_stats(tmp_path):
    client, _SiteUser = make_client(tmp_path)

    login = client.get(
        "/auth/discord/login",
        headers={"host": "north.example.test"},
        follow_redirects=False,
    )
    query = parse_qs(urlparse(login.headers["location"]).query)
    client.get(
        "/auth/discord/callback",
        params={"code": "oauth-code", "state": query["state"][0]},
        headers={"host": "north.example.test"},
        follow_redirects=False,
    )

    link = client.post(
        "/account/link",
        params={"player_id": "player-1"},
        headers={"host": "north.example.test"},
        follow_redirects=False,
    )
    exact = client.get("/players/ace", headers={"host": "north.example.test"})
    similar = client.get("/players/acel", headers={"host": "north.example.test"})
    exact_api = client.get("/api/players/ace", headers={"host": "north.example.test"})
    similar_api = client.get("/api/players/acel", headers={"host": "north.example.test"})

    assert link.status_code in {302, 303, 307}
    assert exact.status_code == 200
    assert '"currentPath": "/players/ace"' in exact.text
    assert exact_api.status_code == 200
    assert exact_api.json()["player"]["state"] == "Linked"
    assert exact_api.json()["linked"]["global_public_wins"] == 9
    assert similar.status_code == 200
    assert '"currentPath": "/players/acel"' in similar.text
    assert similar_api.status_code == 200
    assert similar_api.json()["player"]["state"] == "Observed"
