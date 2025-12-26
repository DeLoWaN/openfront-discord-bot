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


def test_compute_wins_since_link_filters_by_end_time():
    now = datetime.now(timezone.utc)
    linked_at = (now - timedelta(days=1)).replace(tzinfo=None)
    sessions = [
        {"gameEnd": (now - timedelta(hours=2)).isoformat(), "hasWon": True},
        {"gameEnd": (now - timedelta(days=2)).isoformat(), "hasWon": True},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_since_link(client, "p1", linked_at))
    assert wins == 1


def test_compute_wins_sessions_with_clan_matches_tags():
    sessions = [
        {"username": "[ABC]Player", "hasWon": True},
        {"username": "[ABC]Player", "hasWon": False},
        {"username": "Player[ABC]", "hasWon": True},
        {"username": "[XYZ]Other", "hasWon": True},
        {"username": "NoTag", "hasWon": True},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_with_clan(client, "p1", ["abc"]))
    assert wins == 2


def test_compute_wins_sessions_with_clan_requires_bracket_prefix():
    sessions = [
        {"username": "PlayerABCx", "hasWon": True},
        {"username": "xabcPlayer", "hasWon": True},
        {"username": "no_match_here", "hasWon": True},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_with_clan(client, "p1", ["abc"]))
    assert wins == 0


def test_compute_wins_sessions_with_clan_uses_clantag_field():
    sessions = [
        {"username": "irrelevant", "clanTag": "AbC", "hasWon": True},
        {"username": "[XYZ]Other", "clanTag": "xyz", "hasWon": True},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_with_clan(client, "p1", ["abc"]))
    assert wins == 1


def test_compute_wins_total_handles_missing_fields():
    client = FakeOpenFront(player_data={})
    wins = asyncio.run(compute_wins_total(client, "player1"))
    assert wins == 0


def test_compute_wins_sessions_since_link_skips_missing_end_time_or_losses():
    now = datetime.now(timezone.utc)
    linked_at = (now - timedelta(days=1)).replace(tzinfo=None)
    sessions = [
        {"gameEnd": None, "hasWon": True},
        {"gameEnd": (linked_at + timedelta(hours=1)).isoformat(), "hasWon": False},
        {"gameEnd": (linked_at + timedelta(hours=2)).isoformat(), "hasWon": True},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_since_link(client, "p1", linked_at))
    assert wins == 1


def test_compute_wins_sessions_with_clan_matches_case_insensitive_anywhere():
    sessions = [
        {"username": "player[abc]end", "hasWon": True},
        {"username": "PREFIX[XYZ]", "hasWon": True},
        {"username": "note", "clanTag": "xyz", "hasWon": True},
        {"username": "no_match", "hasWon": True},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_with_clan(client, "p1", ["AbC", "xYz"]))
    assert wins == 3


def test_compute_wins_sessions_with_clan_without_configured_tags_requires_clantag():
    sessions = [
        {"username": "[ABC]Player", "hasWon": True},
        {"username": "tagless", "hasWon": True},
        {"username": "has_clantag", "clanTag": "abc", "hasWon": True},
    ]
    client = FakeOpenFront(sessions=sessions)
    wins = asyncio.run(compute_wins_sessions_with_clan(client, "p1", []))
    assert wins == 2
