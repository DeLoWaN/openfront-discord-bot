from peewee import SqliteDatabase


def setup_shared_database(tmp_path):
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema

    database = SqliteDatabase(
        str(tmp_path / "competitive-leaderboards.db"),
        check_same_thread=False,
    )
    shared_database.initialize(database)
    bootstrap_shared_schema(database)
    return database


def test_build_leaderboard_rows_for_competitive_views(tmp_path):
    from src.data.shared.models import GuildPlayerAggregate, Player
    from src.services.guild_sites import provision_guild_site
    from src.services.guild_stats_api import (
        build_leaderboard_response,
        build_scoring_response,
    )

    setup_shared_database(tmp_path)
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
    GuildPlayerAggregate.create(
        guild=guild,
        normalized_username="bolt",
        display_username="[NU] Bolt",
        last_observed_clan_tag="NU",
        player=linked_player,
        win_count=8,
        game_count=12,
        team_win_count=5,
        team_game_count=8,
        ffa_win_count=3,
        ffa_game_count=4,
        team_score=220.0,
        ffa_score=90.0,
        overall_score=181.0,
        donated_troops_total=800000,
        donated_gold_total=250000,
        donation_action_count=9,
        support_bonus=12.0,
        attack_troops_total=50000,
        attack_action_count=2,
        role_label="Backliner",
    )

    team = build_leaderboard_response(guild, "team")
    ffa = build_leaderboard_response(guild, "ffa")
    overall = build_leaderboard_response(guild, "overall")
    support = build_leaderboard_response(guild, "support")
    scoring = build_scoring_response("team")
    overall_scoring = build_scoring_response("overall")

    assert team["view"] == "team"
    assert team["default_sort"] == "team_score"
    assert team["rows"][0]["display_username"] == "Ace"
    assert team["rows"][1]["state"] == "Linked"
    assert ffa["rows"][0]["display_username"] == "Bolt"
    assert overall["rows"][0]["display_username"] == "Ace"
    assert support["default_sort"] == "donated_troops_total"
    assert support["rows"][0]["display_username"] == "Bolt"
    assert support["rows"][0]["role_label"] == "Backliner"
    assert "more teams count more" in scoring["summary"].lower()
    assert "small sample" in overall_scoring["summary"].lower()


def test_build_leaderboard_overall_falls_back_to_team_score_for_team_only_rows(tmp_path):
    from src.data.shared.models import GuildPlayerAggregate
    from src.services.guild_sites import provision_guild_site
    from src.services.guild_stats_api import build_leaderboard_response

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North Guild",
        clan_tags=["NU"],
    )
    GuildPlayerAggregate.create(
        guild=guild,
        normalized_username="temujin",
        display_username="[NU] Temujin",
        last_observed_clan_tag="NU",
        win_count=9,
        game_count=22,
        team_win_count=9,
        team_game_count=22,
        ffa_win_count=0,
        ffa_game_count=0,
        team_score=980.97,
        ffa_score=0.0,
        overall_score=0.0,
        donated_troops_total=0,
        donated_gold_total=0,
        donation_action_count=0,
        support_bonus=0.0,
        attack_troops_total=1000,
        attack_action_count=1,
        role_label="Frontliner",
    )

    overall = build_leaderboard_response(guild, "overall")

    assert overall["rows"][0]["display_username"] == "Temujin"
    assert overall["rows"][0]["overall_score"] == 980.97
