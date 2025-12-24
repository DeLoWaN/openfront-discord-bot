import os
from dataclasses import dataclass
from typing import List

import yaml

CONFIG_ENV_KEY = "CONFIG_PATH"
DEFAULT_CONFIG_PATH = "config.yml"


@dataclass
class BotConfig:
    token: str
    admin_role_ids: List[int]
    database_path: str
    log_level: str


def load_config(path: str | None = None) -> BotConfig:
    config_path = path or os.environ.get(CONFIG_ENV_KEY, DEFAULT_CONFIG_PATH)
    with open(config_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    token = data.get("token", "").strip()
    if not token:
        raise ValueError("Config missing 'token'")

    admin_role_ids = data.get("admin_role_ids") or []
    if not isinstance(admin_role_ids, list) or not all(
        isinstance(i, (int, float, str)) for i in admin_role_ids
    ):
        raise ValueError("Config 'admin_role_ids' must be a list of IDs")
    admin_role_ids_int: List[int] = []
    for value in admin_role_ids:
        try:
            admin_role_ids_int.append(int(value))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid admin_role_id value: {value}") from exc
    if not admin_role_ids_int:
        raise ValueError("Config requires at least one admin_role_id")

    database_path = str(data.get("database_path") or "bot.db")
    log_level = str(data.get("log_level") or "INFO").upper()
    valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
    if log_level not in valid_levels:
        raise ValueError(
            f"Invalid log_level '{log_level}'. Must be one of {sorted(valid_levels)}"
        )

    return BotConfig(
        token=token,
        admin_role_ids=admin_role_ids_int,
        database_path=database_path,
        log_level=log_level,
    )
