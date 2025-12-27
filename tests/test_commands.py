import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import List, Optional

import discord

from src.bot import BotConfig, CountingBot, GuildContext, setup_commands
from src.models import init_guild_db, record_audit
from tests.fakes import FakeGuild, FakeMember, FakeOpenFront, FakeRole


class AdminPermissions:
    def __init__(self):
        self.administrator = True
        self.manage_guild = True


class CommandResponse:
    def __init__(self):
        self.message: Optional[str] = None
        self.messages: List[str] = []
        self.ephemeral = None
        self.deferred = False

    def is_done(self):
        return self.message is not None or bool(self.messages)

    async def send_message(self, content, ephemeral=False, **kwargs):
        self.message = content
        self.messages.append(content)
        self.ephemeral = ephemeral

    async def defer(self, ephemeral=False, thinking=False):
        self.deferred = True


class CommandFollowup:
    def __init__(self):
        self.message: Optional[str] = None
        self.messages: List[str] = []
        self.ephemeral = None

    async def send(self, content, ephemeral=False, **kwargs):
        self.message = content
        self.messages.append(content)
        self.ephemeral = ephemeral


class CommandMember(discord.Member):
    def __init__(self, user_id: int, guild, display_name="Admin"):
        self.id = user_id
        self.guild = guild
        self.roles = []
        self.guild_permissions = AdminPermissions()
        self.display_name = display_name


class CommandInteraction(discord.Interaction):
    def __init__(self, guild, user):
        self.guild = guild
        self.user = user
        self.response = CommandResponse()
        self.followup = CommandFollowup()


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


def make_context(tmp_path, guild_id=999):
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


def capture_commands(tree):
    captured = {}

    def command(*args, **kwargs):
        def decorator(func):
            captured[kwargs.get("name") or func.__name__] = func
            return func

        return decorator

    tree.command = command
    tree.error = lambda *args, **kwargs: (lambda func: func)
    return captured


def stub_bot_calculations(bot, win_total=0, applied_role=None):
    async def compute_wins(*args, **kwargs):
        return win_total

    async def apply_roles(member, thresholds, win_count):
        return applied_role

    bot._compute_wins = compute_wins
    bot.apply_roles_with_queue = apply_roles
    return bot


