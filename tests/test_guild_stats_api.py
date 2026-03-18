from datetime import datetime

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
        team_recent_game_count_30d=4,
        ffa_recent_game_count_30d=1,
        donated_troops_total=1000,
        donated_gold_total=0,
        donation_action_count=1,
        support_bonus=0.0,
        attack_troops_total=250000,
        attack_action_count=8,
        role_label="Frontliner",
        last_team_game_at=datetime(2026, 3, 14, 10, 0, 0),
        last_ffa_game_at=datetime(2026, 3, 13, 12, 0, 0),
        last_game_at=datetime(2026, 3, 14, 10, 0, 0),
    )
    GuildPlayerAggregate.create(
        guild=guild,
        normalized_username="bolt",
        display_username="[NU] Bolt",
        last_observed_clan_tag="NU",
        win_count=7,
        game_count=12,
        team_win_count=5,
        team_game_count=11,
        ffa_win_count=2,
        ffa_game_count=2,
        team_score=180.0,
        ffa_score=90.0,
        team_recent_game_count_30d=8,
        ffa_recent_game_count_30d=2,
        donated_troops_total=5000,
        donated_gold_total=800,
        donation_action_count=12,
        support_bonus=24.5,
        attack_troops_total=125000,
        attack_action_count=5,
        role_label="Backliner",
        last_team_game_at=datetime(2026, 3, 15, 10, 0, 0),
        last_ffa_game_at=datetime(2026, 3, 14, 12, 0, 0),
        last_game_at=datetime(2026, 3, 15, 10, 0, 0),
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
    missing_view = client.get(
        "/api/leaderboards/overall",
        headers={"host": "north.example.test"},
    )

    assert leaderboard.status_code == 200
    assert leaderboard.json()["view"] == "team"
    assert leaderboard.json()["rows"][0]["display_username"] == "Ace"
    assert leaderboard.json()["rows"][0]["team_recent_game_count_30d"] == 4
    assert leaderboard.json()["rows"][0]["support_recent_game_count_30d"] == 4
    assert "overall_score" not in leaderboard.json()["rows"][0]
    assert "[NU] Ace" not in leaderboard.text
    assert scoring.status_code == 200
    assert "summary" in scoring.json()
    assert scoring.json()["details"]["title"] == "Exact computation"
    assert "recent activity" in scoring.json()["summary"].lower()
    assert profile.status_code == 200
    assert profile.json()["player"]["display_username"] == "Ace"
    assert profile.json()["player"]["team_score"] == 260.0
    assert profile.json()["player"]["team_recent_game_count_30d"] == 4
    assert profile.json()["sections"]["team"]["recent_games_30d"] == 4
    assert "overall" not in profile.json()["sections"]
    assert missing_view.status_code == 404


def test_guild_stats_api_exposes_sortable_columns_ratio_and_explicit_order(tmp_path):
    client = make_client(tmp_path)

    response = client.get(
        "/api/leaderboards/team?sort_by=team_recent_game_count_30d&order=asc",
        headers={"host": "north.example.test"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sort_by"] == "team_recent_game_count_30d"
    assert payload["order"] == "asc"
    assert payload["columns"]
    assert any(column["key"] == "ratio" for column in payload["columns"])
    assert any(column["key"] == "win_rate" for column in payload["columns"])
    assert payload["rows"][0]["display_username"] == "Ace"
    assert payload["rows"][0]["ratio"] == "8/10"


def test_guild_stats_api_uses_explicit_view_columns_and_filters_ffa_rows(tmp_path):
    from src.data.shared.models import GuildPlayerAggregate

    client = make_client(tmp_path)
    GuildPlayerAggregate.create(
        guild=1,
        normalized_username="cedar",
        display_username="[NU] Cedar",
        last_observed_clan_tag="NU",
        win_count=4,
        game_count=4,
        team_win_count=4,
        team_game_count=4,
        ffa_win_count=0,
        ffa_game_count=0,
        team_score=120.0,
        ffa_score=0.0,
        team_recent_game_count_30d=4,
        ffa_recent_game_count_30d=0,
        donated_troops_total=250,
        donated_gold_total=25,
        donation_action_count=2,
        support_bonus=5.0,
        attack_troops_total=50000,
        attack_action_count=4,
        role_label="Flexible",
        last_team_game_at=datetime(2026, 3, 16, 10, 0, 0),
        last_game_at=datetime(2026, 3, 16, 10, 0, 0),
    )

    team = client.get("/api/leaderboards/team", headers={"host": "north.example.test"})
    ffa = client.get("/api/leaderboards/ffa", headers={"host": "north.example.test"})
    support = client.get("/api/leaderboards/support", headers={"host": "north.example.test"})

    assert [column["label"] for column in team.json()["columns"]] == [
        "Player",
        "Team Score",
        "Wins",
        "Ratio",
        "Win Rate",
        "Games",
        "Games 30d",
        "Support Bonus",
        "Role",
    ]
    assert [column["label"] for column in ffa.json()["columns"]] == [
        "Player",
        "FFA Score",
        "Wins",
        "Ratio",
        "Win Rate",
        "Games",
        "Games 30d",
    ]
    assert [column["label"] for column in support.json()["columns"]] == [
        "Player",
        "Support Bonus",
        "Troops Donated",
        "Gold Donated",
        "Donation Actions",
        "Games 30d",
        "Role",
    ]
    assert [row["display_username"] for row in ffa.json()["rows"]] == ["Bolt", "Ace"]


def test_guild_stats_api_excludes_invalid_public_aggregate_rows(tmp_path):
    from src.data.shared.models import GuildPlayerAggregate

    client = make_client(tmp_path)
    GuildPlayerAggregate.create(
        guild=1,
        normalized_username="glitch",
        display_username="[NU] Glitch",
        last_observed_clan_tag="NU",
        win_count=9,
        game_count=9,
        team_win_count=7,
        team_game_count=7,
        ffa_win_count=3,
        ffa_game_count=1,
        team_score=140.0,
        ffa_score=100.0,
        team_recent_game_count_30d=3,
        ffa_recent_game_count_30d=1,
        donated_troops_total=0,
        donated_gold_total=0,
        donation_action_count=0,
        support_bonus=0.0,
        attack_troops_total=90000,
        attack_action_count=4,
        role_label="Flexible",
        last_team_game_at=datetime(2026, 3, 16, 12, 0, 0),
        last_ffa_game_at=datetime(2026, 3, 16, 13, 0, 0),
        last_game_at=datetime(2026, 3, 16, 13, 0, 0),
    )

    ffa = client.get("/api/leaderboards/ffa", headers={"host": "north.example.test"})
    profile = client.get("/api/players/glitch", headers={"host": "north.example.test"})

    assert ffa.status_code == 200
    assert [row["display_username"] for row in ffa.json()["rows"]] == ["Bolt", "Ace"]
    assert profile.status_code == 404
