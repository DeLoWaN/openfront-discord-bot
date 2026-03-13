import os
from dataclasses import dataclass
from typing import Any

import yaml

CONFIG_ENV_KEY = "CONFIG_PATH"
DEFAULT_CONFIG_PATH = "config.yml"


@dataclass(frozen=True)
class MariaDBConfig:
    database: str
    user: str
    password: str
    host: str = "127.0.0.1"
    port: int = 3306
    charset: str = "utf8mb4"


@dataclass(frozen=True)
class DiscordOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    session_secret: str
    scope: str = "identify"


@dataclass
class BotConfig:
    token: str
    log_level: str
    central_database_path: str
    sync_interval_hours: int
    results_lobby_poll_seconds: int
    mariadb: MariaDBConfig | None = None
    discord_oauth: DiscordOAuthConfig | None = None


def _load_mariadb_config(data: dict[str, Any]) -> MariaDBConfig | None:
    raw = data.get("mariadb")
    if raw in (None, ""):
        return None
    if not isinstance(raw, dict):
        raise ValueError("mariadb must be a mapping")

    database = str(raw.get("database") or "").strip()
    user = str(raw.get("user") or "").strip()
    password = str(raw.get("password") or "")
    if not database:
        raise ValueError("mariadb.database is required when mariadb is configured")
    if not user:
        raise ValueError("mariadb.user is required when mariadb is configured")
    if password == "":
        raise ValueError("mariadb.password is required when mariadb is configured")

    host = str(raw.get("host") or "127.0.0.1").strip() or "127.0.0.1"
    charset = str(raw.get("charset") or "utf8mb4").strip() or "utf8mb4"
    try:
        port = int(raw.get("port", 3306))
    except (TypeError, ValueError):
        raise ValueError("mariadb.port must be an integer")

    return MariaDBConfig(
        database=database,
        user=user,
        password=password,
        host=host,
        port=port,
        charset=charset,
    )


def _load_discord_oauth_config(data: dict[str, Any]) -> DiscordOAuthConfig | None:
    raw = data.get("discord_oauth")
    if raw in (None, ""):
        return None
    if not isinstance(raw, dict):
        raise ValueError("discord_oauth must be a mapping")

    client_id = str(raw.get("client_id") or "").strip()
    client_secret = str(raw.get("client_secret") or "").strip()
    redirect_uri = str(raw.get("redirect_uri") or "").strip()
    session_secret = str(raw.get("session_secret") or "").strip()
    scope = str(raw.get("scope") or "identify").strip() or "identify"
    if not client_id:
        raise ValueError(
            "discord_oauth.client_id is required when discord_oauth is configured"
        )
    if not client_secret:
        raise ValueError(
            "discord_oauth.client_secret is required when discord_oauth is configured"
        )
    if not redirect_uri:
        raise ValueError(
            "discord_oauth.redirect_uri is required when discord_oauth is configured"
        )
    if not session_secret:
        raise ValueError(
            "discord_oauth.session_secret is required when discord_oauth is configured"
        )

    return DiscordOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        session_secret=session_secret,
        scope=scope,
    )


def load_config(path: str | None = None) -> BotConfig:
    config_path = path or os.environ.get(CONFIG_ENV_KEY, DEFAULT_CONFIG_PATH)
    with open(config_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    token = data.get("token", "").strip()
    if not token:
        raise ValueError("Config missing 'token'")

    log_level = str(data.get("log_level") or "INFO").upper()
    valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
    if log_level not in valid_levels:
        raise ValueError(
            f"Invalid log_level '{log_level}'. Must be one of {sorted(valid_levels)}"
        )

    central_database_path = str(data.get("central_database_path") or "central.db")
    if not central_database_path:
        raise ValueError("Config missing 'central_database_path'")

    interval_raw = data.get("sync_interval_hours", 24)
    try:
        sync_interval_hours = int(interval_raw)
    except (TypeError, ValueError):
        raise ValueError("sync_interval_hours must be an integer")
    sync_interval_hours = max(1, min(24, sync_interval_hours))

    lobby_interval_raw = data.get("results_lobby_poll_seconds", 2)
    try:
        results_lobby_poll_seconds = int(lobby_interval_raw)
    except (TypeError, ValueError):
        raise ValueError("results_lobby_poll_seconds must be an integer")
    results_lobby_poll_seconds = max(1, results_lobby_poll_seconds)
    mariadb = _load_mariadb_config(data)
    discord_oauth = _load_discord_oauth_config(data)

    return BotConfig(
        token=token,
        log_level=log_level,
        central_database_path=central_database_path,
        sync_interval_hours=sync_interval_hours,
        results_lobby_poll_seconds=results_lobby_poll_seconds,
        mariadb=mariadb,
        discord_oauth=discord_oauth,
    )
