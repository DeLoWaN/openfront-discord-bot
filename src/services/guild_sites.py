from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from ..data.shared.models import Guild, GuildClanTag

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_CLAN_TAG_RE = re.compile(r"^[A-Z]+$")
_UNSET = object()


@dataclass(frozen=True)
class GuildSiteSelector:
    guild_id: int | None = None
    slug: str | None = None
    subdomain: str | None = None


def normalize_slug(value: str) -> str:
    slug = _SLUG_RE.sub("-", str(value).strip().lower()).strip("-")
    if not slug:
        raise ValueError("Guild slug must not be empty")
    return slug


def normalize_subdomain(value: str) -> str:
    subdomain = normalize_slug(value)
    if "." in subdomain:
        raise ValueError("Guild subdomain must not contain dots")
    return subdomain


def normalize_clan_tag(value: str) -> str:
    tag = str(value).strip().upper()
    if not tag:
        raise ValueError("Clan tag must not be empty")
    if not _CLAN_TAG_RE.fullmatch(tag):
        raise ValueError("Clan tag must contain only letters A-Z")
    return tag


def build_guild_site_selector(
    *,
    guild_id: int | None = None,
    slug: str | None = None,
    subdomain: str | None = None,
) -> GuildSiteSelector:
    values = [
        value
        for value in (
            guild_id,
            str(slug).strip() if slug is not None else None,
            str(subdomain).strip() if subdomain is not None else None,
        )
        if value not in (None, "")
    ]
    if len(values) != 1:
        raise ValueError("Guild selector must provide exactly one of id, slug, or subdomain")
    return GuildSiteSelector(
        guild_id=guild_id,
        slug=normalize_slug(slug) if slug not in (None, "") else None,
        subdomain=normalize_subdomain(subdomain) if subdomain not in (None, "") else None,
    )


def extract_subdomain(host: str | None) -> str | None:
    if not host:
        return None
    hostname = host.split(":", 1)[0].strip().lower()
    if not hostname or hostname in {"localhost", "127.0.0.1"}:
        return None
    return hostname.split(".", 1)[0]


def _apply_guild_fields(
    guild: Guild,
    *,
    slug: str,
    subdomain: str,
    display_name: str,
    is_active: bool,
    discord_guild_id: int | None,
) -> Guild:
    normalized_slug = normalize_slug(slug)
    normalized_subdomain = normalize_subdomain(subdomain)
    clean_name = str(display_name).strip()
    if not clean_name:
        raise ValueError("Guild display name must not be empty")
    guild.slug = normalized_slug
    guild.subdomain = normalized_subdomain
    guild.display_name = clean_name
    guild.is_active = 1 if is_active else 0
    guild.discord_guild_id = discord_guild_id
    return guild


def _sync_guild_clan_tags(guild: Guild, clan_tags: Iterable[str]) -> None:
    desired_tags = {normalize_clan_tag(tag) for tag in clan_tags}
    existing_tags = {
        row.tag_text: row for row in GuildClanTag.select().where(GuildClanTag.guild == guild)
    }
    for obsolete_tag in sorted(set(existing_tags) - desired_tags):
        existing_tags[obsolete_tag].delete_instance()
    for tag in sorted(desired_tags - set(existing_tags)):
        GuildClanTag.create(guild=guild, tag_text=tag)


def _find_duplicate_guild(
    *,
    slug: str | None = None,
    subdomain: str | None = None,
    discord_guild_id: int | None | object = _UNSET,
    exclude_guild_id: int | None = None,
) -> Guild | None:
    candidates = []
    if slug is not None:
        candidates.append(Guild.get_or_none(Guild.slug == normalize_slug(slug)))
    if subdomain is not None:
        candidates.append(
            Guild.get_or_none(Guild.subdomain == normalize_subdomain(subdomain))
        )
    if discord_guild_id is not _UNSET and discord_guild_id is not None:
        candidates.append(
            Guild.get_or_none(Guild.discord_guild_id == int(discord_guild_id))
        )
    for candidate in candidates:
        if candidate is None:
            continue
        if exclude_guild_id is not None and candidate.id == exclude_guild_id:
            continue
        return candidate
    return None


def list_guild_sites() -> list[Guild]:
    return list(Guild.select().order_by(Guild.slug))


def get_guild_site(selector: GuildSiteSelector) -> Guild | None:
    if selector.guild_id is not None:
        return Guild.get_or_none(Guild.id == selector.guild_id)
    if selector.slug is not None:
        return Guild.get_or_none(Guild.slug == selector.slug)
    if selector.subdomain is not None:
        return Guild.get_or_none(Guild.subdomain == selector.subdomain)
    raise ValueError("Guild selector must provide exactly one of id, slug, or subdomain")


