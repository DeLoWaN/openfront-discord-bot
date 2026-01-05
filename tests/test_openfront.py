import asyncio
from datetime import datetime, timezone
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