def test_roles_add_returns_friendly_error_on_duplicate(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    ctx.models.RoleThreshold.create(wins=5, role_id=123)
    bot.guild_contexts[ctx.guild_id] = ctx

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = SimpleNamespace(id=ctx.guild_id, name="TestGuild")
    member = CommandMember(user_id=1, guild=guild)
    interaction = CommandInteraction(guild=guild, user=member)
    role = FakeRole(123, "Existing")

    asyncio.run(commands["roles_add"](interaction, 5, role))

    assert (
        interaction.response.message
        == "A threshold for 5 wins using role <@&123> already exists."
    )
    assert interaction.response.ephemeral is True


def test_roles_add_blocks_role_used_by_other_threshold(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    ctx.models.RoleThreshold.create(wins=5, role_id=123)
    ctx.models.RoleThreshold.create(wins=10, role_id=456)
    bot.guild_contexts[ctx.guild_id] = ctx

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = SimpleNamespace(id=ctx.guild_id, name="TestGuild")
    member = CommandMember(user_id=1, guild=guild)
    interaction = CommandInteraction(guild=guild, user=member)
    role = FakeRole(123, "Existing")

    asyncio.run(commands["roles_add"](interaction, 10, role))

    assert (
        interaction.response.message
        == "Role <@&123> is already assigned to the 5 wins threshold. Remove it first to reassign it."
    )
    assert interaction.response.ephemeral is True


def test_admin_role_add_response_mentions_role(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(id=ctx.guild_id, roles=[FakeRole(321, "Admin")], members={})
    member = CommandMember(user_id=1, guild=guild)
    interaction = CommandInteraction(guild=guild, user=member)
    role = FakeRole(321, "Admin")

    asyncio.run(commands["admin_role_add"](interaction, role))

    assert interaction.response.message == "Added admin role <@&321>"
    assert interaction.response.ephemeral is True


def test_admin_role_remove_response_mentions_role(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    ctx.models.GuildAdminRole.create(role_id=321)
    bot.guild_contexts[ctx.guild_id] = ctx

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(id=ctx.guild_id, roles=[FakeRole(321, "Admin")], members={})
    member = CommandMember(user_id=1, guild=guild)
    interaction = CommandInteraction(guild=guild, user=member)
    role = FakeRole(321, "Admin")

    asyncio.run(commands["admin_role_remove"](interaction, role))

    assert interaction.response.message == "Removed 1 entries for role <@&321>"
    assert interaction.response.ephemeral is True


def test_admin_roles_lists_mentions(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    ctx.models.GuildAdminRole.create(role_id=321)
    bot.guild_contexts[ctx.guild_id] = ctx

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(id=ctx.guild_id, roles=[FakeRole(321, "Admin")], members={})
    member = CommandMember(user_id=1, guild=guild)
    interaction = CommandInteraction(guild=guild, user=member)

    asyncio.run(commands["admin_roles"](interaction))

    assert interaction.response.message == "<@&321>"
    assert interaction.response.ephemeral is True


def test_link_creates_user_and_reports_wins(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    stub_bot_calculations(bot, win_total=7, applied_role=999)
    bot.client = FakeOpenFront()

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(id=ctx.guild_id, roles=[FakeRole(1, "R")], members={})
    member = CommandMember(user_id=42, guild=guild, display_name="PlayerOne")
    guild.members[member.id] = member
    interaction = CommandInteraction(guild=guild, user=member)

    asyncio.run(commands["link"](interaction, "player-1"))

    record = ctx.models.User.get_by_id(42)
    assert record.player_id == "player-1"
    assert record.last_win_count == 7
    assert record.last_role_id == 999
    assert "Current wins: `7`" in interaction.followup.message
    assert interaction.response.deferred is True
    assert interaction.followup.ephemeral is True


def test_unlink_removes_user(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.User.create(
        discord_user_id=5,
        player_id="p1",
        linked_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(id=ctx.guild_id, roles=[], members={})
    member = CommandMember(user_id=5, guild=guild)
    interaction = CommandInteraction(guild=guild, user=member)

    asyncio.run(commands["unlink"](interaction))

    assert ctx.models.User.select().count() == 0
    assert interaction.response.message == "Unlinked."
    assert interaction.response.ephemeral is True


def test_status_returns_not_linked_when_missing(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(id=ctx.guild_id, roles=[], members={})
    member = CommandMember(user_id=10, guild=guild)
    interaction = CommandInteraction(guild=guild, user=member)

    asyncio.run(commands["status"](interaction))

    assert interaction.response.message == "Not linked."
    assert interaction.response.ephemeral is True


def test_status_shows_last_role_and_counts(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx

    role = FakeRole(77, "Winner")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ctx.models.User.create(
        discord_user_id=11,
        player_id="p-status",
        linked_at=now,
        last_role_id=role.id,
        last_win_count=3,
    )
    settings = ctx.models.Settings.get_by_id(1)
    settings.counting_mode = "total"
    settings.last_sync_at = now
    settings.save()

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(id=ctx.guild_id, roles=[role], members={})
    member = CommandMember(user_id=11, guild=guild)
    guild.members[member.id] = member
    interaction = CommandInteraction(guild=guild, user=member)

    asyncio.run(commands["status"](interaction))

    assert "Player ID: `p-status`" in interaction.response.message
    assert "<@&77>" in interaction.response.message
    assert interaction.response.ephemeral is True


def test_sync_single_user_updates_record(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    stub_bot_calculations(bot, win_total=11, applied_role=321)
    ctx.models.User.create(
        discord_user_id=50,
        player_id="p-sync",
        linked_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    role = FakeRole(321, "Tier")
    guild = FakeGuild(id=ctx.guild_id, roles=[role], members={})
    admin = CommandMember(user_id=1, guild=guild, display_name="Admin")
    target = FakeMember(id=50, roles=[], guild=guild, display_name="Target")
    guild.members[admin.id] = admin
    guild.members[target.id] = target
    interaction = CommandInteraction(guild=guild, user=admin)

    asyncio.run(commands["sync"](interaction, target))

    record = ctx.models.User.get_by_id(50)
    assert record.last_win_count == 11
    assert record.last_role_id == 321
    assert interaction.response.deferred is True
    assert interaction.followup.message == "Synced Target: 11 wins"
    assert interaction.followup.ephemeral is True


def test_set_mode_and_get_mode(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(id=ctx.guild_id, roles=[], members={})
    admin = CommandMember(user_id=1, guild=guild)
    interaction = CommandInteraction(guild=guild, user=admin)

    asyncio.run(commands["set_mode"](interaction, "total"))
    settings = ctx.models.Settings.get_by_id(1)
    assert settings.counting_mode == "total"
    assert interaction.response.message == "Counting mode set to total"

    interaction_get = CommandInteraction(guild=guild, user=admin)
    asyncio.run(commands["get_mode"](interaction_get))
    assert interaction_get.response.message == "Current counting mode: total"


def test_roles_remove_and_list(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    ctx.models.RoleThreshold.create(wins=5, role_id=200)
    ctx.models.RoleThreshold.create(wins=10, role_id=201)

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(
        id=ctx.guild_id, roles=[FakeRole(200, "A"), FakeRole(201, "B")], members={}
    )
    admin = CommandMember(user_id=1, guild=guild)
    interaction_remove = CommandInteraction(guild=guild, user=admin)

    asyncio.run(commands["roles_remove"](interaction_remove, wins=5))

    assert ctx.models.RoleThreshold.select().count() == 1
    assert interaction_remove.response.message == "Removed 1 entries."
    assert interaction_remove.response.ephemeral is True

    interaction_roles = CommandInteraction(guild=guild, user=admin)
    asyncio.run(commands["roles"](interaction_roles))
    assert "10 wins: <@&201>" in interaction_roles.response.message
    assert interaction_roles.response.ephemeral is True


def test_clan_tag_add_remove_and_list(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(id=ctx.guild_id, roles=[], members={})
    admin = CommandMember(user_id=1, guild=guild)

    interaction_add = CommandInteraction(guild=guild, user=admin)
    asyncio.run(commands["clan_tag_add"](interaction_add, "abc"))
    assert interaction_add.response.message == "Clan tag 'ABC' added"

    interaction_list = CommandInteraction(guild=guild, user=admin)
    asyncio.run(commands["clans_list"](interaction_list))
    assert interaction_list.response.message == "ABC"

    interaction_remove = CommandInteraction(guild=guild, user=admin)
    asyncio.run(commands["clan_tag_remove"](interaction_remove, "abc"))
    assert interaction_remove.response.message == "Removed 1 entries"


def test_link_override_sets_user(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(id=ctx.guild_id, roles=[], members={})
    admin = CommandMember(user_id=1, guild=guild)
    target = CommandMember(user_id=99, guild=guild, display_name="TargetUser")
    interaction = CommandInteraction(guild=guild, user=admin)

    asyncio.run(commands["link_override"](interaction, target, "override-id"))

    record = ctx.models.User.get_by_id(99)
    assert record.player_id == "override-id"
    assert interaction.response.message == "Linked TargetUser to override-id"


def test_audit_lists_entries(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    record_audit(ctx.models, actor_discord_id=1, action="do", payload={"a": 1})

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    guild = FakeGuild(id=ctx.guild_id, roles=[], members={})
    guild.members[1] = FakeMember(id=1, roles=[], guild=guild, display_name="Actor")
    admin = CommandMember(user_id=1, guild=guild)
    interaction = CommandInteraction(guild=guild, user=admin)

    asyncio.run(commands["audit"](interaction))

    assert "action=do" in interaction.response.message
    assert interaction.response.ephemeral is True


def test_guild_remove_requires_confirm_and_deletes(tmp_path):
    bot = make_bot(tmp_path)
    ctx = make_context(tmp_path)
    bot.guild_contexts[ctx.guild_id] = ctx
    delete_called = {}

    async def fake_delete(guild_id, db_path=None):
        delete_called["called"] = (guild_id, db_path)

    bot._delete_guild_data = fake_delete

    commands = capture_commands(bot.tree)
    asyncio.run(setup_commands(bot))

    class LeavingGuild(FakeGuild):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.leave_called = False

        async def leave(self):
            self.leave_called = True

    guild = LeavingGuild(id=ctx.guild_id, roles=[], members={})
    admin = CommandMember(user_id=1, guild=guild)

    interaction_confirm_false = CommandInteraction(guild=guild, user=admin)
    asyncio.run(commands["guild_remove"](interaction_confirm_false, confirm=False))
    assert (
        interaction_confirm_false.response.message
        == "This will delete all data for this guild. Re-run with confirm=true to proceed."
    )
    assert interaction_confirm_false.response.ephemeral is True

    interaction_confirm_true = CommandInteraction(guild=guild, user=admin)
    asyncio.run(commands["guild_remove"](interaction_confirm_true, confirm=True))
    assert interaction_confirm_true.response.message == "Removing guild data..."
    assert interaction_confirm_true.response.ephemeral is True
    assert delete_called["called"][0] == ctx.guild_id
    assert guild.leave_called is True
