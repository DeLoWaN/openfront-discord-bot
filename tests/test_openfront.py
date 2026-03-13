import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

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
