import asyncio
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import aiohttp

OPENFRONT_BASE = "https://api.openfront.io"


class OpenFrontError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _parse_datetime(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


class OpenFrontClient:
    def __init__(self, session: aiohttp.ClientSession | None = None):
        self._session = session
        self._owns_session = session is None

    async def close(self):
        if self._owns_session and self._session:
            await self._session.close()

    async def _request(self, method: str, path: str) -> Any:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        url = f"{OPENFRONT_BASE}{path}"
        backoff = 1.0
        last_status: int | None = None
        for attempt in range(5):
            try:
                async with self._session.request(method, url) as resp:
                    if resp.status in (429, 500, 502, 503, 504):
                        raise OpenFrontError(
                            f"Transient error {resp.status}", resp.status
                        )
                    resp.raise_for_status()
                    return await resp.json()
            except Exception as exc:
                status = getattr(exc, "status", None)
                last_status = status or last_status
                if attempt == 4:
                    raise OpenFrontError(
                        f"Failed request {url}: {exc}", status=last_status
                    ) from exc
                await asyncio.sleep(backoff + random.random())
                backoff *= 2

    async def fetch_player(self, player_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/public/player/{player_id}")

    async def fetch_sessions(self, player_id: str) -> List[Dict[str, Any]]:
        # If pagination appears (e.g., next/offset), follow until exhausted.
        sessions: List[Dict[str, Any]] = []
        next_path = f"/public/player/{player_id}/sessions"
        while next_path:
            payload = await self._request("GET", next_path)
            if isinstance(payload, dict) and "data" in payload:
                data = payload.get("data") or []
                sessions.extend(data)
                next_path = payload.get("next")
                if next_path and next_path.startswith("http"):
                    next_path = next_path.replace(OPENFRONT_BASE, "")
            elif isinstance(payload, list):
                sessions.extend(payload)
                next_path = None
            else:
                break
        return sessions

    async def fetch_clan_sessions(
        self, clan_tag: str, start: datetime, end: datetime
    ) -> List[Dict[str, Any]]:
        tag = quote(str(clan_tag))
        start_str = _format_datetime(start)
        end_str = _format_datetime(end)
        path = f"/public/clan/{tag}/sessions?start={start_str}&end={end_str}"
        payload = await self._request("GET", path)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and "data" in payload:
            return list(payload.get("data") or [])
        return []

    async def fetch_game(self, game_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/public/game/{game_id}?turns=false")

    async def last_session_username(self, player_id: str) -> Optional[str]:
        sessions = await self.fetch_sessions(player_id)
        if not sessions:
            return None
        sessions.sort(
            key=lambda s: self.session_end_time(s) or datetime.min,
            reverse=True,
        )
        return sessions[0].get("username")

    @staticmethod
    def session_start_time(session: Dict[str, Any]) -> Optional[datetime]:
        return _parse_datetime(session.get("gameStart"))

    @staticmethod
    def session_end_time(session: Dict[str, Any]) -> Optional[datetime]:
        return _parse_datetime(session.get("gameEnd"))

    @staticmethod
    def session_win(session: Dict[str, Any]) -> bool:
        return bool(session.get("hasWon"))
