import asyncio
from datetime import datetime, timezone

from peewee import SqliteDatabase


def test_migrate_legacy_sqlite_data_into_shared_schema(tmp_path):
    from src.central_db import init_central_db, register_guild
    from src.data.database import shared_database
    from src.data.shared.models import Guild, GuildClanTag, Player, PlayerAlias, PlayerLink, SiteUser
    from src.data.shared.schema import bootstrap_shared_schema
    from src.models import init_guild_db
    from src.services.legacy_migration import migrate_legacy_sqlite_to_shared

    central_db_path = tmp_path / "central.db"
    guild_db_path = tmp_path / "guild_123.db"
    init_central_db(str(central_db_path))
    register_guild(123, str(guild_db_path))

    legacy_models = init_guild_db(str(guild_db_path), 123)
    legacy_models.ClanTag.create(tag_text="NU")
    legacy_models.User.create(
        discord_user_id=42,
        player_id="player-1",
        linked_at=datetime.now(timezone.utc).replace(tzinfo=None),
        last_username="damien",
        last_openfront_username="Ace",
    )

    database = SqliteDatabase(
        str(tmp_path / "shared.db"),
        check_same_thread=False,
    )
    shared_database.initialize(database)
    bootstrap_shared_schema(database)

    summary = migrate_legacy_sqlite_to_shared(str(central_db_path))

    assert summary.guilds_migrated == 1
    assert Guild.select().count() == 1
    assert Guild.get().discord_guild_id == 123
    assert GuildClanTag.get().tag_text == "NU"
    assert SiteUser.get().discord_user_id == 42
    assert Player.get().openfront_player_id == "player-1"
    assert PlayerLink.select().count() == 1
    assert PlayerAlias.get().raw_username == "Ace"
