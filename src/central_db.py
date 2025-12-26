from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from peewee import (
    CharField,
    DateTimeField,
    IntegerField,
    Model,
    SqliteDatabase,
)

central_database = SqliteDatabase(None)


class BaseModel(Model):
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):  # type: ignore[override]
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    class Meta:
        database = central_database


class GuildEntry(BaseModel):
    guild_id = IntegerField(primary_key=True)
    database_path = CharField()


def init_central_db(path: str):
    central_database.init(path)
    central_database.connect(reuse_if_open=True)
    central_database.create_tables([GuildEntry])


def list_active_guilds() -> List[GuildEntry]:
    return list(GuildEntry.select())


def get_guild_entry(guild_id: int) -> Optional[GuildEntry]:
    return GuildEntry.get_or_none(GuildEntry.guild_id == guild_id)


def register_guild(guild_id: int, database_path: str) -> GuildEntry:
    entry, _created = GuildEntry.get_or_create(
        guild_id=guild_id,
        defaults={"database_path": database_path},
    )
    if entry.database_path != database_path:
        entry.database_path = database_path
        entry.save()
    return entry


def remove_guild(guild_id: int) -> bool:
    deleted = GuildEntry.delete().where(GuildEntry.guild_id == guild_id).execute()
    return deleted > 0
