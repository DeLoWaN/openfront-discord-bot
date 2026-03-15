import gzip
import json
from datetime import datetime
from pathlib import Path

from peewee import SqliteDatabase


def setup_shared_database(tmp_path):
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema

    database = SqliteDatabase(
        str(tmp_path / "un-guild-regression.db"),
        check_same_thread=False,
    )
    shared_database.initialize(database)
    bootstrap_shared_schema(database)
    return database


def load_sql_fixture(database: SqliteDatabase, fixture_path: Path) -> None:
    sql_text = gzip.decompress(fixture_path.read_bytes()).decode("utf-8")
    database.connection().executescript(sql_text)


def test_un_guild_fixture_rebuilds_contribution_first_scores(tmp_path):
    from src.data.shared.models import Guild, GuildPlayerAggregate
    from src.services.guild_stats_api import build_leaderboard_response
    from src.services.openfront_ingestion import refresh_guild_player_aggregates

    database = setup_shared_database(tmp_path)
    fixture_path = Path("tests/fixtures/un_guild_fixture.sql.gz")
    snapshot_path = Path("tests/fixtures/un_guild_snapshot.json")

    load_sql_fixture(database, fixture_path)
    snapshot = json.loads(snapshot_path.read_text())
    guild = Guild.get(Guild.slug == "un")

    refresh_guild_player_aggregates(guild, now=datetime(2026, 3, 15, 12, 0, 0))

    rows = list(
        GuildPlayerAggregate.select().where(GuildPlayerAggregate.guild == guild)
    )
    team = build_leaderboard_response(guild, "team")
    support = build_leaderboard_response(guild, "support")
    team_rank_by_name = {
        row["display_username"]: index + 1 for index, row in enumerate(team["rows"])
    }

    assert len(rows) == snapshot["player_count"]
    assert team["rows"][0]["display_username"] in snapshot["allowed_top_team_players"]
    assert support["rows"][0]["display_username"] == snapshot["top_support_player"]
    assert team["rows"][0]["team_score"] > team["rows"][9]["team_score"]

    by_name = {row.display_username: row for row in rows}
    veteran = by_name["Temujin"]
    sprinter = by_name[snapshot["small_sample_player"]]

    assert veteran.team_score >= snapshot["min_temujin_team_score"]
    assert team_rank_by_name["Temujin"] <= snapshot["max_temujin_team_rank"]
    assert veteran.team_score > sprinter.team_score
    assert veteran.team_recent_game_count_30d >= 0

    support_bonus_by_name = {row.display_username: row.support_bonus for row in rows}
    for stronger, weaker in snapshot["support_order_pairs"]:
        assert support_bonus_by_name[stronger] > support_bonus_by_name[weaker]
