from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..data.shared.models import (
    GameParticipant,
    Guild,
    GuildPlayerAggregate,
    Player,
    PlayerAlias,
    PlayerLink,
    SiteUser,
)
from .guild_sites import list_guild_clan_tags
from .openfront_ingestion import normalize_username, refresh_guild_player_aggregates, resolve_effective_clan_tag


@dataclass(frozen=True)
class LinkedProfileStats:
    guild_win_count: int
    guild_game_count: int
    global_public_wins: int
    aliases: list[str]


def _latest_username_from_sessions(sessions: list[dict[str, Any]]) -> str | None:
    def _session_time(session: dict[str, Any]) -> datetime:
        raw = session.get("gameEnd") or session.get("gameStart") or ""
        if isinstance(raw, str) and raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(raw)
        except Exception:
            return datetime.min

    if not sessions:
        return None
    latest = max(sessions, key=_session_time)
    username = str(latest.get("username") or "").strip()
    return username or None


def _public_wins_from_player_payload(payload: dict[str, Any]) -> int:
    public_stats = payload.get("stats", {}).get("Public", {})
    ffa = int(public_stats.get("Free For All", {}).get("Medium", {}).get("wins", 0) or 0)
    team = int(public_stats.get("Team", {}).get("Medium", {}).get("wins", 0) or 0)
    return ffa + team


def _clear_player_associations(player: Player) -> set[int]:
    affected_guild_ids = {
        row.guild_id
        for row in GameParticipant.select(GameParticipant.guild_id).where(
            GameParticipant.player == player
        )
    }
    GameParticipant.update(player=None).where(GameParticipant.player == player).execute()
    GuildPlayerAggregate.update(player=None).where(
        GuildPlayerAggregate.player == player
    ).execute()
    return affected_guild_ids


async def link_site_user_to_player(
    site_user: SiteUser,
    player_id: str,
    client: Any,
) -> Player:
    clean_player_id = str(player_id or "").strip()
    if not clean_player_id:
        raise ValueError("player_id must not be empty")

    player_payload = await client.fetch_player(clean_player_id)
    sessions = list(await client.fetch_sessions(clean_player_id))
    latest_username = _latest_username_from_sessions(sessions) or clean_player_id

    player = Player.get_or_none(Player.openfront_player_id == clean_player_id)
    if player is None:
        player = Player.create(
            openfront_player_id=clean_player_id,
            canonical_username=latest_username,
            canonical_normalized_username=normalize_username(latest_username),
            is_linked=1,
        )
    else:
        player.canonical_username = latest_username
        player.canonical_normalized_username = normalize_username(latest_username)
        player.is_linked = 1
        player.save()

    current_link = PlayerLink.get_or_none(PlayerLink.site_user == site_user)
    affected_guild_ids: set[int] = set()
    if current_link and current_link.player_id != player.id:
        affected_guild_ids.update(_clear_player_associations(current_link.player))
        current_link.player = player
        current_link.save()
    elif current_link is None:
        PlayerLink.create(site_user=site_user, player=player)

    PlayerAlias.delete().where(PlayerAlias.player == player).execute()
    aliases = sorted(
        {
            str(session.get("username") or "").strip()
            for session in sessions
            if str(session.get("username") or "").strip()
        }
    )
    for alias in aliases:
        PlayerAlias.create(
            player=player,
            raw_username=alias,
            normalized_username=normalize_username(alias),
            source="linked_history",
        )

    if aliases:
        matching_query = GameParticipant.select(GameParticipant.guild_id).where(
            GameParticipant.raw_username.in_(aliases)
        )
        affected_guild_ids.update(row.guild_id for row in matching_query)
        GameParticipant.update(player=player).where(
            GameParticipant.raw_username.in_(aliases)
        ).execute()

    for guild_id in affected_guild_ids:
        refresh_guild_player_aggregates(guild_id)

    return player


def unlink_site_user_player(site_user: SiteUser) -> None:
    link = PlayerLink.get_or_none(PlayerLink.site_user == site_user)
    if link is None:
        return
    affected_guild_ids = _clear_player_associations(link.player)
    link.delete_instance()
    for guild_id in affected_guild_ids:
        refresh_guild_player_aggregates(guild_id)


async def compute_linked_profile_stats(
    player: Player,
    guild: Guild,
    client: Any,
) -> LinkedProfileStats:
    if not player.openfront_player_id:
        return LinkedProfileStats(0, 0, 0, [])

    player_payload = await client.fetch_player(player.openfront_player_id)
    sessions = list(await client.fetch_sessions(player.openfront_player_id))
    guild_tags = set(list_guild_clan_tags(guild))
    aliases = sorted(
        {
            str(session.get("username") or "").strip()
            for session in sessions
            if str(session.get("username") or "").strip()
        }
    )

    guild_game_count = 0
    guild_win_count = 0
    for session in sessions:
        if str(session.get("gameType") or "").upper() != "PUBLIC":
            continue
        resolution = resolve_effective_clan_tag(
            session.get("clanTag"),
            session.get("username"),
        )
        if not resolution.effective_tag or resolution.effective_tag not in guild_tags:
            continue
        guild_game_count += 1
        if bool(session.get("hasWon") or session.get("won")):
            guild_win_count += 1

    return LinkedProfileStats(
        guild_win_count=guild_win_count,
        guild_game_count=guild_game_count,
        global_public_wins=_public_wins_from_player_payload(player_payload),
        aliases=aliases,
    )
