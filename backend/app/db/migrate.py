"""Применение SQL-миграций из ``migrations/*.sql`` (без Alembic и SQLAlchemy)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import asyncpg

from app.config import Settings

log = logging.getLogger("app.db.migrate")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
LOCK_KEY = 7_204_117_001


async def migrate(conn: asyncpg.Connection) -> list[str]:
    """Применяет ненакопленные миграции под консультативной блокировкой.

    Каждый файл и запись о версии выполняются в одной транзакции.

    Returns:
        Версии, применённые этим вызовом.
    """
    applied: list[str] = []
    await conn.execute("SELECT pg_advisory_lock($1)", LOCK_KEY)
    try:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migration ("
            "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        done = {row["version"] for row in await conn.fetch("SELECT version FROM schema_migration")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in done:
                continue
            async with conn.transaction():
                await conn.execute(path.read_text(encoding="utf-8"))
                await conn.execute("INSERT INTO schema_migration (version) VALUES ($1)", path.stem)
            applied.append(path.stem)
            log.info("Применена миграция %s", path.stem)
    finally:
        await conn.execute("SELECT pg_advisory_unlock($1)", LOCK_KEY)
    return applied


async def migrate_dsn(dsn: str) -> list[str]:
    """Открывает отдельное соединение и применяет миграции."""
    conn = await asyncpg.connect(dsn)
    try:
        return await migrate(conn)
    finally:
        await conn.close()


def main() -> None:
    """Точка входа ``python -m app.db.migrate``: DSN берётся из настроек (``DATABASE_URL``)."""
    settings = Settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL не задан")
    asyncio.run(migrate_dsn(settings.database_url))


if __name__ == "__main__":
    main()
