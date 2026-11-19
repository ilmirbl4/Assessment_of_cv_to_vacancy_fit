"""Пул соединений asyncpg."""

from __future__ import annotations

import asyncio
import json
from urllib.parse import unquote, urlsplit

import asyncpg


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def ensure_database(dsn: str) -> None:
    """При SQLSTATE 3D000 создаёт целевую БД через служебную базу postgres."""
    try:
        conn = await asyncpg.connect(dsn)
    except asyncpg.InvalidCatalogNameError:
        name = unquote(urlsplit(dsn).path.removeprefix("/"))
        if not name or "\0" in name or len(name.encode()) > 63:
            raise ValueError("Укажите имя целевой базы в пути DATABASE_URL") from None
        admin = await asyncpg.connect(dsn, database="postgres")
        try:
            await admin.execute("SELECT pg_advisory_lock(7204117002)")
            if not await admin.fetchval("SELECT EXISTS(SELECT FROM pg_database WHERE datname=$1)", name):
                identifier = '"' + name.replace('"', '""') + '"'
                await admin.execute(f"CREATE DATABASE {identifier} TEMPLATE template0 ENCODING 'UTF8'")
        finally:
            await admin.close()
    else:
        await conn.close()


class Database:
    """Пул соединений; создаётся синхронно, открывается в ``lifespan`` (пул привязан к циклу событий)."""

    def __init__(self, dsn: str, min_size: int, max_size: int) -> None:
        """Запоминает параметры подключения, соединений не открывает."""
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self) -> None:
        """Открывает пул и регистрирует кодек ``jsonb``; запоминает цикл событий пула."""
        self.loop = asyncio.get_running_loop()
        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=self._min_size, max_size=self._max_size, init=_init_connection
        )

    async def close(self) -> None:
        """Закрывает пул; повторный вызов безопасен."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        """Открытый пул.

        Raises:
            RuntimeError: ``connect`` ещё не вызывался.
        """
        if self._pool is None:
            raise RuntimeError("Пул соединений не открыт: вызовите Database.connect()")
        return self._pool
