import asyncio
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from peewee import SqliteDatabase

from src.core import openfront as openfront_module
from src.data.database import shared_database
from src.data.shared.schema import bootstrap_shared_schema
from src.openfront import OpenFrontClient


class PagingClient(OpenFrontClient):
    def __init__(self, pages_by_offset, total):
        super().__init__(session=None)
        self.pages_by_offset = pages_by_offset
        self.total = total
        self.calls = []

    async def _request_with_headers(self, method, path):
        self.calls.append(path)
        parsed = urlparse(path)
        params = parse_qs(parsed.query)
        offset = int(params.get("offset", ["0"])[0])
        page = list(self.pages_by_offset.get(offset, []))
        if page:
            start = offset
            end = offset + len(page) - 1
        else:
            start = offset
            end = offset - 1
        header = f"games {start}-{end}/{self.total}"
        return page, {"content-range": header}


def test_fetch_public_games_paginates():
    pages = {0: [{"game": "g1"}, {"game": "g2"}], 2: [{"game": "g3"}]}
    client = PagingClient(pages, total=3)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)

    games = asyncio.run(client.fetch_public_games(start, start, limit=2))

    assert [game["game"] for game in games] == ["g1", "g2", "g3"]
    assert len(client.calls) == 2


class ChunkingClient(OpenFrontClient):
    def __init__(self):
        super().__init__(session=None)
        self.calls = []

    async def _request_with_headers(self, method, path):
        parsed = urlparse(path)
        params = parse_qs(parsed.query)
        start = datetime.fromisoformat(params["start"][0].replace("Z", "+00:00"))
        end = datetime.fromisoformat(params["end"][0].replace("Z", "+00:00"))
        offset = int(params.get("offset", ["0"])[0])
        self.calls.append((start, end, offset))
        page = {
            datetime(2025, 1, 1, tzinfo=timezone.utc): [
                {"game": "g1"},
                {"game": "shared"},
            ],
            datetime(2025, 1, 3, tzinfo=timezone.utc): [
                {"game": "shared"},
                {"game": "g2"},
            ],
        }.get(start, [])
        return page, {"content-range": f"games 0-{len(page) - 1}/{len(page)}"}


def test_fetch_public_games_chunks_large_ranges_and_deduplicates_boundaries():
    client = ChunkingClient()
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 1, 5, tzinfo=timezone.utc)

    games = asyncio.run(client.fetch_public_games(start, end, limit=1000))

    assert [game["game"] for game in games] == ["g1", "shared", "g2"]
    assert len(client.calls) == 2
    assert all(
        call_end - call_start <= timedelta(days=2)
        for call_start, call_end, _ in client.calls
    )


def setup_shared_database(tmp_path):
    database = SqliteDatabase(
        str(tmp_path / "openfront-shared.db"),
        check_same_thread=False,
    )
    shared_database.initialize(database)
    bootstrap_shared_schema(database)
    return database


class FakeClock:
    def __init__(self, current: datetime):
        self.current = current
        self.sleep_calls = []

    def now(self):
        return self.current

    async def sleep(self, delay: float):
        self.sleep_calls.append(delay)
        self.current += timedelta(seconds=delay)


class FakeResponse:
    def __init__(self, status, payload, headers=None):
        self.status = status
        self._payload = payload
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, content_type=None):
        return self._payload

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"unexpected status {self.status}")


class WaitingResponse(FakeResponse):
    def __init__(self, status, payload, started_event, release_event, headers=None):
        super().__init__(status, payload, headers=headers)
        self.started_event = started_event
        self.release_event = release_event

    async def __aenter__(self):
        self.started_event.set()
        await self.release_event.wait()
        return self


class QueueSession:
    def __init__(self, clock, responses):
        self.clock = clock
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url):
        self.requests.append((method, url, self.clock.now()))
        return self.responses.pop(0)

    async def close(self):
        return None


def test_parse_retry_after_accepts_http_date():
    retry_time = datetime.now(timezone.utc) + timedelta(seconds=120)

    parsed = openfront_module._parse_retry_after(
        format_datetime(retry_time, usegmt=True)
    )

    assert parsed is not None
    assert 100 <= parsed <= 120


