import asyncio
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

OPENFRONT_BASE = "https://api.openfront.io"
OPENFRONT_LOBBY_BASE = "https://openfront.io/api"


class OpenFrontError(Exception):
    def __init__(
        self,
        message: str,
        status: int | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


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


def _parse_content_range(
    value: str | None,
) -> Tuple[int | None, int | None, int | None]:
    if not value:
        return None, None, None
    match = re.match(r"^\s*\w+\s+(\d+)-(\d+)/(\d+|\*)\s*$", value)
    if not match:
        return None, None, None
    start = int(match.group(1))
    end = int(match.group(2))
    total_raw = match.group(3)
    total = None if total_raw == "*" else int(total_raw)
    return start, end, total


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class OpenFrontClient:
    def __init__(self, session: aiohttp.ClientSession | None = None):
        self._session = session
        self._owns_session = session is None

    async def close(self):
        if self._owns_session and self._session:
            await self._session.close()

    async def _request_with_headers(
        self,
        method: str,
        path: str,
        base: str | None = None,
        fail_fast_statuses: set[int] | None = None,
        retry_on_429: bool = True,
        ignore_content_type: bool = False,
    ) -> tuple[Any, Dict[str, str]]:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        if path.startswith("http"):
            url = path
        else:
            url = f"{base or OPENFRONT_BASE}{path}"
        fail_fast = set(fail_fast_statuses or [])
        backoff = 1.0
        last_status: int | None = None
        for attempt in range(5):
            try:
                async with self._session.request(method, url) as resp:
                    if resp.status == 429 and not retry_on_429:
                        retry_after = _parse_retry_after(
                            resp.headers.get("Retry-After")
                        )
                        raise OpenFrontError(
                            "Rate limited", resp.status, retry_after=retry_after
                        )
                    if resp.status in fail_fast:
                        raise OpenFrontError(
                            f"Failed request {url}: {resp.status}", resp.status
                        )
                    if resp.status in (429, 500, 502, 503, 504):
                        retry_after = None
                        if resp.status == 429:
                            retry_after = _parse_retry_after(
                                resp.headers.get("Retry-After")
                            )
                        raise OpenFrontError(
                            f"Transient error {resp.status}",
                            resp.status,
                            retry_after=retry_after,
                        )
                    resp.raise_for_status()
                    if ignore_content_type:
                        payload = await resp.json(content_type=None)
                    else:
                        payload = await resp.json()
                    headers = {
                        key.lower(): value for key, value in resp.headers.items()
                    }
                    return payload, headers
            except OpenFrontError as exc:
                status = exc.status
                last_status = status or last_status
                if status in fail_fast or (status == 429 and not retry_on_429):
                    raise
                if attempt == 4:
                    raise OpenFrontError(
                        f"Failed request {url}: {exc}",
                        status=last_status,
                        retry_after=exc.retry_after,
                    ) from exc
                if status == 429 and exc.retry_after:
                    await asyncio.sleep(exc.retry_after)
                else:
                    await asyncio.sleep(backoff + random.random())
                    backoff *= 2
            except Exception as exc:
                status = getattr(exc, "status", None)
                last_status = status or last_status
                if status in fail_fast:
                    raise OpenFrontError(
                        f"Failed request {url}: {exc}", status=status
                    ) from exc
                if attempt == 4:
                    raise OpenFrontError(
                        f"Failed request {url}: {exc}", status=last_status
                    ) from exc
                await asyncio.sleep(backoff + random.random())
                backoff *= 2
        return None, {}

    async def _request(
        self,
        method: str,
        path: str,
        base: str | None = None,
        fail_fast_statuses: set[int] | None = None,
        retry_on_429: bool = True,
        ignore_content_type: bool = False,
    ) -> Any:
        payload, _headers = await self._request_with_headers(
            method,
            path,
            base=base,
            fail_fast_statuses=fail_fast_statuses,
            retry_on_429=retry_on_429,
            ignore_content_type=ignore_content_type,
        )
        return payload

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

    async def fetch_public_games(
        self, start: datetime, end: datetime, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        start_str = _format_datetime(start)
        end_str = _format_datetime(end)
        offset = 0
        games: List[Dict[str, Any]] = []
        while True:
            path = (
                "/public/games"
                f"?start={start_str}&end={end_str}&type=Public"
                f"&limit={limit}&offset={offset}"
            )
            payload, headers = await self._request_with_headers("GET", path)
            if isinstance(payload, list):
                page = payload
            elif isinstance(payload, dict) and "data" in payload:
                page = list(payload.get("data") or [])
            else:
                break
            games.extend(page)
            start_idx, end_idx, total = _parse_content_range(
                headers.get("content-range")
            )
            if start_idx is None or end_idx is None:
                break
            if total is None:
                if not page or len(page) < limit:
                    break
                offset = end_idx + 1
                continue
            if end_idx + 1 >= total:
                break
            offset = end_idx + 1
        return games

    async def fetch_game(self, game_id: str) -> Dict[str, Any]:
        return await self._request(
            "GET",
            f"/public/game/{game_id}?turns=false",
            fail_fast_statuses={404},
            retry_on_429=False,
        )

    async def fetch_public_lobbies(self) -> List[Dict[str, Any]]:
        payload = await self._request(
            "GET",
            "/public_lobbies",
            base=OPENFRONT_LOBBY_BASE,
            retry_on_429=False,
            ignore_content_type=True,
        )
        if isinstance(payload, dict) and "lobbies" in payload:
            return list(payload.get("lobbies") or [])
        if isinstance(payload, list):
            return list(payload)
        return []

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
