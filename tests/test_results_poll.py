import asyncio
from datetime import datetime, timezone
from typing import Any, cast

from src.bot import BotConfig, CountingBot, GuildContext
from src.central_db import TrackedGame, track_game
from src.models import init_guild_db
from src.openfront import OpenFrontError
from tests.fakes import FakeChannel, FakeGuild, FakeOpenFront


def make_bot(tmp_path):
    config = BotConfig(
        token="dummy",
        log_level="INFO",
        central_database_path=str(tmp_path / "central.db"),
        sync_interval_hours=24,
        results_lobby_poll_seconds=2,
    )
    bot = CountingBot(config)
    bot.guild_data_dir = tmp_path / "guild_data"
    bot.guild_data_dir.mkdir(parents=True, exist_ok=True)
    return bot


def make_context(tmp_path, guild_id=321):
    db_path = tmp_path / f"guild_{guild_id}.db"
    models = init_guild_db(str(db_path), guild_id)
    ctx = GuildContext(
        guild_id=guild_id,
        database_path=str(db_path),
        models=models,
        admin_role_ids=set(),
        sync_lock=asyncio.Lock(),
    )
    return ctx


def enable_results(ctx, channel_id=123):
    settings = ctx.models.Settings.get_by_id(1)
    settings.results_enabled = 1
    settings.results_channel_id = channel_id
    settings.save()


def queue_game(game_id: str):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    track_game(game_id, next_attempt_at=now)


