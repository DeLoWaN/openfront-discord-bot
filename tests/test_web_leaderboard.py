from datetime import datetime

from peewee import SqliteDatabase


def make_client(tmp_path):
    from src.apps.web.app import create_app
    from src.data.database import shared_database
    from src.data.shared.models import GuildPlayerAggregate, Player
    from src.data.shared.schema import bootstrap_shared_schema
    from src.services.guild_sites import provision_guild_site

    database = SqliteDatabase(
        str(tmp_path / "leaderboard.db"),
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
    linked_player = Player.create(
        openfront_player_id="player-1",
        canonical_username="Bolt",
        canonical_normalized_username="bolt",
        is_linked=1,
    )
    GuildPlayerAggregate.create(
        guild=guild,
        normalized_username="bolt",
        display_username="[NU] Bolt",
        last_observed_clan_tag="NU",
        player=linked_player,
        win_count=7,
        game_count=9,
        team_win_count=5,
        team_game_count=7,
        ffa_win_count=2,
        ffa_game_count=2,
        team_score=220.0,
        ffa_score=70.0,
        team_recent_game_count_30d=5,
        ffa_recent_game_count_30d=1,
        donated_troops_total=1200,
        donated_gold_total=50,
        donation_action_count=2,
        support_bonus=3.5,
        attack_troops_total=8000,
        attack_action_count=9,
        role_label="Hybrid",
        last_team_game_at=datetime(2026, 3, 14, 11, 0, 0),
        last_ffa_game_at=datetime(2026, 3, 10, 12, 0, 0),
        last_game_at=datetime(2026, 3, 14, 11, 0, 0),
    )
    GuildPlayerAggregate.create(
        guild=guild,
        normalized_username="ace",
        display_username="[NU] Ace",
        last_observed_clan_tag="NU",
        win_count=11,
        game_count=13,
        team_win_count=9,
        team_game_count=11,
        ffa_win_count=2,
        ffa_game_count=2,
        team_score=260.0,
        ffa_score=80.0,
        team_recent_game_count_30d=3,
        ffa_recent_game_count_30d=1,
        donated_troops_total=500,
        donated_gold_total=10,
        donation_action_count=1,
        support_bonus=0.0,
        attack_troops_total=12000,
        attack_action_count=14,
        role_label="Frontliner",
        last_team_game_at=datetime(2026, 3, 13, 18, 0, 0),
        last_ffa_game_at=datetime(2026, 3, 9, 14, 0, 0),
        last_game_at=datetime(2026, 3, 13, 18, 0, 0),
    )
    return create_app()


def test_leaderboard_uses_stored_aggregates_and_marks_state(tmp_path):
    from fastapi.testclient import TestClient

    client = TestClient(make_client(tmp_path))

    response = client.get("/leaderboard", headers={"host": "north.example.test"})

    assert response.status_code == 200
    assert "North Guild" in response.text
    assert 'id="app-root"' in response.text
    assert "/leaderboard" in response.text
    assert "/players" in response.text
    assert "/combos" in response.text
    assert "/wins" in response.text
    assert '"currentPath": "/leaderboard"' in response.text


def test_leaderboard_shell_supports_all_public_views_except_overall(tmp_path):
    from fastapi.testclient import TestClient

    client = TestClient(make_client(tmp_path))

    team = client.get(
        "/leaderboard?view=team",
        headers={"host": "north.example.test"},
    )
    ffa = client.get(
        "/leaderboard?view=ffa",
        headers={"host": "north.example.test"},
    )
    overall = client.get(
        "/leaderboard?view=overall",
        headers={"host": "north.example.test"},
    )
    support = client.get(
        "/leaderboard?view=support",
        headers={"host": "north.example.test"},
    )

    assert team.status_code == 200
    assert '"currentPath": "/leaderboard"' in team.text

    assert ffa.status_code == 200
    assert '"currentPath": "/leaderboard"' in ffa.text

    assert overall.status_code == 404

    assert support.status_code == 200
    assert '"currentPath": "/leaderboard"' in support.text


def test_leaderboard_shell_keeps_guild_scope_for_all_supported_views(tmp_path):
    from fastapi.testclient import TestClient

    client = TestClient(make_client(tmp_path))
    team = client.get(
        "/leaderboard?view=team",
        headers={"host": "north.example.test"},
    )
    ffa = client.get(
        "/leaderboard?view=ffa",
        headers={"host": "north.example.test"},
    )
    support = client.get(
        "/leaderboard?view=support",
        headers={"host": "north.example.test"},
    )

    assert "North Guild" in team.text
    assert "North Guild" in ffa.text
    assert "North Guild" in support.text
    assert "/players" in team.text
    assert "/combos" in ffa.text
    assert "/wins" in support.text


def test_player_profile_page_is_public_for_observed_and_linked_entries(tmp_path):
    from fastapi.testclient import TestClient

    client = TestClient(make_client(tmp_path))

    observed = client.get("/players/ace", headers={"host": "north.example.test"})
    linked = client.get("/players/bolt", headers={"host": "north.example.test"})

    assert observed.status_code == 200
    assert 'id="app-root"' in observed.text
    assert '"currentPath": "/players/ace"' in observed.text
    assert linked.status_code == 200
    assert '"currentPath": "/players/bolt"' in linked.text
