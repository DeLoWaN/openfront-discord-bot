from peewee import SqliteDatabase


def test_bootstrap_shared_schema_creates_tables_and_runs_additive_migrations():
    from src.data.database import shared_database
    from src.data.shared.schema import SHARED_MODELS, bootstrap_shared_schema

    database = SqliteDatabase(":memory:")
    shared_database.initialize(database)
    database.connect(reuse_if_open=True)
    database.execute_sql(
        """
        CREATE TABLE site_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_user_id BIGINT NOT NULL UNIQUE,
            discord_username VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
        """
    )

    bootstrap_shared_schema(database)

    table_names = set(database.get_tables())
    expected_tables = {model._meta.table_name for model in SHARED_MODELS}
    site_user_columns = {column.name for column in database.get_columns("site_users")}

    assert expected_tables.issubset(table_names)
    assert "discord_global_name" in site_user_columns
    assert "discord_avatar_hash" in site_user_columns
    assert "last_login_at" in site_user_columns
    assert "backfill_runs" in table_names
    assert "backfill_cursors" in table_names
    assert "backfill_games" in table_names
    assert "cached_openfront_games" in table_names
