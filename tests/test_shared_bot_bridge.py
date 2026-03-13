import asyncio

from peewee import SqliteDatabase


def setup_shared_database(tmp_path):
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema
    from src.services.shared_bot_bridge import set_shared_bot_bridge_enabled

    database = SqliteDatabase(
        str(tmp_path / "shared-bridge.db"),
        check_same_thread=False,
    )
    shared_database.initialize(database)
    bootstrap_shared_schema(database)
    set_shared_bot_bridge_enabled(True)
    return database


def test_bot_username_index_merges_shared_backend_aliases(tmp_path):
    from src.bot import build_openfront_username_index
    from src.data.shared.models import Player, PlayerAlias, PlayerLink, SiteUser
    from src.models import init_guild_db

    setup_shared_database(tmp_path)
    site_user = SiteUser.create(discord_user_id=42, discord_username="damien")
    player = Player.create(
        openfront_player_id="player-1",
        canonical_username="Ace",
        canonical_normalized_username="ace",
        is_linked=1,
    )
    PlayerAlias.create(
        player=player,
        raw_username="AcePrime",
        normalized_username="aceprime",
        source="linked_history",
    )
    PlayerLink.create(site_user=site_user, player=player)

    legacy_models = init_guild_db(str(tmp_path / "guild_1.db"), 1)
    legacy_models.User.create(
        discord_user_id=99,
        player_id="legacy",
        linked_at="2026-03-11 00:00:00",
        last_openfront_username="LegacyAce",
    )

    index = build_openfront_username_index(legacy_models)

    assert index["LegacyAce"] == [99]
    assert index["Ace"] == [42]
    assert index["AcePrime"] == [42]


def test_mirror_legacy_bot_link_creates_shared_site_user_and_player_link(tmp_path):
    from src.data.shared.models import PlayerLink, SiteUser
    from src.services.shared_bot_bridge import mirror_legacy_bot_link

    setup_shared_database(tmp_path)

    class FakeOpenFront:
        async def fetch_player(self, player_id):
            return {"stats": {"Public": {}}}

        async def fetch_sessions(self, player_id):
            return [
                {
                    "username": "Ace",
                    "clanTag": "NU",
                    "gameType": "Public",
                    "hasWon": True,
                    "gameStart": "2026-03-01T10:00:00Z",
                    "gameEnd": "2026-03-01T10:20:00Z",
                }
            ]

    asyncio.run(
        mirror_legacy_bot_link(
            discord_user_id=42,
            display_name="Damien",
            player_id="player-1",
            client=FakeOpenFront(),
        )
    )

    assert SiteUser.get().discord_user_id == 42
    assert PlayerLink.select().count() == 1