def test_fetch_game_retries_rate_limits_and_honors_retry_after(
    tmp_path, monkeypatch
):
    setup_shared_database(tmp_path)
    clock = FakeClock(datetime(2026, 3, 14, 0, 0, 0))
    session = QueueSession(
        clock,
        [
            FakeResponse(429, {"error": "rate limited"}, {"Retry-After": "3"}),
            FakeResponse(200, {"info": {"gameID": "g-rate"}}),
        ],
    )
    client = OpenFrontClient(session=session)

    monkeypatch.setattr(openfront_module, "_utcnow_naive", clock.now)
    monkeypatch.setattr(openfront_module.asyncio, "sleep", clock.sleep)

    payload = asyncio.run(client.fetch_game("g-rate"))

    assert payload["info"]["gameID"] == "g-rate"
    assert clock.sleep_calls == [3]
    assert len(session.requests) == 2
    assert session.requests[1][2] - session.requests[0][2] == timedelta(seconds=3)


def test_openfront_clients_allow_two_parallel_requests_and_throttle_third(
    tmp_path, monkeypatch
):
    setup_shared_database(tmp_path)
    clock = FakeClock(datetime(2026, 3, 14, 0, 0, 0))
    first_started = asyncio.Event()
    second_started = asyncio.Event()
    release_first_two = asyncio.Event()
    session_one = QueueSession(
        clock,
        [WaitingResponse(200, {"playerId": "p1"}, first_started, release_first_two)],
    )
    session_two = QueueSession(
        clock,
        [WaitingResponse(200, {"playerId": "p2"}, second_started, release_first_two)],
    )
    session_three = QueueSession(clock, [FakeResponse(200, {"playerId": "p3"})])
    client_one = OpenFrontClient(session=session_one)
    client_two = OpenFrontClient(session=session_two)
    client_three = OpenFrontClient(session=session_three)

    monkeypatch.setattr(openfront_module, "_utcnow_naive", clock.now)
    original_sleep = asyncio.sleep

    async def yielding_sleep(delay: float):
        await clock.sleep(delay)
        await original_sleep(0)

    monkeypatch.setattr(openfront_module.asyncio, "sleep", yielding_sleep)

    async def run_requests():
        async def release_once_first_two_started():
            await first_started.wait()
            await second_started.wait()
            release_first_two.set()

        return await asyncio.gather(
            release_once_first_two_started(),
            client_one.fetch_player("player-1"),
            client_two.fetch_player("player-2"),
            client_three.fetch_player("player-3"),
        )

    _, first, second, third = asyncio.run(run_requests())

    assert first["playerId"] == "p1"
    assert second["playerId"] == "p2"
    assert third["playerId"] == "p3"
    request_times = sorted(
        [
            session_one.requests[0][2],
            session_two.requests[0][2],
            session_three.requests[0][2],
        ]
    )
    assert request_times[1] - request_times[0] == timedelta(seconds=0)
    assert request_times[2] - request_times[1] >= timedelta(seconds=0.5)
    assert request_times[2] - request_times[1] < timedelta(seconds=1)
    assert max(clock.sleep_calls) == 0.5


def test_fetch_game_emits_rate_limit_event_with_retry_after(tmp_path, monkeypatch):
    setup_shared_database(tmp_path)
    clock = FakeClock(datetime(2026, 3, 14, 0, 0, 0))
    session = QueueSession(
        clock,
        [
            FakeResponse(429, {"error": "rate limited"}, {"Retry-After": "3"}),
            FakeResponse(200, {"info": {"gameID": "g-rate"}}),
        ],
    )
    events = []
    client = OpenFrontClient(session=session, on_rate_limit=events.append)

    monkeypatch.setattr(openfront_module, "_utcnow_naive", clock.now)
    monkeypatch.setattr(openfront_module.asyncio, "sleep", clock.sleep)

    payload = asyncio.run(client.fetch_game("g-rate"))

    assert payload["info"]["gameID"] == "g-rate"
    assert len(events) == 1
    assert events[0].status == 429
    assert events[0].cooldown_seconds == 3
    assert events[0].source == "retry-after"
