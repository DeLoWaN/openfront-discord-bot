import os
from dataclasses import dataclass

import yaml

CONFIG_ENV_KEY = "CONFIG_PATH"
DEFAULT_CONFIG_PATH = "config.yml"


@dataclass
class BotConfig:
    token: str
    log_level: str
    central_database_path: str


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

    return BotConfig(
        token=token,
        log_level=log_level,
        central_database_path=central_database_path,
    )
