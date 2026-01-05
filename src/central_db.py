from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from peewee import (
    CharField,
    DateTimeField,
    IntegerField,
    Model,
    SqliteDatabase,
)

central_database = SqliteDatabase(None)


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BaseModel(Model):
    created_at = DateTimeField(default=utcnow_naive)
    updated_at = DateTimeField(default=utcnow_naive)

    def save(self, *args, **kwargs):  # type: ignore[override]
        self.updated_at = utcnow_naive()
        return super().save(*args, **kwargs)

    class Meta:
        database = central_database


class GuildEntry(BaseModel):
    guild_id = IntegerField(primary_key=True)
    database_path = CharField()


class TrackedGame(BaseModel):
    game_id = CharField(primary_key=True)
    first_seen_at = DateTimeField()
    next_attempt_at = DateTimeField()
    consecutive_unexpected_failures = IntegerField(default=0)
    failed_at = DateTimeField(null=True)


def init_central_db(path: str):
    central_database.init(path)
    central_database.connect(reuse_if_open=True)
    central_database.create_tables([GuildEntry, TrackedGame])
    if hasattr(GuildEntry, "_records"):
        GuildEntry._records = []
    if hasattr(TrackedGame, "_records"):
        TrackedGame._records = []
    try:
        cols = central_database.execute_sql(
            f"PRAGMA table_info({TrackedGame._meta.table_name});"
        ).fetchall()
        col_names = {row[1] for row in cols}
        if "consecutive_unexpected_failures" not in col_names:
            central_database.execute_sql(
                f"ALTER TABLE {TrackedGame._meta.table_name} "
                "ADD COLUMN consecutive_unexpected_failures INTEGER NOT NULL DEFAULT 0"
            )
        if "failed_at" not in col_names:
            central_database.execute_sql(
                f"ALTER TABLE {TrackedGame._meta.table_name} "
                "ADD COLUMN failed_at DATETIME"
            )
    except Exception:
        pass


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


def track_game(game_id: str, next_attempt_at: datetime) -> bool:
    now = utcnow_naive()
    existing = TrackedGame.get_or_none(TrackedGame.game_id == game_id)
    if existing:
        return False
    TrackedGame.create(
        game_id=game_id,
        first_seen_at=now,
        next_attempt_at=next_attempt_at,
    )
    return True


def list_due_tracked_games(now: datetime, limit: int = 50) -> List[TrackedGame]:
    try:
        return list(
            TrackedGame.select()
            .where(TrackedGame.next_attempt_at <= now, TrackedGame.failed_at.is_null())
            .order_by(TrackedGame.next_attempt_at)
            .limit(limit)
        )
    except TypeError:
        rows = [
            row
            for row in TrackedGame.select()
            if row.next_attempt_at <= now and row.failed_at is None
        ]
        rows.sort(key=lambda row: row.next_attempt_at)
        return rows[:limit]


def reschedule_tracked_game(game_id: str, next_attempt_at: datetime) -> None:
    entry = TrackedGame.get_or_none(TrackedGame.game_id == game_id)
    if not entry:
        return
    entry.next_attempt_at = next_attempt_at
    entry.save()


def remove_tracked_game(game_id: str) -> None:
    TrackedGame.delete().where(TrackedGame.game_id == game_id).execute()


def reset_tracked_game_unexpected_failures(game_id: str) -> None:
    entry = TrackedGame.get_or_none(TrackedGame.game_id == game_id)
    if not entry or entry.consecutive_unexpected_failures == 0:
        return
    entry.consecutive_unexpected_failures = 0
    entry.save()


def note_tracked_game_unexpected_failure(
    game_id: str, failed_at: datetime, max_failures: int
) -> bool:
    entry = TrackedGame.get_or_none(TrackedGame.game_id == game_id)
    if not entry:
        return False
    if entry.failed_at:
        return True
    entry.consecutive_unexpected_failures += 1
    if entry.consecutive_unexpected_failures >= max_failures:
        entry.failed_at = failed_at
    entry.save()
    return entry.failed_at is not None
