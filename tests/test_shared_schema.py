from types import SimpleNamespace

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


def test_bootstrap_shared_schema_uses_longtext_for_cached_payload_columns():
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema

    database = SqliteDatabase(":memory:")
    shared_database.initialize(database)
    bootstrap_shared_schema(database)

    create_sql = database.execute_sql(
        "SELECT sql FROM sqlite_master WHERE name = 'cached_openfront_games'"
    ).fetchone()[0]

    assert '"PAYLOAD_JSON" LONGTEXT' in create_sql.upper()
    assert '"TURN_PAYLOAD_JSON" LONGTEXT' in create_sql.upper()


def test_run_shared_migrations_widens_cached_payload_columns():
    from src.data.shared.schema import run_shared_migrations

    executed = []

    class FakeDatabase:
        def get_columns(self, table_name):
            if table_name == "site_users":
                return [
                    SimpleNamespace(name="id"),
                    SimpleNamespace(name="discord_user_id"),
                    SimpleNamespace(name="discord_username"),
                    SimpleNamespace(name="created_at"),
                    SimpleNamespace(name="updated_at"),
                ]
            if table_name == "cached_openfront_games":
                return [
                    SimpleNamespace(name="payload_json", data_type="TEXT"),
                    SimpleNamespace(name="turn_payload_json", data_type="TEXT"),
                ]
            return []

        def execute_sql(self, sql):
            executed.append(sql)
            return None

    run_shared_migrations(FakeDatabase())

    assert any(
        "ALTER TABLE cached_openfront_games MODIFY COLUMN payload_json LONGTEXT NOT NULL"
        in sql
        for sql in executed
    )
    assert any(
        "ALTER TABLE cached_openfront_games MODIFY COLUMN turn_payload_json LONGTEXT NULL"
        in sql
        for sql in executed
    )
