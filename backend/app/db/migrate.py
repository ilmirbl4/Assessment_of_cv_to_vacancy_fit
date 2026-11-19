"""Применение SQL-миграций из ``migrations/*.sql`` (без Alembic и SQLAlchemy)."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

import asyncpg

from app.config import Settings
from app.db.database import ensure_database
from app.db.validate import validate_original

log = logging.getLogger("app.db.migrate")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
LOCK_KEY = 7_204_117_001


async def require_migrated(conn: asyncpg.Connection) -> None:
    """Verify migration versions without creating or altering the schema."""
    marker = await conn.fetchval("SELECT to_regclass('public.schema_migration')")
    done = (
        {row["version"] for row in await conn.fetch("SELECT version FROM public.schema_migration")} if marker else set()
    )
    pending = sorted(path.stem for path in MIGRATIONS_DIR.glob("*.sql") if path.stem not in done)
    if pending:
        raise RuntimeError(
            f"DB_AUTO_MIGRATE=false: не применены миграции {', '.join(pending)}. "
            "Запустите python -m app.db.migrate перед стартом приложения."
        )


async def migrate(conn: asyncpg.Connection) -> list[str]:
    """Применяет ещё не зарегистрированные миграции под сеансовой блокировкой.

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
        if "0001_initial" in done:
            async with conn.transaction():
                await validate_original(conn, (MIGRATIONS_DIR / "0001_initial.sql").read_text())
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in done:
                continue
            async with conn.transaction():
                sql = path.read_text(encoding="utf-8")
                installed = False
                if path.stem == "0001_initial":
                    tables = {
                        r["tablename"]
                        for r in await conn.fetch(
                            "SELECT tablename FROM pg_tables "
                            "WHERE schemaname='public' AND tablename <> 'schema_migration'"
                        )
                    }
                    expected = set(re.findall(r"^CREATE TABLE (\w+)", sql, re.MULTILINE))
                    if tables and not expected <= tables:
                        raise RuntimeError("Существующая БД имеет несовместимую или неполную схему")
                    installed = bool(tables)
                    if installed:
                        await validate_original(conn, sql)
                if not installed:
                    await conn.execute(sql)
                await conn.execute("INSERT INTO schema_migration (version) VALUES ($1)", path.stem)
            applied.append(path.stem)
            log.info("Применена миграция %s", path.stem)
    finally:
        await conn.execute("SELECT pg_advisory_unlock($1)", LOCK_KEY)
    return applied


async def migrate_dsn(dsn: str) -> list[str]:
    """Открывает отдельное соединение и применяет миграции."""
    await ensure_database(dsn)
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
