from __future__ import annotations

from typing import Any

from ..core.config import MariaDBConfig

try:
    from peewee import DatabaseProxy
    from playhouse.pool import PooledMySQLDatabase
    from playhouse.shortcuts import ReconnectMixin

    class ReconnectablePooledMySQLDatabase(
        ReconnectMixin,
        PooledMySQLDatabase,
    ):
        pass
except ImportError:
    class DatabaseProxy:
        def __init__(self):
            self.obj = None

        def initialize(self, database: Any) -> None:
            self.obj = database

        def connect(self, *args: Any, **kwargs: Any) -> Any:
            if self.obj and hasattr(self.obj, "connect"):
                return self.obj.connect(*args, **kwargs)
            return None

        def close(self) -> Any:
            if self.obj and hasattr(self.obj, "close"):
                return self.obj.close()
            return None

        def is_closed(self) -> bool:
            if self.obj and hasattr(self.obj, "is_closed"):
                return bool(self.obj.is_closed())
            return self.obj is None

        def __getattr__(self, name: str) -> Any:
            if self.obj is None:
                raise AttributeError(name)
            return getattr(self.obj, name)

    class ReconnectablePooledMySQLDatabase:
        def __init__(self, database: str, **connect_params: Any):
            self.database = database
            self.connect_params = connect_params
            self._is_closed = True

        def connect(self, reuse_if_open: bool = True) -> None:
            if reuse_if_open and not self._is_closed:
                return
            self._is_closed = False

        def close(self) -> None:
            self._is_closed = True

        def is_closed(self) -> bool:
            return self._is_closed


shared_database = DatabaseProxy()
MARIADB_POOL_MAX_CONNECTIONS = 4
MARIADB_POOL_STALE_TIMEOUT = 300


def build_mariadb_connect_params(config: MariaDBConfig) -> dict[str, object]:
    return {
        "user": config.user,
        "password": config.password,
        "host": config.host,
        "port": config.port,
        "charset": config.charset,
        "use_unicode": True,
    }


def build_mariadb_database(config: MariaDBConfig) -> ReconnectablePooledMySQLDatabase:
    return ReconnectablePooledMySQLDatabase(
        config.database,
        max_connections=MARIADB_POOL_MAX_CONNECTIONS,
        stale_timeout=MARIADB_POOL_STALE_TIMEOUT,
        **build_mariadb_connect_params(config),
    )


def init_shared_database(
    config: MariaDBConfig,
    *,
    connect: bool = True,
) -> ReconnectablePooledMySQLDatabase:
    database = build_mariadb_database(config)
    shared_database.initialize(database)
    if connect:
        database.connect(reuse_if_open=True)
    return database


def close_shared_database() -> None:
    database = getattr(shared_database, "obj", None)
    if database and hasattr(database, "close"):
        database.close()


__all__ = [
    "build_mariadb_connect_params",
    "build_mariadb_database",
    "close_shared_database",
    "init_shared_database",
    "shared_database",
]
