from __future__ import annotations

from typing import Iterable

from ..database import shared_database
from .models import SHARED_MODELS, SiteUser


def _existing_columns(database, table_name: str) -> set[str]:
    try:
        return {column.name for column in database.get_columns(table_name)}
    except Exception:
        try:
            rows = database.execute_sql(f"PRAGMA table_info({table_name});").fetchall()
        except Exception:
            return set()
        return {row[1] for row in rows}


def _column_metadata(database, table_name: str) -> dict[str, object]:
    try:
        return {column.name: column for column in database.get_columns(table_name)}
    except Exception:
        return {}


def _normalized_data_type(column: object) -> str:
    data_type = getattr(column, "data_type", "") or getattr(column, "column_type", "")
    return str(data_type).strip().upper()


def _supports_modify_column(database) -> bool:
    module_name = type(database).__module__.lower()
    class_name = type(database).__name__.lower()
    return "sqlite" not in module_name and "sqlite" not in class_name


def ensure_column(database, table_name: str, column_name: str, ddl_sql: str) -> None:
    if column_name in _existing_columns(database, table_name):
        return
    database.execute_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl_sql}")


def ensure_column_type(
    database,
    table_name: str,
    column_name: str,
    ddl_sql: str,
    expected_types: set[str],
) -> None:
    if not _supports_modify_column(database):
        return
    metadata = _column_metadata(database, table_name)
    column = metadata.get(column_name)
    if column is None:
        return
    if _normalized_data_type(column) in {value.upper() for value in expected_types}:
        return
    database.execute_sql(
        f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {ddl_sql}"
    )


def run_shared_migrations(database) -> None:
    site_user_table = SiteUser._meta.table_name
    ensure_column(
        database,
        site_user_table,
        "discord_global_name",
        "VARCHAR(255) NULL",
    )
    ensure_column(
        database,
        site_user_table,
        "discord_avatar_hash",
        "VARCHAR(255) NULL",
    )
    ensure_column(database, site_user_table, "last_login_at", "DATETIME NULL")

    additive_columns = (
        ("backfill_runs", "skipped_known_count", "INTEGER NOT NULL DEFAULT 0"),
        ("backfill_runs", "replayed_count", "INTEGER NOT NULL DEFAULT 0"),
        ("backfill_runs", "cache_failure_count", "INTEGER NOT NULL DEFAULT 0"),
        (
            "backfill_runs",
            "openfront_rate_limit_hit_count",
            "INTEGER NOT NULL DEFAULT 0",
        ),
        (
            "backfill_runs",
            "openfront_retry_after_count",
            "INTEGER NOT NULL DEFAULT 0",
        ),
        (
            "backfill_runs",
            "openfront_cooldown_seconds_total",
            "DOUBLE NOT NULL DEFAULT 0",
        ),
        (
            "backfill_runs",
            "openfront_cooldown_seconds_max",
            "DOUBLE NOT NULL DEFAULT 0",
        ),
        (
            "openfront_rate_limit_state",
            "active_leases",
            "INTEGER NOT NULL DEFAULT 0",
        ),
        ("backfill_games", "matched_guild_count", "INTEGER NOT NULL DEFAULT 0"),
        ("cached_openfront_games", "turn_payload_json", "LONGTEXT NULL"),
        ("game_participants", "attack_troops_total", "BIGINT NOT NULL DEFAULT 0"),
        ("game_participants", "attack_action_count", "INTEGER NOT NULL DEFAULT 0"),
        ("game_participants", "donated_troops_total", "BIGINT NOT NULL DEFAULT 0"),
        ("game_participants", "donated_gold_total", "BIGINT NOT NULL DEFAULT 0"),
        ("game_participants", "donation_action_count", "INTEGER NOT NULL DEFAULT 0"),
        ("guild_player_aggregates", "team_win_count", "INTEGER NOT NULL DEFAULT 0"),
        ("guild_player_aggregates", "team_game_count", "INTEGER NOT NULL DEFAULT 0"),
        ("guild_player_aggregates", "ffa_win_count", "INTEGER NOT NULL DEFAULT 0"),
        ("guild_player_aggregates", "ffa_game_count", "INTEGER NOT NULL DEFAULT 0"),
        (
            "guild_player_aggregates",
            "donated_troops_total",
            "BIGINT NOT NULL DEFAULT 0",
        ),
        (
            "guild_player_aggregates",
            "donated_gold_total",
            "BIGINT NOT NULL DEFAULT 0",
        ),
        (
            "guild_player_aggregates",
            "donation_action_count",
            "INTEGER NOT NULL DEFAULT 0",
        ),
        (
            "guild_player_aggregates",
            "attack_troops_total",
            "BIGINT NOT NULL DEFAULT 0",
        ),
        (
            "guild_player_aggregates",
            "attack_action_count",
            "INTEGER NOT NULL DEFAULT 0",
        ),
        ("guild_player_aggregates", "support_bonus", "DOUBLE NOT NULL DEFAULT 0"),
        ("guild_player_aggregates", "team_score", "DOUBLE NOT NULL DEFAULT 0"),
        ("guild_player_aggregates", "ffa_score", "DOUBLE NOT NULL DEFAULT 0"),
        ("guild_player_aggregates", "overall_score", "DOUBLE NOT NULL DEFAULT 0"),
        ("guild_player_aggregates", "role_label", "VARCHAR(255) NULL"),
        (
            "guild_player_aggregates",
            "team_recent_game_count_30d",
            "INTEGER NOT NULL DEFAULT 0",
        ),
        (
            "guild_player_aggregates",
            "ffa_recent_game_count_30d",
            "INTEGER NOT NULL DEFAULT 0",
        ),
        ("guild_player_aggregates", "last_team_game_at", "DATETIME NULL"),
        ("guild_player_aggregates", "last_ffa_game_at", "DATETIME NULL"),
    )
    for table_name, column_name, ddl_sql in additive_columns:
        ensure_column(database, table_name, column_name, ddl_sql)
    ensure_column_type(
        database,
        "cached_openfront_games",
        "payload_json",
        "LONGTEXT NOT NULL",
        {"LONGTEXT"},
    )
    ensure_column_type(
        database,
        "cached_openfront_games",
        "turn_payload_json",
        "LONGTEXT NULL",
        {"LONGTEXT"},
    )


def bootstrap_shared_schema(database=None, models: Iterable[type] = SHARED_MODELS) -> None:
    target_database = database or getattr(shared_database, "obj", None) or shared_database
    target_database.connect(reuse_if_open=True)
    bound_models = list(models)
    target_database.bind(bound_models, bind_refs=False, bind_backrefs=False)
    target_database.create_tables(bound_models, safe=True)
    run_shared_migrations(target_database)
