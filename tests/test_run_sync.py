import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from src.bot import BotConfig, CountingBot, GuildContext, apply_roles
from src.models import init_guild_db
from tests.fakes import FakeGuild, FakeMember, FakeOpenFront, FakeRole


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

    # For tests, bypass the background role queue.
    async def immediate_apply(member, thresholds, wins):
        return await apply_roles(member, thresholds, wins)

    bot.apply_roles_with_queue = cast(Any, immediate_apply)
    return bot


def make_context(tmp_path, guild_id=123):
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


def fake_guild_with_member(guild_id: int, member_id: int, roles):
    guild = FakeGuild(
        id=guild_id,
        roles=roles,
        members={},
    )
    member = FakeMember(id=member_id, roles=[], guild=guild)
    guild.members[member_id] = member
    return guild, member


def test_run_sync_assigns_role_in_total_mode(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    models = ctx.models

    # Thresholds and user
    models.RoleThreshold.create(wins=5, role_id=1)
    models.RoleThreshold.create(wins=10, role_id=2)
    models.User.create(
        discord_user_id=42,
        player_id="p1",
        linked_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    settings = models.Settings.get_by_id(1)
    settings.counting_mode = "total"
    settings.roles_enabled = 1
    settings.save()

    guild, member = fake_guild_with_member(
        ctx.guild_id, 42, [FakeRole(1, "Bronze"), FakeRole(2, "Silver")]
    )
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)
    bot.client = cast(
        Any,
        FakeOpenFront(
            player_data={
                "stats": {
                    "Public": {
                        "Free For All": {"Medium": {"wins": 4}},
                        "Team": {"Medium": {"wins": 8}},
                    }
                }
            },
        ),
    )

    bot.guild_contexts[ctx.guild_id] = ctx
    summary = asyncio.run(bot.run_sync(ctx, manual=True))

    record = models.User.get_by_id(42)
    assert "Processed 1 users" in summary
    assert record.last_win_count == 12
    assert record.last_role_id == 2
    assert member.added_roles == [2]
    assert member.removed_roles == []


def test_run_sync_skips_roles_when_disabled(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    models = ctx.models

    models.RoleThreshold.create(wins=5, role_id=1)
    models.User.create(
        discord_user_id=42,
        player_id="p1",
        linked_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    settings = models.Settings.get_by_id(1)
    settings.counting_mode = "total"
    settings.roles_enabled = 0
    settings.save()

    guild, member = fake_guild_with_member(
        ctx.guild_id, 42, [FakeRole(1, "Bronze")]
    )
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)
    bot.client = cast(
        Any,
        FakeOpenFront(
            player_data={
                "stats": {
                    "Public": {
                        "Free For All": {"Medium": {"wins": 5}},
                        "Team": {"Medium": {"wins": 0}},
                    }
                }
            },
        ),
    )

    bot.guild_contexts[ctx.guild_id] = ctx
    asyncio.run(bot.run_sync(ctx, manual=True))

    record = models.User.get_by_id(42)
    assert record.last_win_count == 5
    assert record.last_role_id is None
    assert member.added_roles == []
    assert member.removed_roles == []


def test_run_sync_sessions_with_clan(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    models = ctx.models

    models.RoleThreshold.create(wins=1, role_id=5)
    models.User.create(
        discord_user_id=99,
        player_id="p2",
        linked_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    models.ClanTag.create(tag_text="ABC")
    settings = models.Settings.get_by_id(1)
    settings.counting_mode = "sessions_with_clan"
    settings.roles_enabled = 1
    settings.save()

    guild, member = fake_guild_with_member(
        ctx.guild_id, 99, [FakeRole(5, "ClanWinner")]
    )
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)
    sessions = [
        {"username": "[ABC]Player", "hasWon": True, "gameType": "Public"},
        {"username": "[XYZ]Other", "hasWon": True, "gameType": "Public"},
    ]
    bot.client = cast(Any, FakeOpenFront(sessions=sessions))

    bot.guild_contexts[ctx.guild_id] = ctx
    asyncio.run(bot.run_sync(ctx, manual=True))

    record = models.User.get_by_id(99)
    assert record.last_win_count == 1
    assert record.last_role_id == 5
    assert member.added_roles == [5]
    assert member.removed_roles == []


def test_run_sync_sessions_since_link(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    models = ctx.models

    models.RoleThreshold.create(wins=1, role_id=7)
    linked_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    models.User.create(discord_user_id=77, player_id="p3", linked_at=linked_at)
    settings = models.Settings.get_by_id(1)
    settings.counting_mode = "sessions_since_link"
    settings.roles_enabled = 1
    settings.save()

    guild, member = fake_guild_with_member(
        ctx.guild_id, 77, [FakeRole(7, "RecentWinner")]
    )
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)
    sessions = [
        {"gameStart": (linked_at + timedelta(hours=1)).isoformat(), "hasWon": True},
        {"gameStart": (linked_at - timedelta(hours=1)).isoformat(), "hasWon": True},
    ]
    bot.client = cast(Any, FakeOpenFront(sessions=sessions))

    bot.guild_contexts[ctx.guild_id] = ctx
    asyncio.run(bot.run_sync(ctx, manual=True))

    record = models.User.get_by_id(77)
    assert record.last_win_count == 1
    assert record.last_role_id == 7
    assert member.added_roles == [7]
    assert member.removed_roles == []


def test_run_sync_sets_backoff_on_openfront_errors(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    models = ctx.models
    models.User.create(
        discord_user_id=11,
        player_id="p4",
        linked_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    models.RoleThreshold.create(wins=1, role_id=9)

    guild, member = fake_guild_with_member(ctx.guild_id, 11, [FakeRole(9, "Any")])
    bot.get_guild = cast(Any, lambda gid: guild if gid == ctx.guild_id else None)
    bot.client = cast(Any, FakeOpenFront(should_fail=True))

    bot.guild_contexts[ctx.guild_id] = ctx
    summary = asyncio.run(bot.run_sync(ctx, manual=True))

    settings = models.Settings.get_by_id(1)
    assert "failures" in summary
    assert settings.backoff_until is not None

    # Subsequent sync should honor backoff and skip
    later_summary = asyncio.run(bot.run_sync(ctx, manual=True))
    assert "In backoff until" in later_summary
    assert member.added_roles == []
    assert member.removed_roles == []