def _require_guild_site(selector: GuildSiteSelector) -> Guild:
    guild = get_guild_site(selector)
    if guild is None:
        raise ValueError("Guild site not found")
    return guild


def create_guild_site(
    *,
    slug: str,
    subdomain: str,
    display_name: str,
    clan_tags: Iterable[str] | None = None,
    is_active: bool = True,
    discord_guild_id: int | None = None,
) -> Guild:
    duplicate = _find_duplicate_guild(
        slug=slug,
        subdomain=subdomain,
        discord_guild_id=discord_guild_id,
    )
    if duplicate is not None:
        raise ValueError("Guild site already exists for one of the provided identifiers")

    guild = _apply_guild_fields(
        Guild(),
        slug=slug,
        subdomain=subdomain,
        display_name=display_name,
        is_active=is_active,
        discord_guild_id=discord_guild_id,
    )
    guild.save(force_insert=True)
    if clan_tags is not None:
        _sync_guild_clan_tags(guild, clan_tags)
    return guild


def update_guild_site(
    selector: GuildSiteSelector,
    *,
    slug: str | None = None,
    subdomain: str | None = None,
    display_name: str | None = None,
    clan_tags: Iterable[str] | None | object = _UNSET,
    is_active: bool | None = None,
    discord_guild_id: int | None | object = _UNSET,
) -> Guild:
    guild = _require_guild_site(selector)
    next_slug = guild.slug if slug is None else slug
    next_subdomain = guild.subdomain if subdomain is None else subdomain
    next_display_name = guild.display_name if display_name is None else display_name
    next_is_active = bool(guild.is_active) if is_active is None else is_active
    next_discord_guild_id = (
        guild.discord_guild_id if discord_guild_id is _UNSET else discord_guild_id
    )

    duplicate = _find_duplicate_guild(
        slug=next_slug,
        subdomain=next_subdomain,
        discord_guild_id=next_discord_guild_id,
        exclude_guild_id=guild.id,
    )
    if duplicate is not None:
        raise ValueError("Guild site already exists for one of the provided identifiers")

    _apply_guild_fields(
        guild,
        slug=next_slug,
        subdomain=next_subdomain,
        display_name=next_display_name,
        is_active=next_is_active,
        discord_guild_id=(
            None if next_discord_guild_id is _UNSET else next_discord_guild_id
        ),
    )
    guild.save()
    if clan_tags is not _UNSET:
        _sync_guild_clan_tags(guild, [] if clan_tags is None else clan_tags)
    return guild


def set_guild_site_active(selector: GuildSiteSelector, *, is_active: bool) -> Guild:
    return update_guild_site(selector, is_active=is_active)


def delete_guild_site(selector: GuildSiteSelector, *, confirm: bool) -> bool:
    if not confirm:
        raise ValueError("Guild site deletion requires explicit confirmation")
    guild = _require_guild_site(selector)
    return bool(guild.delete_instance(recursive=True))


def provision_guild_site(
    *,
    slug: str,
    subdomain: str,
    display_name: str,
    clan_tags: Iterable[str] | None = None,
    is_active: bool = True,
    discord_guild_id: int | None = None,
) -> Guild:
    normalized_slug = normalize_slug(slug)
    normalized_subdomain = normalize_subdomain(subdomain)
    guild = Guild.get_or_none(Guild.slug == normalized_slug)
    if guild is None:
        guild = Guild.get_or_none(Guild.subdomain == normalized_subdomain)
    if guild is None and discord_guild_id is not None:
        guild = Guild.get_or_none(Guild.discord_guild_id == discord_guild_id)

    if guild is None:
        guild = create_guild_site(
            slug=normalized_slug,
            subdomain=normalized_subdomain,
            display_name=display_name,
            clan_tags=clan_tags,
            is_active=is_active,
            discord_guild_id=discord_guild_id,
        )
    else:
        _apply_guild_fields(
            guild,
            slug=normalized_slug,
            subdomain=normalized_subdomain,
            display_name=display_name,
            is_active=is_active,
            discord_guild_id=discord_guild_id,
        )
        guild.save()
        if clan_tags is not None:
            _sync_guild_clan_tags(guild, clan_tags)

    return guild


def list_guild_clan_tags(guild: Guild) -> list[str]:
    return sorted(
        row.tag_text
        for row in GuildClanTag.select()
        .where(GuildClanTag.guild == guild)
        .order_by(GuildClanTag.tag_text)
    )


def resolve_guild_site(subdomain: str | None) -> Guild | None:
    if not subdomain:
        return None
    guild = Guild.get_or_none(Guild.subdomain == normalize_subdomain(subdomain))
    if guild is None or not bool(guild.is_active):
        return None
    return guild


def resolve_guild_site_for_host(host: str | None) -> Guild | None:
    return resolve_guild_site(extract_subdomain(host))
