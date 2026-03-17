from fastapi.testclient import TestClient
from peewee import SqliteDatabase


def make_client(tmp_path):
    from src.apps.web.app import create_app
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema
    from src.services.guild_sites import provision_guild_site

    database = SqliteDatabase(
        str(tmp_path / "guild-sites.db"),
        check_same_thread=False,
    )
    shared_database.initialize(database)
    bootstrap_shared_schema(database)
    provision_guild_site(
        slug="north-guild",
        subdomain="north",
        display_name="North Guild",
        clan_tags=["NRTH", "NTH"],
        discord_guild_id=123,
    )
    provision_guild_site(
        slug="sleeping-guild",
        subdomain="sleeping",
        display_name="Sleeping Guild",
        clan_tags=["SLP"],
        is_active=False,
    )
    return TestClient(create_app())


def test_web_root_resolves_active_guild_by_subdomain(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/", headers={"host": "north.example.test"})

    assert response.status_code == 200
    assert "North Guild" in response.text
    assert "NRTH" in response.text
    assert "/leaderboard" in response.text
    assert "/players" in response.text
    assert "/combos" in response.text
    assert "/wins" in response.text
    assert "window.__GUILD_CONTEXT__" in response.text


def test_web_root_returns_not_found_for_unknown_or_inactive_guild(tmp_path):
    client = make_client(tmp_path)

    unknown = client.get("/", headers={"host": "unknown.example.test"})
    inactive = client.get("/", headers={"host": "sleeping.example.test"})

    assert unknown.status_code == 404
    assert inactive.status_code == 404
