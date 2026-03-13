from __future__ import annotations

from dataclasses import dataclass

from ..central_db import init_central_db, list_active_guilds
from ..models import init_guild_db
from ..data.shared.models import Guild, Player, PlayerAlias, PlayerLink, SiteUser
from .guild_sites import provision_guild_site


@dataclass(frozen=True)
class LegacyMigrationSummary:
    guilds_migrated: int
    users_migrated: int


def _placeholder_slug(guild_id: int) -> str:
    return f"discord-{guild_id}"


def migrate_legacy_sqlite_to_shared(central_database_path: str) -> LegacyMigrationSummary:
    init_central_db(central_database_path)
    guilds_migrated = 0
    users_migrated = 0

    for entry in list_active_guilds():
        guild_id = int(entry.guild_id)
        legacy_models = init_guild_db(str(entry.database_path), guild_id)
        existing_guild = Guild.get_or_none(Guild.discord_guild_id == guild_id)
        clan_tags = [row.tag_text for row in legacy_models.ClanTag.select()]
        if existing_guild is None:
            guild = provision_guild_site(
                slug=_placeholder_slug(guild_id),
                subdomain=_placeholder_slug(guild_id),
                display_name=f"Discord Guild {guild_id}",
                clan_tags=clan_tags,
                discord_guild_id=guild_id,
            )
        else:
            guild = provision_guild_site(
                slug=existing_guild.slug,
                subdomain=existing_guild.subdomain,
                display_name=existing_guild.display_name,
                clan_tags=clan_tags,
                is_active=bool(existing_guild.is_active),
                discord_guild_id=guild_id,
            )

        guilds_migrated += 1

        for legacy_user in legacy_models.User.select():
            site_user = SiteUser.get_or_none(
                SiteUser.discord_user_id == legacy_user.discord_user_id
            )
            if site_user is None:
                site_user = SiteUser.create(
                    discord_user_id=legacy_user.discord_user_id,
                    discord_username=legacy_user.last_username
                    or f"discord-{legacy_user.discord_user_id}",
                )
            else:
                if legacy_user.last_username:
                    site_user.discord_username = legacy_user.last_username
                    site_user.save()

            player = Player.get_or_none(Player.openfront_player_id == legacy_user.player_id)
            canonical_username = (
                legacy_user.last_openfront_username
                or legacy_user.player_id
            )
            if player is None:
                player = Player.create(
                    openfront_player_id=legacy_user.player_id,
                    canonical_username=canonical_username,
                    canonical_normalized_username=canonical_username.strip().lower(),
                    is_linked=1,
                )
            else:
                player.canonical_username = canonical_username
                player.canonical_normalized_username = canonical_username.strip().lower()
                player.is_linked = 1
                player.save()

            PlayerLink.insert(
                site_user=site_user,
                player=player,
                linked_at=legacy_user.linked_at,
            ).on_conflict(
                conflict_target=[PlayerLink.site_user],
                update={
                    PlayerLink.player: player,
                    PlayerLink.linked_at: legacy_user.linked_at,
                },
            ).execute()

            if legacy_user.last_openfront_username:
                PlayerAlias.insert(
                    player=player,
                    raw_username=legacy_user.last_openfront_username,
                    normalized_username=legacy_user.last_openfront_username.strip().lower(),
                    source="legacy_migration",
                ).on_conflict_ignore().execute()

            users_migrated += 1

    return LegacyMigrationSummary(
        guilds_migrated=guilds_migrated,
        users_migrated=users_migrated,
    )
