import asyncio
from datetime import datetime, timezone
from typing import Any, cast

from src.bot import BotConfig, CountingBot, GuildContext
from src.models import init_guild_db
from tests.fakes import FakeChannel, FakeGuild, FakeOpenFront


def make_bot(tmp_path):
    config = BotConfig(
        token="dummy",
        log_level="INFO",
        central_database_path=str(tmp_path / "central.db"),
        sync_interval_hours=24,
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
        results_lock=asyncio.Lock(),
    )
    return ctx


def enable_results(ctx, channel_id=123):
    settings = ctx.models.Settings.get_by_id(1)
    settings.results_enabled = 1
    settings.results_channel_id = channel_id
    settings.results_interval_seconds = 60
    settings.results_last_poll_at = None
    settings.save()


def test_results_poll_posts_embed_and_dedupes(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=101)

    channel = FakeChannel(id=101)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={101: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    sessions = [
        {
            "gameId": "g1",
            "clanTag": "NU",
            "hasWon": True,
            "gameStart": "2025-11-17T00:30:14.614Z",
            "numTeams": 41,
            "playerTeams": "Trios",
        }
    ]
    game = {
        "info": {
            "config": {"gameMap": "Halkidiki"},
            "players": [
                {"username": "Ace", "clanTag": "NU"},
                {"username": "Enemy", "clanTag": "XYZ"},
            ],
            "start": 1763338803169,
            "end": 1763339806340,
            "duration": 1003,
        }
    }
    bot.client = FakeOpenFront(clan_sessions={"NU": sessions}, games={"g1": game})

    summary = asyncio.run(bot.run_results_poll(ctx))

    assert "Posted 1 games" in summary
    assert len(channel.sent_embeds) == 1
    embed = channel.sent_embeds[0]
    assert "Halkidiki" in embed.description
    assert "41 teams (Trios)" in embed.description
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

    sessions = [
        {
            "gameId": "g2",
            "clanTag": "NU",
            "hasWon": True,
            "gameStart": "2025-11-17T01:30:14.614Z",
            "numTeams": 7,
            "playerTeams": "12",
        }
    ]
    game = {
        "info": {
            "config": {"gameMap": "Alps"},
            "players": [{"username": "Ace", "clanTag": "NU"}],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(clan_sessions={"NU": sessions}, games={"g2": game})

    asyncio.run(bot.run_results_poll(ctx))

    embed = channel.sent_embeds[0]
    assert "7 teams (12 players per team)" in embed.description


def test_results_poll_uses_total_player_count_for_team_size(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=606)

    channel = FakeChannel(id=606)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={606: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    sessions = [
        {
            "gameId": "g6",
            "clanTag": "NU",
            "hasWon": True,
            "gameStart": "2025-11-17T05:30:14.614Z",
            "numTeams": 4,
            "playerTeams": "4",
            "totalPlayerCount": 28,
        }
    ]
    game = {
        "info": {
            "config": {"gameMap": "Gamma"},
            "players": [
                {"username": "Ace", "clanTag": "NU"},
                {"username": "Enemy", "clanTag": "JK"},
            ],
            "start": 1763338803169,
            "end": 1763339806340,
        }
    }
    bot.client = FakeOpenFront(clan_sessions={"NU": sessions}, games={"g6": game})

    asyncio.run(bot.run_results_poll(ctx))

    embed = channel.sent_embeds[0]
    assert "4 teams (7 players per team)" in embed.description


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

    sessions = [
        {
            "gameId": "g3",
            "clanTag": "NU",
            "hasWon": True,
            "gameStart": "2025-11-17T02:30:14.614Z",
            "numTeams": 2,
            "playerTeams": "Duos",
        }
    ]
    game = {
        "info": {
            "config": {"gameMap": "Delta"},
            "players": [
                {"username": "Ace", "clanTag": "NU"},
                {"username": "Other", "clanTag": "XYZ"},
            ],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(clan_sessions={"NU": sessions}, games={"g3": game})

    asyncio.run(bot.run_results_poll(ctx))

    embed = channel.sent_embeds[0]
    winners_field = next(field for field in embed.fields if field["name"] == "Winners")
    assert "<@42>" in winners_field["value"]


def test_results_poll_includes_untagged_winner_count(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.ClanTag.create(tag_text="NU")
    enable_results(ctx, channel_id=505)

    channel = FakeChannel(id=505)
    guild = FakeGuild(id=ctx.guild_id, roles=[], members={}, channels={505: channel})
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)

    sessions = [
        {
            "gameId": "g5",
            "clanTag": "NU",
            "hasWon": True,
            "gameStart": "2025-11-17T04:30:14.614Z",
            "numTeams": 2,
            "playerTeams": "Duos",
        }
    ]
    game = {
        "info": {
            "config": {"gameMap": "Foxtrot"},
            "players": [
                {"username": "Ace", "clanTag": "NU"},
                {"username": "Anon", "clanTag": None},
            ],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(clan_sessions={"NU": sessions}, games={"g5": game})

    asyncio.run(bot.run_results_poll(ctx))

    embed = channel.sent_embeds[0]
    winners_field = next(field for field in embed.fields if field["name"] == "Winners")
    assert "+1 other player" in winners_field["value"]


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

    sessions = [
        {
            "gameId": "g4",
            "clanTag": "NU",
            "hasWon": True,
            "gameStart": "2025-11-17T03:30:14.614Z",
            "numTeams": 2,
            "playerTeams": "Duos",
        }
    ]
    game = {
        "info": {
            "config": {"gameMap": "Echo"},
            "players": [
                {"username": "Ace", "clanTag": "NU"},
                {"username": "Other", "clanTag": "XYZ"},
            ],
            "start": 1763338803169,
        }
    }
    bot.client = FakeOpenFront(clan_sessions={"NU": sessions}, games={"g4": game})

    asyncio.run(bot.run_results_poll(ctx))

    embed = channel.sent_embeds[0]
    winners_field = next(field for field in embed.fields if field["name"] == "Winners")
    assert "Ace" in winners_field["value"]
    assert "<@" not in winners_field["value"]
