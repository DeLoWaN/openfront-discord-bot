import asyncio
from types import SimpleNamespace

import discord

from src.bot import BotConfig, CountingBot, GuildContext, setup_commands
from src.models import init_guild_db
from tests.fakes import FakeRole


class AdminPermissions:
    def __init__(self):
        self.administrator = True
        self.manage_guild = True


class CommandResponse:
    def __init__(self):
        self.message = None
        self.ephemeral = None

    def is_done(self):
        return self.message is not None

    async def send_message(self, content, ephemeral=False, **kwargs):
        self.message = content
        self.ephemeral = ephemeral


class CommandMember(discord.Member):
    def __init__(self, user_id: int, guild):
        self.id = user_id
        self.guild = guild
        self.roles = []
        self.guild_permissions = AdminPermissions()
        self.display_name = "Admin"


class CommandInteraction(discord.Interaction):
    def __init__(self, guild, user):
        self.guild = guild
        self.user = user
        self.response = CommandResponse()


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
