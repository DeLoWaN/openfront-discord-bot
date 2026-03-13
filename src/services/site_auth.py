from __future__ import annotations

from ..data.shared.models import SiteUser


def get_site_user(site_user_id: int | None) -> SiteUser | None:
    if not site_user_id:
        return None
    return SiteUser.get_or_none(SiteUser.id == int(site_user_id))


def upsert_site_user_from_discord(discord_user: dict[str, str]) -> SiteUser:
    discord_user_id = int(discord_user["id"])
    site_user = SiteUser.get_or_none(SiteUser.discord_user_id == discord_user_id)
    if site_user is None:
        site_user = SiteUser.create(
            discord_user_id=discord_user_id,
            discord_username=discord_user.get("username") or str(discord_user_id),
            discord_global_name=discord_user.get("global_name"),
            discord_avatar_hash=discord_user.get("avatar"),
        )
    else:
        site_user.discord_username = discord_user.get("username") or site_user.discord_username
        site_user.discord_global_name = discord_user.get("global_name")
        site_user.discord_avatar_hash = discord_user.get("avatar")
        site_user.save()
    return site_user
