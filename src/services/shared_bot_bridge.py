from __future__ import annotations

from typing import Dict, List

from ..core.config import BotConfig
from ..data.database import init_shared_database, shared_database
from ..data.shared.models import PlayerAlias, PlayerLink, SiteUser
from ..data.shared.schema import bootstrap_shared_schema
from .player_linking import link_site_user_to_player, unlink_site_user_player

_shared_bot_bridge_enabled = False


def shared_backend_ready() -> bool:
    return _shared_bot_bridge_enabled and getattr(shared_database, "obj", None) is not None


def set_shared_bot_bridge_enabled(enabled: bool) -> None:
    global _shared_bot_bridge_enabled
    _shared_bot_bridge_enabled = bool(enabled)


def bootstrap_shared_backend(config: BotConfig) -> bool:
    set_shared_bot_bridge_enabled(False)
    if not config.mariadb:
        return False
    database = init_shared_database(config.mariadb, connect=False)
    bootstrap_shared_schema(database)
    set_shared_bot_bridge_enabled(True)
    return True


def merge_shared_openfront_username_index(
    index: Dict[str, List[int]],
) -> Dict[str, List[int]]:
    if not shared_backend_ready():
        return index
    merged: dict[str, set[int]] = {
        username: set(user_ids) for username, user_ids in index.items()
    }
    query = PlayerLink.select(PlayerLink, SiteUser).join(SiteUser)
    for link in query:
        usernames = {link.player.canonical_username}
        aliases = PlayerAlias.select().where(PlayerAlias.player == link.player)
        usernames.update(alias.raw_username for alias in aliases)
        for username in usernames:
            if not username:
                continue
            merged.setdefault(username, set()).add(link.site_user.discord_user_id)
    return {username: sorted(user_ids) for username, user_ids in merged.items()}


async def mirror_legacy_bot_link(
    *,
    discord_user_id: int,
    display_name: str | None,
    player_id: str,
    client,
) -> None:
    if not shared_backend_ready():
        return
    site_user = SiteUser.get_or_none(SiteUser.discord_user_id == discord_user_id)
    if site_user is None:
        site_user = SiteUser.create(
            discord_user_id=discord_user_id,
            discord_username=display_name or f"discord-{discord_user_id}",
        )
    else:
        if display_name:
            site_user.discord_username = display_name
            site_user.save()
    await link_site_user_to_player(site_user, player_id, client)


def mirror_legacy_bot_unlink(discord_user_id: int) -> None:
    if not shared_backend_ready():
        return
    site_user = SiteUser.get_or_none(SiteUser.discord_user_id == discord_user_id)
    if site_user is None:
        return
    unlink_site_user_player(site_user)
