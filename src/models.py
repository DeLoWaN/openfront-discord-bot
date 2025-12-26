from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from peewee import (
    AutoField,
    CharField,
    DateTimeField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

DEFAULT_COUNTING_MODE = "sessions_with_clan"
DEFAULT_SYNC_INTERVAL = 60


def utcnow_naive() -> datetime:
    """Return current UTC time without tzinfo for SQLite storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class GuildModels:
    db: SqliteDatabase
    User: type
    RoleThreshold: type
    ClanTag: type
    Settings: type
    Audit: type
    GuildAdminRole: type


def _create_guild_models(db: SqliteDatabase) -> GuildModels:
    class BaseModel(Model):
        created_at = DateTimeField(default=utcnow_naive)
        updated_at = DateTimeField(default=utcnow_naive)

        def save(self, *args, **kwargs):  # type: ignore[override]
            self.updated_at = utcnow_naive()
            return super().save(*args, **kwargs)

        class Meta:
            database = db

    class User(BaseModel):
        discord_user_id = IntegerField(primary_key=True)
        player_id = CharField()
        linked_at = DateTimeField()
        last_win_count = IntegerField(default=0)
        last_role_id = IntegerField(null=True)
        last_username = CharField(null=True)

    class RoleThreshold(BaseModel):
        id = AutoField()
        wins = IntegerField(unique=True)
        role_id = IntegerField(unique=True)

    class ClanTag(BaseModel):
        id = AutoField()
        tag_text = CharField(unique=True)

    class Settings(BaseModel):
        id = IntegerField(primary_key=True)
        counting_mode = CharField()
        sync_interval_minutes = IntegerField()
        backoff_until = DateTimeField(null=True)
        last_sync_at = DateTimeField(null=True)

    class Audit(BaseModel):
        id = AutoField()
        actor_discord_id = IntegerField()
        action = CharField()
        payload = TextField(null=True)

    class GuildAdminRole(BaseModel):
        role_id = IntegerField(primary_key=True)

    return GuildModels(
        db=db,
        User=User,
        RoleThreshold=RoleThreshold,
        ClanTag=ClanTag,
        Settings=Settings,
        Audit=Audit,
        GuildAdminRole=GuildAdminRole,
    )


def init_guild_db(path: str, guild_id: int) -> GuildModels:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = SqliteDatabase(path)
    models = _create_guild_models(db)
    db.connect(reuse_if_open=True)
    db.create_tables(
        [
            models.User,
            models.RoleThreshold,
            models.ClanTag,
            models.Settings,
            models.Audit,
            models.GuildAdminRole,
        ]
    )

    # Ensure new columns are present for older DBs.
    try:
        cols = db.execute_sql(
            f"PRAGMA table_info({models.User._meta.table_name});"
        ).fetchall()
        col_names = {row[1] for row in cols}
        if "last_username" not in col_names:
            db.execute_sql(
                f"ALTER TABLE {models.User._meta.table_name} ADD COLUMN last_username TEXT"
            )
        # Remove legacy role_name column by recreating the table without it if present.
        rt_table = models.RoleThreshold._meta.table_name
        rt_cols = db.execute_sql(f"PRAGMA table_info({rt_table});").fetchall()
        if any(row[1] == "role_name" for row in rt_cols):
            db.execute_sql(
                f"""
                BEGIN;
                CREATE TABLE {rt_table}_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wins INTEGER NOT NULL UNIQUE,
                    role_id INTEGER NOT NULL UNIQUE,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                );
                INSERT INTO {rt_table}_new (id, wins, role_id, created_at, updated_at)
                    SELECT id, wins, role_id, created_at, updated_at FROM {rt_table};
                DROP TABLE {rt_table};
                ALTER TABLE {rt_table}_new RENAME TO {rt_table};
                COMMIT;
                """
            )
    except Exception:
        # If PRAGMA/ALTER not supported (e.g., stub), ignore.
        pass

    if models.Settings.select().where(models.Settings.id == 1).count() == 0:
        models.Settings.create(
            id=1,
            counting_mode=DEFAULT_COUNTING_MODE,
            sync_interval_minutes=DEFAULT_SYNC_INTERVAL,
        )

    return models


def record_audit(
    models: GuildModels, actor_discord_id: int, action: str, payload: dict | None = None
):
    models.Audit.create(
        actor_discord_id=actor_discord_id,
        action=action,
        payload=json.dumps(payload) if payload else None,
    )


def upsert_role_threshold(models: GuildModels, wins: int, role_id: int):
    models.RoleThreshold.insert(wins=wins, role_id=role_id).on_conflict(
        conflict_target=[models.RoleThreshold.wins],
        update={
            models.RoleThreshold.role_id: role_id,
        },
    ).execute()


def seed_admin_roles(models: GuildModels, role_ids: Iterable[int]):
    for role_id in role_ids:
        try:
            rid = int(role_id)
        except (TypeError, ValueError):
            continue
        models.GuildAdminRole.insert(role_id=rid).on_conflict_ignore().execute()
