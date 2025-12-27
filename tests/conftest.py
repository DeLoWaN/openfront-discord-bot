# pyright: reportGeneralTypeIssues=false

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

# Ensure project root is on sys.path for `import src`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_discord_stub():
    """Provide a minimal discord.py stub so tests run without the real package."""
    discord = types.ModuleType("discord")

    class Intents:
        def __init__(self):
            self.members = False
            self.guilds = False

        @classmethod
        def default(cls):
            return cls()

    class InteractionType:
        application_command = "application_command"

    class Member:
        pass

    class Role:
        pass

    class Guild:
        pass

    class Interaction:
        pass

    class User:
        pass

    # app_commands stub
    class AppCommandError(Exception):
        pass

    class CheckFailure(AppCommandError):
        pass

    def describe(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def _decorator_passthrough(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    app_commands = types.SimpleNamespace(
        describe=describe,
        AppCommandError=AppCommandError,
        CheckFailure=CheckFailure,
    )

    # commands.Bot stub with minimal API used in CountingBot
    class FakeTree:
        def __init__(self):
            self._commands = []

        async def sync(self):
            return None

        def command(self, *args, **kwargs):
            return _decorator_passthrough(*args, **kwargs)

        def error(self, *args, **kwargs):
            return _decorator_passthrough(*args, **kwargs)

    class FakeBot:
        def __init__(self, *args, **kwargs):
            self.command_prefix = kwargs.get("command_prefix")
            self.intents = kwargs.get("intents")
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.tree = FakeTree()

        def listen(self, *args, **kwargs):
            return _decorator_passthrough(*args, **kwargs)

    commands_mod = types.SimpleNamespace(Bot=FakeBot)

    discord.Intents = Intents
    discord.InteractionType = InteractionType
    discord.Interaction = Interaction
    discord.abc = types.SimpleNamespace(User=User)
    discord.Member = Member
    discord.Role = Role
    discord.Guild = Guild
    discord.ext = types.SimpleNamespace(commands=commands_mod)
    discord.app_commands = app_commands

    sys.modules["discord"] = discord
    sys.modules["discord.ext"] = discord.ext
    sys.modules["discord.ext.commands"] = commands_mod
    sys.modules["discord.abc"] = discord.abc
    sys.modules["discord.app_commands"] = app_commands


# Always stub discord for tests to avoid depending on the real package being installed.
_install_discord_stub()


def _install_peewee_stub():
    """Provide a minimal Peewee stub sufficient for tests."""
    peewee = types.ModuleType("peewee")

    class Field:
        def __init__(self, primary_key=False, unique=False, null=False, default=None):
            self.primary_key = primary_key
            self.unique = unique
            self.null = null
            self.default = default
            self.name = None

        def __set_name__(self, owner, name):
            self.name = name

        def __get__(self, instance, owner):
            if instance is None:
                return self
            return instance.__dict__.get(self.name, self.default)

        def __set__(self, instance, value):
            instance.__dict__[self.name] = value

        def __eq__(self, other):
            return lambda obj: getattr(obj, self.name) == other

    class AutoField(Field):
        def __init__(self, *args, **kwargs):
            super().__init__(primary_key=True, *args, **kwargs)

    class CharField(Field):
        pass

    class IntegerField(Field):
        pass

    class TextField(Field):
        pass

    class DateTimeField(Field):
        pass

    class Query:
        def __init__(self, model, rows):
            self.model = model
            self.rows = list(rows)

        def where(self, predicate):
            return Query(self.model, [r for r in self.rows if predicate(r)])

        def count(self):
            return len(self.rows)

        def execute(self):
            return len(self.rows)

        def order_by(self, field):
            return Query(
                self.model,
                sorted(self.rows, key=lambda r: getattr(r, field.name)),
            )

        def paginate(self, page, limit):
            start = (page - 1) * limit
            end = start + limit
            return Query(self.model, self.rows[start:end])

        def __iter__(self):
            return iter(self.rows)

    class InsertHelper:
        def __init__(self, model, kwargs):
            self.model = model
            self.kwargs = kwargs
            self._update = None
            self._conflict_target = None
            self._ignore = False
            self._replace = False

        def on_conflict(self, conflict_target=None, update=None):
            self._conflict_target = conflict_target or []
            self._update = update or {}
            return self

        def on_conflict_ignore(self):
            self._ignore = True
            return self

        def on_conflict_replace(self):
            self._replace = True
            return self

        def execute(self):
            target_fields = [
                f.name if hasattr(f, "name") else str(f)
                for f in self._conflict_target or []
            ]
            # Find existing record matching conflict target
            existing = None
            if target_fields:
                for rec in self.model._records:
                    if all(
                        getattr(rec, f) == self.kwargs.get(f) for f in target_fields
                    ):
                        existing = rec
                        break
            if existing and self._ignore:
                return 0
            if existing and (self._replace or self._update is not None):
                for k, v in (self._update or {}).items():
                    setattr(existing, k.name if hasattr(k, "name") else k, v)
                return 1
            obj = self.model(**self.kwargs)
            self.model._records.append(obj)
            return 1

    class DeleteHelper:
        def __init__(self, model):
            self.model = model
            self.predicate = None

        def where(self, predicate):
            self.predicate = predicate
            return self

        def execute(self):
            before = len(self.model._records)
            if self.predicate:
                self.model._records = [
                    r for r in self.model._records if not self.predicate(r)
                ]
            else:
                self.model._records = []
            return before - len(self.model._records)

    class ModelMeta(type):
        def __new__(mcls, name, bases, attrs):
            cls = super().__new__(mcls, name, bases, attrs)
            cls._records = []
            # identify pk field
            cls._pk_field = None
            for k, v in attrs.items():
                if isinstance(v, Field) and v.primary_key:
                    cls._pk_field = k
            return cls

    class Model(metaclass=ModelMeta):
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            # auto-assign pk if needed
            if getattr(self, "_pk_field", None):
                pk = getattr(self, self._pk_field, None)
                if pk is None and isinstance(
                    getattr(self.__class__, self._pk_field), AutoField
                ):
                    setattr(self, self._pk_field, len(self.__class__._records) + 1)

        @classmethod
        def select(cls, *args):
            return Query(cls, cls._records)

        @classmethod
        def create(cls, **kwargs):
            obj = cls(**kwargs)
            cls._records.append(obj)
            return obj

        @classmethod
        def get_by_id(cls, pk):
            for rec in cls._records:
                if getattr(rec, cls._pk_field) == pk:
                    return rec
            raise KeyError(pk)

        @classmethod
        def get_or_none(cls, predicate):
            for rec in cls._records:
                if predicate(rec):
                    return rec
            return None

        @classmethod
        def insert(cls, **kwargs):
            return InsertHelper(cls, kwargs)

        @classmethod
        def delete(cls):
            return DeleteHelper(cls)

        def save(self, *args, **kwargs):
            # replace existing by pk or append
            pk_val = getattr(self, self._pk_field)
            for idx, rec in enumerate(self.__class__._records):
                if getattr(rec, self._pk_field) == pk_val:
                    self.__class__._records[idx] = self
                    return 1
            self.__class__._records.append(self)
            return 1

    class SqliteDatabase:
        def __init__(self, path):
            self.path = path

        def connect(self, reuse_if_open=False):
            return None

        def create_tables(self, models):
            return None

        def init(self, path):
            self.path = path

        def execute_sql(self, *args, **kwargs):
            class DummyCursor:
                def fetchall(self_inner):
                    return []

            return DummyCursor()

    peewee.AutoField = AutoField
    peewee.CharField = CharField
    peewee.DateTimeField = DateTimeField
    peewee.IntegerField = IntegerField
    peewee.Model = Model
    peewee.SqliteDatabase = SqliteDatabase
    peewee.TextField = TextField

    sys.modules["peewee"] = peewee


if importlib.util.find_spec("peewee") is None:
    _install_peewee_stub()


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as asyncio")
