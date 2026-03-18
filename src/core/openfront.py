from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import aiohttp

from .config import OpenFrontBypassConfig
from ..data.database import shared_database

OPENFRONT_BASE = "https://api.openfront.io"
OPENFRONT_LOBBY_BASE = "https://openfront.io/api"
PUBLIC_GAMES_MAX_RANGE = timedelta(days=2)
OPENFRONT_GATE_LEASE_SECONDS = 30.0
OPENFRONT_MAX_IN_FLIGHT = 2
OPENFRONT_GATE_WAIT_POLL_SECONDS = 0.05
OPENFRONT_SUCCESS_DELAY_SECONDS = 0.5
OPENFRONT_MIN_RATE_LIMIT_COOLDOWN_SECONDS = 1.0
OPENFRONT_RESET_HEADERS = (
    "ratelimit-reset",
    "x-ratelimit-reset",
    "x-ratelimit-reset-after",
)

LOGGER = logging.getLogger(__name__)
_LOCAL_GATE_LOCKS: dict[int, asyncio.Lock] = {}
_LOCAL_COOLDOWN_UNTIL: datetime | None = None
_LOCAL_ACTIVE_LEASES = 0
_LOCAL_LEASE_EXPIRES_AT: datetime | None = None


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value in (None, ""):
        return default
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _env_float(name: str, default: float, *, minimum: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value in (None, ""):
        return default
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _openfront_max_in_flight() -> int:
    return _env_int(
        "OPENFRONT_MAX_IN_FLIGHT",
        OPENFRONT_MAX_IN_FLIGHT,
        minimum=1,
    )


def _openfront_success_delay_seconds() -> float:
    return _env_float(
        "OPENFRONT_SUCCESS_DELAY_SECONDS",
        OPENFRONT_SUCCESS_DELAY_SECONDS,
        minimum=0.0,
    )


def _openfront_min_rate_limit_cooldown_seconds() -> float:
    return _env_float(
        "OPENFRONT_MIN_RATE_LIMIT_COOLDOWN_SECONDS",
        OPENFRONT_MIN_RATE_LIMIT_COOLDOWN_SECONDS,
        minimum=0.0,
    )


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


@dataclass(frozen=True)
class OpenFrontRateLimitEvent:
    status: int
    cooldown_seconds: float
    source: str
    url: str


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        pass

    try:
        retry_time = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None

    if retry_time.tzinfo is None:
        retry_time = retry_time.replace(tzinfo=timezone.utc)
    delta = retry_time.astimezone(timezone.utc) - datetime.now(timezone.utc)
    return max(delta.total_seconds(), 0.0)


def _parse_reset_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        raw_value = float(value)
    except (TypeError, ValueError):
        return None
    if raw_value < 0:
        return None
    current_epoch = datetime.now(timezone.utc).timestamp()
    if raw_value > current_epoch + 1:
        return max(raw_value - current_epoch, 0.0)
    return raw_value


def _response_cooldown_seconds(
    headers: Dict[str, str],
) -> tuple[float | None, str | None]:
    retry_after = _parse_retry_after(headers.get("retry-after"))
    if retry_after is not None:
        return retry_after, "retry-after"

    retry_after_ms = headers.get("retry-after-ms")
    if retry_after_ms is not None:
        try:
            return max(float(retry_after_ms) / 1000.0, 0.0), "retry-after-ms"
        except (TypeError, ValueError):
            pass

    for header_name in OPENFRONT_RESET_HEADERS:
        reset_after = _parse_reset_after(headers.get(header_name))
        if reset_after is not None:
            return reset_after, header_name
    return None, None


def _shared_database_available():
    return getattr(shared_database, "obj", None)


def _database_supports_for_update(database: object) -> bool:
    module_name = type(database).__module__.lower()
    class_name = type(database).__name__.lower()
    return "sqlite" not in module_name and "sqlite" not in class_name


def _get_local_gate_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    lock = _LOCAL_GATE_LOCKS.get(loop_id)
    if lock is None:
        lock = asyncio.Lock()
        _LOCAL_GATE_LOCKS[loop_id] = lock
    return lock


def _reset_local_leases_if_expired(now: datetime) -> None:
    global _LOCAL_ACTIVE_LEASES, _LOCAL_LEASE_EXPIRES_AT
    if _LOCAL_LEASE_EXPIRES_AT and _LOCAL_LEASE_EXPIRES_AT <= now:
        _LOCAL_ACTIVE_LEASES = 0
        _LOCAL_LEASE_EXPIRES_AT = None


def _local_wait_or_acquire() -> float:
    global _LOCAL_ACTIVE_LEASES, _LOCAL_LEASE_EXPIRES_AT
    now = _utcnow_naive()
    max_in_flight = _openfront_max_in_flight()
    _reset_local_leases_if_expired(now)
    if _LOCAL_COOLDOWN_UNTIL and _LOCAL_COOLDOWN_UNTIL > now:
        return (_LOCAL_COOLDOWN_UNTIL - now).total_seconds()
    if _LOCAL_ACTIVE_LEASES >= max_in_flight:
        if _LOCAL_LEASE_EXPIRES_AT and _LOCAL_LEASE_EXPIRES_AT > now:
            return min(
                (_LOCAL_LEASE_EXPIRES_AT - now).total_seconds(),
                OPENFRONT_GATE_WAIT_POLL_SECONDS,
            )
        _LOCAL_ACTIVE_LEASES = 0
    _LOCAL_ACTIVE_LEASES += 1
    _LOCAL_LEASE_EXPIRES_AT = now + timedelta(seconds=OPENFRONT_GATE_LEASE_SECONDS)
    return 0.0


def _release_local_gate(delay_seconds: float) -> None:
    global _LOCAL_ACTIVE_LEASES, _LOCAL_COOLDOWN_UNTIL, _LOCAL_LEASE_EXPIRES_AT
    now = _utcnow_naive()
    _reset_local_leases_if_expired(now)
    if _LOCAL_ACTIVE_LEASES > 0:
        _LOCAL_ACTIVE_LEASES -= 1
    _LOCAL_COOLDOWN_UNTIL = _utcnow_naive() + timedelta(
        seconds=max(delay_seconds, 0.0)
    )
    if _LOCAL_ACTIVE_LEASES > 0:
        _LOCAL_LEASE_EXPIRES_AT = now + timedelta(seconds=OPENFRONT_GATE_LEASE_SECONDS)
    else:
        _LOCAL_LEASE_EXPIRES_AT = None


def _shared_wait_or_acquire(owner_id: str) -> float | None:
    database = _shared_database_available()
    if database is None:
        return None

    from ..data.shared.models import OpenFrontRateLimitState

    database.connect(reuse_if_open=True)
    with database.atomic():
        OpenFrontRateLimitState.get_or_create(id=1)
        query = OpenFrontRateLimitState.select().where(
            OpenFrontRateLimitState.id == 1
        )
        if _database_supports_for_update(database):
            query = query.for_update()
        state = query.get()
        now = _utcnow_naive()
        max_in_flight = _openfront_max_in_flight()

        if state.lease_expires_at and state.lease_expires_at <= now:
            state.active_leases = 0
            state.lease_owner = None
            state.lease_expires_at = None

        if state.cooldown_until and state.cooldown_until > now:
            state.save()
            return (state.cooldown_until - now).total_seconds()

        if state.active_leases >= max_in_flight:
            if state.lease_expires_at and state.lease_expires_at > now:
                state.save()
                return min(
                    (state.lease_expires_at - now).total_seconds(),
                    OPENFRONT_GATE_WAIT_POLL_SECONDS,
                )
            state.active_leases = 0

        state.active_leases += 1
        state.lease_owner = owner_id
        state.lease_expires_at = now + timedelta(seconds=OPENFRONT_GATE_LEASE_SECONDS)
        state.save()
        return 0.0


def _release_shared_gate(owner_id: str, delay_seconds: float, reason: str) -> bool:
    database = _shared_database_available()
    if database is None:
        return False

    from ..data.shared.models import OpenFrontRateLimitState

    database.connect(reuse_if_open=True)
    with database.atomic():
        OpenFrontRateLimitState.get_or_create(id=1)
        query = OpenFrontRateLimitState.select().where(
            OpenFrontRateLimitState.id == 1
        )
        if _database_supports_for_update(database):
            query = query.for_update()
        state = query.get()
        now = _utcnow_naive()
        cooldown_until = now + timedelta(seconds=max(delay_seconds, 0.0))
        if state.lease_expires_at and state.lease_expires_at <= now:
            state.active_leases = 0
        if state.cooldown_until is None or cooldown_until > state.cooldown_until:
            state.cooldown_until = cooldown_until
            state.cooldown_reason = reason
        if state.active_leases > 0:
            state.active_leases -= 1
        if state.active_leases > 0:
            state.lease_expires_at = now + timedelta(seconds=OPENFRONT_GATE_LEASE_SECONDS)
        else:
            state.lease_owner = None
            state.lease_expires_at = None
        state.save()
    return True


class _OpenFrontGateLease:
    def __init__(self, owner_id: str, shared_gate: bool):
        self._owner_id = owner_id
        self._shared_gate = shared_gate
        self._released = False

    def release(self, delay_seconds: float, reason: str) -> None:
        if self._released:
            return
        try:
            if self._shared_gate:
                released = _release_shared_gate(self._owner_id, delay_seconds, reason)
                if not released:
                    _release_local_gate(delay_seconds)
            else:
                _release_local_gate(delay_seconds)
        except Exception as exc:
            LOGGER.warning(
                "Shared OpenFront gate release failed (%s). Falling back to local cooldown.",
                exc,
            )
            _release_local_gate(delay_seconds)
        self._released = True


async def _acquire_request_gate(owner_id: str) -> _OpenFrontGateLease:
    lock = _get_local_gate_lock()
    await lock.acquire()
    try:
        while True:
            try:
                shared_wait = _shared_wait_or_acquire(owner_id)
            except Exception as exc:
                LOGGER.warning(
                    "Shared OpenFront gate unavailable (%s). Falling back to local cooldown.",
                    exc,
                )
                shared_wait = None

            if shared_wait is None:
                local_wait = _local_wait_or_acquire()
                if local_wait <= 0:
                    lock.release()
                    return _OpenFrontGateLease(owner_id, False)
                lock.release()
                await asyncio.sleep(local_wait)
                await lock.acquire()
                continue

            if shared_wait <= 0:
                lock.release()
                return _OpenFrontGateLease(owner_id, True)

            lock.release()
            await asyncio.sleep(shared_wait)
            await lock.acquire()
    except Exception:
        if lock.locked():
            lock.release()
        raise


class OpenFrontClient:
    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        on_rate_limit: Callable[[OpenFrontRateLimitEvent], None] | None = None,
        bypass_header_name: str | None = None,
        bypass_header_value: str | None = None,
        user_agent: str | None = None,
        bypass_config: OpenFrontBypassConfig | None = None,
    ):
        self._session = session
        self._owns_session = session is None
        self._request_owner = f"{os.getpid()}:{uuid.uuid4().hex}"
        self._rate_limit_observers: list[Callable[[OpenFrontRateLimitEvent], None]] = []
        if on_rate_limit is not None:
            self._rate_limit_observers.append(on_rate_limit)
        if bypass_config is not None:
            bypass_header_name = bypass_config.bypass_header_name
            bypass_header_value = bypass_config.bypass_header_value
            user_agent = bypass_config.user_agent
        self._bypass_header_name = str(bypass_header_name or "").strip() or None
        self._bypass_header_value = str(bypass_header_value or "").strip() or None
        self._user_agent = str(user_agent or "").strip() or None

    async def close(self):
        if self._owns_session and self._session:
            await self._session.close()

    def add_rate_limit_observer(
        self,
        observer: Callable[[OpenFrontRateLimitEvent], None],
    ) -> Callable[[], None]:
        self._rate_limit_observers.append(observer)

        def remove() -> None:
            try:
                self._rate_limit_observers.remove(observer)
            except ValueError:
                return

        return remove

    def set_rate_limit_observer(
        self,
        observer: Callable[[OpenFrontRateLimitEvent], None] | None,
    ) -> Callable[[OpenFrontRateLimitEvent], None] | None:
        previous = self._rate_limit_observers[-1] if self._rate_limit_observers else None
        self._rate_limit_observers = [] if observer is None else [observer]
        return previous

    def _emit_rate_limit_event(
        self,
        *,
        status: int,
        cooldown_seconds: float,
        source: str,
        url: str,
    ) -> None:
        if status != 429:
            return
        event = OpenFrontRateLimitEvent(
            status=status,
            cooldown_seconds=cooldown_seconds,
            source=source,
            url=url,
        )
        for observer in list(self._rate_limit_observers):
            observer(event)

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
        request_headers: dict[str, str] = {}
        if self._bypass_header_name and self._bypass_header_value:
            request_headers[self._bypass_header_name] = self._bypass_header_value
        if self._user_agent:
            request_headers["User-Agent"] = self._user_agent
        if not request_headers:
            request_headers = None  # type: ignore[assignment]
        fail_fast = set(fail_fast_statuses or [])
        backoff = 1.0
        last_status: int | None = None
        for attempt in range(5):
            lease = (
                None
                if request_headers is not None
                else await _acquire_request_gate(self._request_owner)
            )
            try:
                async with self._session.request(
                    method,
                    url,
                    headers=request_headers,
                ) as resp:
                    headers = {
                        key.lower(): value for key, value in resp.headers.items()
                    }
                    rate_limit_delay, rate_limit_source = _response_cooldown_seconds(
                        headers
                    )
                    if resp.status in fail_fast:
                        if lease is not None:
                            lease.release(
                                rate_limit_delay or 0.0,
                                f"status:{resp.status}",
                            )
                        raise OpenFrontError(
                            f"Failed request {url}: {resp.status}",
                            resp.status,
                            retry_after=rate_limit_delay,
                        )
                    if resp.status in (429, 500, 502, 503, 504):
                        if request_headers is not None and resp.status == 429:
                            LOGGER.warning(
                                "OpenFront returned 429 while bypass header %s was configured; are you sure about your bypass key? url=%s",
                                self._bypass_header_name,
                                url,
                            )
                        if resp.status == 429:
                            retry_delay = max(
                                rate_limit_delay or 0.0,
                                _openfront_min_rate_limit_cooldown_seconds(),
                            )
                        else:
                            retry_delay = (
                                rate_limit_delay
                                if rate_limit_delay is not None
                                else backoff + random.random()
                            )
                        self._emit_rate_limit_event(
                            status=resp.status,
                            cooldown_seconds=retry_delay,
                            source=rate_limit_source or "fallback",
                            url=url,
                        )
                        if lease is not None:
                            lease.release(retry_delay, f"status:{resp.status}")
                        raise OpenFrontError(
                            f"Transient error {resp.status}",
                            resp.status,
                            retry_after=rate_limit_delay,
                        )
                    resp.raise_for_status()
                    if ignore_content_type:
                        payload = await resp.json(content_type=None)
                    else:
                        payload = await resp.json()
                    if lease is not None:
                        lease.release(
                            max(
                                rate_limit_delay or 0.0,
                                _openfront_success_delay_seconds(),
                            ),
                            "success",
                        )
                    return payload, headers
            except OpenFrontError as exc:
                last_status = exc.status or last_status
                if exc.status in fail_fast:
                    raise
                if request_headers is not None and exc.status == 429:
                    raise
                if exc.status == 429 and not retry_on_429:
                    raise
                if attempt == 4:
                    raise OpenFrontError(
                        f"Failed request {url}: {exc}",
                        status=last_status,
                        retry_after=exc.retry_after,
                    ) from exc
                backoff *= 2
                continue
            except Exception as exc:
                delay = backoff + random.random()
                if lease is not None:
                    lease.release(delay, "transport_error")
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
                backoff *= 2
                continue
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
        self,
        clan_tag: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> List[Dict[str, Any]]:
        params: list[str] = []
        if start is not None:
            params.append(f"start={_format_datetime(start)}")
        if end is not None:
            params.append(f"end={_format_datetime(end)}")
        suffix = f"?{'&'.join(params)}" if params else ""
        payload = await self._request(
            "GET",
            f"/public/clan/{clan_tag}/sessions{suffix}",
        )
        if isinstance(payload, list):
            return list(payload)
        if isinstance(payload, dict) and "data" in payload:
            return list(payload.get("data") or [])
        return []

    async def _fetch_public_games_window(
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

    async def fetch_public_games(
        self, start: datetime, end: datetime, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        if end < start:
            return []

        games: List[Dict[str, Any]] = []
        seen_game_ids: set[str] = set()
        window_start = start
        while True:
            window_end = min(window_start + PUBLIC_GAMES_MAX_RANGE, end)
            for game in await self._fetch_public_games_window(
                window_start, window_end, limit=limit
            ):
                game_id = game.get("game") if isinstance(game, dict) else None
                if game_id:
                    if game_id in seen_game_ids:
                        continue
                    seen_game_ids.add(game_id)
                games.append(game)
            if window_end >= end:
                break
            window_start = window_end
        return games

    async def fetch_game(
        self,
        game_id: str,
        *,
        include_turns: bool = False,
        retry_on_429: bool = True,
    ) -> Dict[str, Any]:
        suffix = "" if include_turns else "?turns=false"
        return await self._request(
            "GET",
            f"/public/game/{game_id}{suffix}",
            fail_fast_statuses={404},
            retry_on_429=retry_on_429,
        )

    async def fetch_public_lobbies(self) -> List[Dict[str, Any]]:
        payload = await self._request(
            "GET",
            "/public_lobbies",
            base=OPENFRONT_LOBBY_BASE,
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
