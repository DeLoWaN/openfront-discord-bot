from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable, List

from peewee import (
    AutoField,
    CharField,
    DateTimeField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

database = SqliteDatabase(None)


class BaseModel(Model):
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):  # type: ignore[override]
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    class Meta:
        database = database


class User(BaseModel):
    discord_user_id = IntegerField(primary_key=True)
    player_id = CharField()
    linked_at = DateTimeField()
    last_win_count = IntegerField(default=0)
    last_role_id = IntegerField(null=True)


class RoleThreshold(BaseModel):
    id = AutoField()
    wins = IntegerField(unique=True)
    role_id = IntegerField(unique=True)
    role_name = CharField()


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


DEFAULT_COUNTING_MODE = "sessions_with_clan"
DEFAULT_SYNC_INTERVAL = 60

DEFAULT_THRESHOLDS: List[dict] = [
    {
        "wins": 2,
        "role_id": 1453382920323731466,
        "role_name": "UN Recruit | Basic | 2 wins",
    },
    {
        "wins": 5,
        "role_id": 1453488016390754336,
        "role_name": "UN Trainee | Novice | 5 wins",
    },
    {
        "wins": 50,
        "role_id": 1453383116415701146,
        "role_name": "UN Champion | Supreme Strategist | 50 wins",
    },
]


def init_db(path: str):
    database.init(path)
    database.connect(reuse_if_open=True)
    database.create_tables([User, RoleThreshold, ClanTag, Settings, Audit])

    if Settings.select().where(Settings.id == 1).count() == 0:
        Settings.create(
            id=1,
            counting_mode=DEFAULT_COUNTING_MODE,
            sync_interval_minutes=DEFAULT_SYNC_INTERVAL,
        )

    existing_thresholds = {rt.wins for rt in RoleThreshold.select(RoleThreshold.wins)}
    for entry in DEFAULT_THRESHOLDS:
        if entry["wins"] in existing_thresholds:
            continue
        RoleThreshold.create(
            wins=entry["wins"], role_id=entry["role_id"], role_name=entry["role_name"]
        )


def record_audit(actor_discord_id: int, action: str, payload: dict | None = None):
    Audit.create(
        actor_discord_id=actor_discord_id,
        action=action,
        payload=json.dumps(payload) if payload else None,
    )


def upsert_role_threshold(wins: int, role_id: int, role_name: str):
    RoleThreshold.insert(wins=wins, role_id=role_id, role_name=role_name).on_conflict(
        conflict_target=[RoleThreshold.wins],
        update={RoleThreshold.role_id: role_id, RoleThreshold.role_name: role_name},
    ).execute()
