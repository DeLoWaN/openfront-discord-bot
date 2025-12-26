import asyncio
from datetime import datetime, timedelta, timezone

from src.wins import (
    compute_wins_sessions_since_link,
    compute_wins_sessions_with_clan,
    compute_wins_total,
)
from tests.fakes import FakeOpenFront


def test_compute_wins_total_sums_public_modes():
    data = {
        "stats": {
            "Public": {
                "Free For All": {"Medium": {"wins": 3}},
                "Team": {"Medium": {"wins": 7}},
            }
        }
    }
    client = FakeOpenFront(player_data=data)
    wins = asyncio.run(compute_wins_total(client, "player1"))
    assert wins == 10


def test_compute_wins_since_link_filters_by_start_time():
    now = datetime.now(timezone.utc)
    linked_at = (now - timedelta(days=1)).replace(tzinfo=None)
    sessions = [
        {"gameStart": (linked_at + timedelta(hours=2)).isoformat(), "hasWon": True},
        {"gameStart": (linked_at - timedelta(hours=2)).isoformat(), "hasWon": True},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_since_link(client, "p1", linked_at))
    assert wins == 1


def test_compute_wins_sessions_with_clan_matches_tags():
    sessions = [
        {"username": "[ABC]Player", "hasWon": True, "gameType": "Public"},
        {"username": "[ABC]Player", "hasWon": False, "gameType": "Public"},
        {"username": "Player[ABC]", "hasWon": True, "gameType": "Public"},
        {"username": "[XYZ]Other", "hasWon": True, "gameType": "Public"},
        {"username": "NoTag", "hasWon": True, "gameType": "Public"},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_with_clan(client, "p1", ["abc"]))
    assert wins == 2


def test_compute_wins_sessions_with_clan_requires_bracket_prefix():
    sessions = [
        {"username": "PlayerABCx", "hasWon": True, "gameType": "Public"},
        {"username": "xabcPlayer", "hasWon": True, "gameType": "Public"},
        {"username": "no_match_here", "hasWon": True, "gameType": "Public"},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_with_clan(client, "p1", ["abc"]))
    assert wins == 0


def test_compute_wins_sessions_with_clan_uses_clantag_field():
    sessions = [
        {
            "username": "irrelevant",
            "clanTag": "AbC",
            "hasWon": True,
            "gameType": "Public",
        },
        {
            "username": "[XYZ]Other",
            "clanTag": "xyz",
            "hasWon": True,
            "gameType": "Public",
        },
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_with_clan(client, "p1", ["abc"]))
    assert wins == 1


def test_compute_wins_total_handles_missing_fields():
    client = FakeOpenFront(player_data={})
    wins = asyncio.run(compute_wins_total(client, "player1"))
    assert wins == 0


def test_compute_wins_sessions_since_link_skips_missing_start_or_losses():
    now = datetime.now(timezone.utc)
    linked_at = (now - timedelta(days=1)).replace(tzinfo=None)
    sessions = [
        {
            "gameStart": None,
            "gameEnd": (linked_at + timedelta(hours=1)).isoformat(),
            "hasWon": True,
        },  # uses fallback to end time
        {"gameStart": (linked_at - timedelta(hours=2)).isoformat(), "hasWon": True},
        {"gameStart": (linked_at + timedelta(hours=2)).isoformat(), "hasWon": False},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_since_link(client, "p1", linked_at))
    assert wins == 1


def test_compute_wins_sessions_with_clan_matches_case_insensitive_anywhere():
    sessions = [
        {"username": "player[abc]end", "hasWon": True, "gameType": "Public"},
        {
            "username": "PREFIX[XYZ]",
            "hasWon": True,
            "clanTag": None,
            "gameType": "Public",
        },
        {"username": "note", "clanTag": "xyz", "hasWon": True, "gameType": "Public"},
        {"username": "no_match", "hasWon": True, "gameType": "Public"},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_with_clan(client, "p1", ["AbC", "xYz"]))
    assert wins == 3


def test_compute_wins_sessions_with_clan_only_counts_public():
    sessions = [
        {"username": "[ABC]PublicWin", "hasWon": True, "gameType": "Public"},
        {"username": "[ABC]RankedWin", "hasWon": True, "gameType": "Ranked"},
        {"username": "[ABC]PublicLoss", "hasWon": False, "gameType": "Public"},
        {"username": "[XYZ]PublicWin", "hasWon": True, "gameType": "Public"},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_with_clan(client, "p1", ["abc"]))
    assert wins == 1


def test_compute_wins_sessions_with_clan_without_configured_tags_requires_clantag():
    sessions = [
        {"username": "[ABC]Player", "hasWon": True, "gameType": "Public"},
        {"username": "tagless", "hasWon": True, "gameType": "Public"},
        {
            "username": "has_clantag",
            "clanTag": "abc",
            "hasWon": True,
            "gameType": "Public",
        },
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_with_clan(client, "p1", []))
    assert wins == 2