def test_results_poll_posts_embed_and_dedupes(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=101)

    channel = FakeChannel(id=101)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={101: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    game = {
        "info": {
            "config": {
                "gameMap": "Halkidiki",
                "gameMode": "Team",
                "playerTeams": "Duos",
            },
            "numTeams": 24,
            "players": [
                {"clientID": "c1", "username": "Ace", "clanTag": "NU"},
                {"clientID": "c2", "username": "Enemy", "clanTag": "XYZ"},
            ],
            "winner": ["team", "Team 1", "c1"],
            "start": 1763338803169,
            "end": 1763339806340,
            "duration": 1003,
        }
    }
    bot.client = FakeOpenFront(games={"g1": game})
    queue_game("g1")

    summary = asyncio.run(bot.run_results_poll(ctx))

    assert "Posted 1 games" in summary
    assert len(channel.sent_embeds) == 1
    embed = channel.sent_embeds[0]
    assert "Halkidiki" in embed.description
    assert "24 teams of 2 players (Duos)" in embed.description
    assert "Finished:" in embed.description
    opponents_field = next(
        field for field in embed.fields if field["name"] == "Opponents"
    )
    assert "XYZ: 1 player (Enemy)" in opponents_field["value"]
    assert ctx.models.PostedGame.select().count() == 1

    asyncio.run(bot.run_results_poll(ctx))
    assert len(channel.sent_embeds) == 1


def test_results_poll_formats_numeric_mode(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=202)

    channel = FakeChannel(id=202)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={202: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    game = {
        "info": {
            "config": {
                "gameMap": "Alps",
                "gameMode": "Team",
                "playerTeams": "7",
                "maxPlayers": 84,
            },
            "players": [{"clientID": "c1", "username": "Ace", "clanTag": "NU"}],
            "winner": ["team", "Team 7", "c1"],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(games={"g2": game})
    queue_game("g2")

    asyncio.run(bot.run_results_poll(ctx))

    embed = channel.sent_embeds[0]
    assert "7 teams of 12 players" in embed.description


def test_results_poll_posts_ffa_game(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=707)

    channel = FakeChannel(id=707)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={707: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    game = {
        "info": {
            "config": {"gameMap": "World", "gameMode": "Free For All"},
            "players": [
                {"clientID": "c1", "username": "Ace", "clanTag": "NU"},
                {"clientID": "c2", "username": "Buddy", "clanTag": "NU"},
            ],
            "winner": ["player", "c1"],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(games={"g9": game})
    queue_game("g9")

    asyncio.run(bot.run_results_poll(ctx))

    embed = channel.sent_embeds[0]
    assert "Free For All" in embed.description
    winners_field = next(field for field in embed.fields if field["name"] == "Winners")
    assert "Ace" in winners_field["value"]
    assert "Buddy" not in winners_field["value"]
    assert "died early" not in winners_field["value"]


def test_results_poll_uses_total_player_count_for_team_size(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=606)

    channel = FakeChannel(id=606)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={606: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    game = {
        "info": {
            "config": {"gameMap": "Gamma", "gameMode": "Team", "playerTeams": "4"},
            "numTeams": 4,
            "totalPlayerCount": 28,
            "players": [
                {"clientID": "c1", "username": "Ace", "clanTag": "NU"},
                {"clientID": "c2", "username": "Enemy", "clanTag": "JK"},
            ],
            "winner": ["team", "Team 2", "c1"],
            "start": 1763338803169,
            "end": 1763339806340,
        }
    }
    bot.client = FakeOpenFront(games={"g6": game})
    queue_game("g6")

    asyncio.run(bot.run_results_poll(ctx))

    embed = channel.sent_embeds[0]
    assert "4 teams of 7 players" in embed.description


def test_results_poll_mentions_unique_match(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    ctx.models.User.create(
        discord_user_id=42,
        player_id="p1",
        linked_at=datetime.now(timezone.utc).replace(tzinfo=None),
        last_openfront_username="Ace",
    )
    enable_results(ctx, channel_id=303)

    channel = FakeChannel(id=303)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={303: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    game = {
        "info": {
            "config": {"gameMap": "Delta", "gameMode": "Team", "playerTeams": "Duos"},
            "numTeams": 2,
            "players": [
                {"clientID": "c1", "username": "Ace", "clanTag": "NU"},
                {"clientID": "c2", "username": "Other", "clanTag": "XYZ"},
            ],
            "winner": ["team", "Team 1", "c1"],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(games={"g3": game})
    queue_game("g3")

    asyncio.run(bot.run_results_poll(ctx))

    embed = channel.sent_embeds[0]
    winners_field = next(field for field in embed.fields if field["name"] == "Winners")
    assert "<@42>" in winners_field["value"]


def test_results_poll_marks_died_early(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=505)

    channel = FakeChannel(id=505)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={505: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    game = {
        "info": {
            "config": {
                "gameMap": "Foxtrot",
                "gameMode": "Team",
                "playerTeams": "Trios",
            },
            "numTeams": 2,
            "players": [
                {"clientID": "c1", "username": "Ace", "clanTag": "NU"},
                {"clientID": "c2", "username": "Buddy", "clanTag": "NU"},
            ],
            "winner": ["team", "Team 1", "c1"],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(games={"g5": game})
    queue_game("g5")

    asyncio.run(bot.run_results_poll(ctx))

    embed = channel.sent_embeds[0]
    winners_field = next(field for field in embed.fields if field["name"] == "Winners")
    assert "Buddy" in winners_field["value"]
    assert " - 💀 *died early*" in winners_field["value"]
    assert "+1 other player" in winners_field["value"]


def test_results_poll_skips_humans_vs_nations_mode(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=606)

    channel = FakeChannel(id=606)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={606: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    game = {
        "info": {
            "config": {
                "gameMap": "Gamma",
                "gameMode": "Team",
                "playerTeams": "Humans Vs Nations",
            },
            "players": [{"clientID": "c1", "username": "Ace", "clanTag": "NU"}],
            "winner": ["team", "Team 1", "c1"],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(games={"g6": game})
    queue_game("g6")

    summary = asyncio.run(bot.run_results_poll(ctx))

    assert "Posted 0 games" in summary
    assert channel.sent_embeds == []
    assert ctx.models.PostedGame.select().count() == 0


def test_results_poll_skips_when_winner_tag_missing(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=707)

    channel = FakeChannel(id=707)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={707: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    game = {
        "info": {
            "config": {"gameMap": "Golf", "gameMode": "Team"},
            "players": [{"clientID": "c1", "username": "Ace", "clanTag": None}],
            "winner": ["team", "Team 1", "c1"],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(games={"g7": game})
    queue_game("g7")

    asyncio.run(bot.run_results_poll(ctx))

    assert channel.sent_embeds == []


def test_results_poll_posts_when_winner_tags_mixed_includes_guild(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=808)

    channel = FakeChannel(id=808)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={808: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    game = {
        "info": {
            "config": {"gameMap": "Hotel", "gameMode": "Team"},
            "players": [
                {"clientID": "c1", "username": "Ace", "clanTag": "NU"},
                {"clientID": "c2", "username": "Enemy", "clanTag": "XYZ"},
            ],
            "winner": ["team", "Team 1", "c1", "c2"],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(games={"g8": game})
    queue_game("g8")

    asyncio.run(bot.run_results_poll(ctx))

    assert len(channel.sent_embeds) == 1
    embed = channel.sent_embeds[0]
    winners_field = next(field for field in embed.fields if field["name"] == "Winners")
    assert "Ace" in winners_field["value"]
    assert "Enemy" not in winners_field["value"]


def test_results_poll_skips_mentions_on_multiple_matches(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    ctx.models.User.create(
        discord_user_id=42,
        player_id="p1",
        linked_at=datetime.now(timezone.utc).replace(tzinfo=None),
        last_openfront_username="Ace",
    )
    ctx.models.User.create(
        discord_user_id=43,
        player_id="p2",
        linked_at=datetime.now(timezone.utc).replace(tzinfo=None),
        last_openfront_username="Ace",
    )
    enable_results(ctx, channel_id=404)

    channel = FakeChannel(id=404)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={404: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    game = {
        "info": {
            "config": {"gameMap": "Echo", "gameMode": "Team", "playerTeams": "Duos"},
            "numTeams": 2,
            "players": [
                {"clientID": "c1", "username": "Ace", "clanTag": "NU"},
                {"clientID": "c2", "username": "Other", "clanTag": "XYZ"},
            ],
            "winner": ["team", "Team 1", "c1"],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(games={"g4": game})
    queue_game("g4")

    asyncio.run(bot.run_results_poll(ctx))

    embed = channel.sent_embeds[0]
    winners_field = next(field for field in embed.fields if field["name"] == "Winners")
    assert "Ace" in winners_field["value"]
    assert "<@" not in winners_field["value"]


def test_results_poll_reschedules_missing_game(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=909)

    channel = FakeChannel(id=909)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={909: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    bot.client = FakeOpenFront(games={})
    queue_game("missing")

    asyncio.run(bot.run_results_poll(ctx))

    entry = TrackedGame.get_or_none(TrackedGame.game_id == "missing")
    assert entry is not None
    assert entry.next_attempt_at > datetime.now(timezone.utc).replace(tzinfo=None)


def test_results_poll_marks_failed_after_unexpected_errors(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    enable_results(ctx, channel_id=909)

    class FailingClient:
        async def fetch_game(self, game_id: str):
            raise OpenFrontError("bad request", status=400)

    bot.client = FailingClient()
    queue_game("bad")

    for _ in range(3):
        posted, failures, retry = asyncio.run(bot._process_tracked_game("bad"))

    entry = TrackedGame.get_or_none(TrackedGame.game_id == "bad")
    assert entry is not None
    assert entry.failed_at is not None
    assert entry.consecutive_unexpected_failures == 3
    assert retry is False
    assert posted == 0
    assert failures == 0


def test_results_lobby_tracking_records_games(tmp_path):
    bot = make_bot(tmp_path)

    added = bot._record_public_lobbies(
        [{"gameID": "g1"}, {"gameID": "g2"}, {"gameId": "g3"}]
    )

    assert added == 3
    assert TrackedGame.select().count() == 3
