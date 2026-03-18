from textwrap import dedent

from src.core.config import MariaDBConfig, OpenFrontBypassConfig, load_config


def test_load_config_reads_optional_mariadb_settings(tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        dedent(
            """
            token: "token"
            central_database_path: "central.db"
            mariadb:
              database: "guild_stats"
              user: "guildbot"
              password: "secret"
              host: "db.internal"
              port: 3307
              charset: "utf8mb4"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_config(str(config_path))

    assert config.mariadb == MariaDBConfig(
        database="guild_stats",
        user="guildbot",
        password="secret",
        host="db.internal",
        port=3307,
        charset="utf8mb4",
    )


def test_build_and_init_shared_mariadb_database():
    from src.data.database import (
        build_mariadb_connect_params,
        build_mariadb_database,
        init_shared_database,
        shared_database,
    )

    config = MariaDBConfig(
        database="guild_stats",
        user="guildbot",
        password="secret",
        host="db.internal",
        port=3307,
    )

    connect_params = build_mariadb_connect_params(config)
    database = build_mariadb_database(config)
    initialized = init_shared_database(config, connect=False)

    assert connect_params == {
        "user": "guildbot",
        "password": "secret",
        "host": "db.internal",
        "port": 3307,
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    assert database.database == "guild_stats"
    for key, value in connect_params.items():
        assert database.connect_params[key] == value
    assert initialized.database == "guild_stats"
    assert getattr(shared_database, "obj", None) is initialized


def test_load_config_reads_optional_openfront_bypass_settings(tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        dedent(
            """
            token: "token"
            central_database_path: "central.db"
            openfront:
              bypass_header_name: "X-OpenFront-Bypass"
              bypass_header_value: "secret-key"
              user_agent: "guild-bot/1.0"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_config(str(config_path))

    assert config.openfront == OpenFrontBypassConfig(
        bypass_header_name="X-OpenFront-Bypass",
        bypass_header_value="secret-key",
        user_agent="guild-bot/1.0",
    )
