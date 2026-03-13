from fastapi.testclient import TestClient
from peewee import SqliteDatabase


def make_client(tmp_path):
    from src.apps.web.app import create_app
    from src.data.database import shared_database
    from src.data.shared.models import GuildPlayerAggregate
    from src.data.shared.schema import bootstrap_shared_schema
    from src.services.guild_sites import provision_guild_site

    database = SqliteDatabase(
        str(tmp_path / "guild-stats-api.db"),
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
    GuildPlayerAggregate.create(
        guild=guild,
        normalized_username="ace",
        display_username="[NU] Ace",
        last_observed_clan_tag="NU",
        win_count=10,
        game_count=12,
        team_win_count=8,
        team_game_count=10,
        ffa_win_count=2,
        ffa_game_count=2,
        team_score=260.0,
        ffa_score=70.0,
        overall_score=203.0,
        donated_troops_total=1000,
        donated_gold_total=0,
        donation_action_count=1,
        support_bonus=0.0,
        attack_troops_total=250000,
        attack_action_count=8,
        role_label="Frontliner",
    )
    return TestClient(create_app())


def test_guild_stats_api_exposes_leaderboard_and_scoring_payloads(tmp_path):
    client = make_client(tmp_path)

    leaderboard = client.get(
        "/api/leaderboards/team",
        headers={"host": "north.example.test"},
    )
    scoring = client.get(
        "/api/scoring/team",
        headers={"host": "north.example.test"},
    )
    profile = client.get(
        "/api/players/ace",
        headers={"host": "north.example.test"},
    )

    assert leaderboard.status_code == 200
    assert leaderboard.json()["view"] == "team"
    assert leaderboard.json()["rows"][0]["display_username"] == "Ace"
    assert "[NU] Ace" not in leaderboard.text
    assert scoring.status_code == 200
    assert "70% team" in scoring.json()["overall_summary"].lower()
    assert profile.status_code == 200
    assert profile.json()["player"]["display_username"] == "Ace"
    assert profile.json()["player"]["team_score"] == 260.0
