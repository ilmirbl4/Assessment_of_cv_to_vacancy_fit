"""Пул соединений asyncpg."""

from __future__ import annotations

import asyncio
import json

import asyncpg


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


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
