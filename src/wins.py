from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Iterable, Optional, Protocol

from .openfront import OpenFrontClient


class OpenFrontLike(Protocol):
    async def fetch_player(self, player_id: str) -> dict[str, Any]: ...

    async def fetch_sessions(self, player_id: str) -> Iterable[dict[str, Any]]: ...

    @staticmethod
    def session_end_time(session: dict[str, Any]) -> datetime | None: ...

    @staticmethod
    def session_win(session: dict[str, Any]) -> bool: ...

    async def last_session_username(self, player_id: str) -> Optional[str]: ...


LOGGER = logging.getLogger(__name__)


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
    wins = 0
    for session in sessions:
        end_time = client.session_end_time(session)
        if not end_time:
            continue
        if end_time >= linked_at and client.session_win(session):
            wins += 1
    return wins


async def compute_wins_sessions_with_clan(
    client: OpenFrontLike,
    player_id: str,
    clan_tags: Iterable[str],
) -> int:
    sessions = list(await client.fetch_sessions(player_id))
    normalized_tags = [tag.upper() for tag in clan_tags]
    wins = 0
    for session in sessions:
        if "clanTag" not in session:
            match = re.search(
                r"\[([A-Za-z0-9]+)\]", session.get("username", ""), re.IGNORECASE
            )
            clan_tag = match.group(1).upper() if match else ""
        else:
            clan_tag = str(session.get("clanTag", "")).upper()
        if clan_tag == "":
            continue
        if normalized_tags and clan_tag not in normalized_tags:
            continue
        if client.session_win(session):
            wins += 1
    LOGGER.info(
        "Clan wins for %s: %s wins across %s sessions (tags=%s)",
        player_id,
        wins,
        len(sessions),
        normalized_tags or "any",
    )
    return wins


async def last_session_username(client: OpenFrontLike, player_id: str) -> Optional[str]:
    return await client.last_session_username(player_id)
