from datetime import datetime

import pytest
from peewee import SqliteDatabase


def make_database(tmp_path):
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema

    database = SqliteDatabase(
        str(tmp_path / "guild-site-services.db"),
        check_same_thread=False,
    )
    shared_database.initialize(database)
    bootstrap_shared_schema(database)
    return database


def test_build_guild_site_selector_requires_exactly_one_field(tmp_path):
    make_database(tmp_path)

    from src.services.guild_sites import build_guild_site_selector

    with pytest.raises(ValueError, match="exactly one"):
        build_guild_site_selector()

    with pytest.raises(ValueError, match="exactly one"):
        build_guild_site_selector(guild_id=1, slug="north")

    selector = build_guild_site_selector(slug="north-guild")

    assert selector.slug == "north-guild"
    assert selector.guild_id is None
    assert selector.subdomain is None


def test_create_list_get_update_and_toggle_guild_site(tmp_path):
    make_database(tmp_path)

    from src.services.guild_sites import (
        build_guild_site_selector,
        create_guild_site,
        get_guild_site,
        list_guild_sites,
        list_guild_clan_tags,
        set_guild_site_active,
        update_guild_site,
    )

    guild = create_guild_site(
        slug="north-guild",
        subdomain="north",
        display_name="North Guild",
        clan_tags=["NRTH", "NTH"],
        discord_guild_id=123,
    )

    assert guild.slug == "north-guild"
    assert bool(guild.is_active) is True
    assert list_guild_clan_tags(guild) == ["NRTH", "NTH"]

    listed = list_guild_sites()
    assert [item.slug for item in listed] == ["north-guild"]

    fetched = get_guild_site(build_guild_site_selector(slug="north-guild"))
    assert fetched is not None
    assert fetched.id == guild.id

    updated = update_guild_site(
        build_guild_site_selector(slug="north-guild"),
        display_name="North Wolves",
        subdomain="wolves",
        clan_tags=["WLF"],
    )

    assert updated.display_name == "North Wolves"
    assert updated.subdomain == "wolves"
    assert list_guild_clan_tags(updated) == ["WLF"]

    inactive = set_guild_site_active(
        build_guild_site_selector(guild_id=updated.id),
        is_active=False,
    )
    assert bool(inactive.is_active) is False

    active = set_guild_site_active(
        build_guild_site_selector(subdomain="wolves"),
        is_active=True,
    )
    assert bool(active.is_active) is True


def test_create_guild_site_rejects_duplicate_identity(tmp_path):
    make_database(tmp_path)

    from src.services.guild_sites import create_guild_site

    create_guild_site(
        slug="north-guild",
        subdomain="north",
        display_name="North Guild",
        discord_guild_id=123,
    )

    with pytest.raises(ValueError, match="already exists"):
        create_guild_site(
            slug="north-guild",
            subdomain="other",
            display_name="Other Guild",
        )

    with pytest.raises(ValueError, match="already exists"):
        create_guild_site(
            slug="other-guild",
            subdomain="north",
            display_name="Other Guild",
        )

    with pytest.raises(ValueError, match="already exists"):
        create_guild_site(
            slug="third-guild",
            subdomain="third",
            display_name="Third Guild",
            discord_guild_id=123,
        )


def test_create_guild_site_rejects_non_letter_clan_tags(tmp_path):
    make_database(tmp_path)

    from src.services.guild_sites import create_guild_site

    with pytest.raises(ValueError, match="letters A-Z"):
        create_guild_site(
            slug="north-guild",
            subdomain="north",
            display_name="North Guild",
            clan_tags=["NU1"],
        )


def test_delete_guild_site_requires_confirmation_and_preserves_global_records(
    tmp_path,
):
    make_database(tmp_path)

    from src.data.shared.models import (
        GameParticipant,
        Guild,
        GuildClanTag,
        GuildPlayerAggregate,
        ObservedGame,
        Player,
        PlayerLink,
        SiteUser,
    )
    from src.services.guild_sites import (
        build_guild_site_selector,
        create_guild_site,
        delete_guild_site,
    )

    guild = create_guild_site(
        slug="north-guild",
        subdomain="north",
        display_name="North Guild",
        clan_tags=["NRTH"],
    )
    site_user = SiteUser.create(discord_user_id=42, discord_username="damien")
    player = Player.create(
        openfront_player_id="player-1",
        canonical_username="Ace",
        canonical_normalized_username="ace",
        is_linked=1,
    )
    PlayerLink.create(site_user=site_user, player=player, linked_at=datetime(2026, 3, 11))
    game = ObservedGame.create(openfront_game_id="game-1", game_type="PUBLIC")
    GameParticipant.create(
        game=game,
        guild=guild,
        raw_username="Ace",
        normalized_username="ace",
        raw_clan_tag="NRTH",
        effective_clan_tag="NRTH",
        clan_tag_source="api",
        client_id="client-1",
        did_win=1,
        player=player,
    )
    GuildPlayerAggregate.create(
        guild=guild,
        player=player,
        normalized_username="ace",
        display_username="Ace",
        win_count=1,
        game_count=1,
    )

    with pytest.raises(ValueError, match="confirmation"):
        delete_guild_site(build_guild_site_selector(slug="north-guild"), confirm=False)

    deleted = delete_guild_site(
        build_guild_site_selector(slug="north-guild"),
        confirm=True,
    )

    assert deleted is True
    assert Guild.select().count() == 0
    assert GuildClanTag.select().count() == 0
    assert GameParticipant.select().count() == 0
    assert GuildPlayerAggregate.select().count() == 0
    assert SiteUser.select().count() == 1
    assert Player.select().count() == 1
    assert PlayerLink.select().count() == 1
