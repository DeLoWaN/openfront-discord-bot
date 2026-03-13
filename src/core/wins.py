from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Iterable, Optional, Protocol, Sequence

from .openfront import OpenFrontClient


class OpenFrontLike(Protocol):
    async def fetch_player(self, player_id: str) -> dict[str, Any]: ...

    async def fetch_sessions(self, player_id: str) -> Iterable[dict[str, Any]]: ...

    @staticmethod
    def session_start_time(session: dict[str, Any]) -> datetime | None: ...

    @staticmethod
    def session_end_time(session: dict[str, Any]) -> datetime | None: ...

    @staticmethod
    def session_win(session: dict[str, Any]) -> bool: ...

    async def last_session_username(self, player_id: str) -> Optional[str]: ...


LOGGER = logging.getLogger(__name__)

_HUMANS_VS_NATIONS_LABEL = "Humans Vs Nations"


def is_humans_vs_nations(player_teams: Any) -> bool:
    return isinstance(player_teams, str) and player_teams == _HUMANS_VS_NATIONS_LABEL


async def compute_wins_total(client: OpenFrontLike, player_id: str) -> int:
    data = await client.fetch_player(player_id)
    public_stats = (
        data.get("stats", {}).get("Public", {}) if isinstance(data, dict) else {}
    )
    ffa_wins = int(
        public_stats.get("Free For All", {}).get("Medium", {}).get("wins", 0) or 0
    )
    team_wins = int(public_stats.get("Team", {}).get("Medium", {}).get("wins", 0) or 0)
    return ffa_wins + team_wins


async def compute_wins_sessions_since_link(
    client: OpenFrontLike,
    player_id: str,
    linked_at: datetime,
) -> int:
    sessions = await client.fetch_sessions(player_id)
    return compute_wins_sessions_since_link_from_sessions(client, sessions, linked_at)


async def compute_wins_sessions_with_clan(
    client: OpenFrontLike,
    player_id: str,
    clan_tags: Iterable[str],
) -> int:
    sessions = list(await client.fetch_sessions(player_id))
    return compute_wins_sessions_with_clan_from_sessions(client, sessions, clan_tags)


def compute_wins_sessions_since_link_from_sessions(
    client: OpenFrontLike,
    sessions: Sequence[dict[str, Any]],
    linked_at: datetime,
) -> int:
    wins = 0
    for session in sessions:
        if is_humans_vs_nations(session.get("playerTeams")):
            continue
        # Prefer gameStart; fall back to gameEnd if start is missing.
        start_time = client.session_start_time(session)
        if not start_time:
            start_time = client.session_end_time(session)
        if not start_time:
            continue
        if start_time >= linked_at and client.session_win(session):
            wins += 1
    return wins


def compute_wins_sessions_with_clan_from_sessions(
    client: OpenFrontLike,
    sessions: Sequence[dict[str, Any]],
    clan_tags: Iterable[str],
) -> int:
    normalized_tags = [tag.upper() for tag in clan_tags]
    wins = 0
    for session in sessions:
        if is_humans_vs_nations(session.get("playerTeams")):
            continue
        game_type = session.get("gameType")
        if str(game_type).upper() != "PUBLIC":
            continue
        raw_clan_tag = session.get("clanTag")
        if raw_clan_tag is None or raw_clan_tag == "":
            match = re.search(
                r"\[([A-Za-z0-9]+)\]", session.get("username", ""), re.IGNORECASE
            )
            clan_tag = match.group(1).upper() if match else ""
        else:
            clan_tag = str(raw_clan_tag).upper()
        if clan_tag == "":
            continue
        if normalized_tags and clan_tag not in normalized_tags:
            continue
        if client.session_win(session):
            wins += 1
    LOGGER.debug(
        "Clan wins: %s wins across %s sessions (tags=%s)",
        wins,
        len(sessions),
        normalized_tags or "any",
    )
    return wins


def last_session_username_from_sessions(
    client: OpenFrontLike,
    sessions: Sequence[dict[str, Any]],
) -> Optional[str]:
    if not sessions:
        return None
    sorted_sessions = sorted(
        sessions,
        key=lambda s: client.session_end_time(s)
        or client.session_start_time(s)
        or datetime.min,
        reverse=True,
    )
    return sorted_sessions[0].get("username")


async def last_session_username(client: OpenFrontLike, player_id: str) -> Optional[str]:
    return await client.last_session_username(player_id)
