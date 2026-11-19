"""Журнал запусков сбора вакансий на PostgreSQL."""

from __future__ import annotations

from datetime import datetime

import asyncpg

from app.db.database import Database
from app.domain.models import CollectionRun, RunMode, RunStatus
from app.repositories.postgres._mapping import as_uuid, from_uuid, sql_template

_COLUMNS = (
    "id, mode, snapshot_at, modified_from, complete, started_at, finished_at, status, pages_fetched, received, "
    "inserted, updated, unchanged, deactivated, failed, error_message"
)


def _run(row: asyncpg.Record) -> CollectionRun:
    return CollectionRun(
        id=from_uuid(row["id"]),
        mode=RunMode(row["mode"]),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        status=RunStatus(row["status"]),
        snapshot_at=row["snapshot_at"],
        modified_from=row["modified_from"],
        new_count=row["inserted"],
        updated_count=row["updated"],
        deactivated_count=row["deactivated"],
        error_count=row["failed"],
        complete=row["complete"],
        error_message=row["error_message"],
        unchanged_count=row["unchanged"],
        pages_fetched=row["pages_fetched"],
        received=row["received"],
    )


def _args(run: CollectionRun) -> tuple[object, ...]:
    return (
        as_uuid(run.id),
        run.mode.value,
        run.snapshot_at,
        run.modified_from,
        run.complete,
        run.started_at,
        run.finished_at,
        run.status.value,
        run.pages_fetched,
        run.received,
        run.new_count,
        run.updated_count,
        run.unchanged_count,
        run.deactivated_count,
        run.error_count,
        run.error_message,
    )


class PgCollectionRunRepository:
    """Запуски сбора в таблице ``ingestion_run``."""

    def __init__(self, db: Database) -> None:
        """Создаёт репозиторий."""
        self._db = db

    async def create(self, run: CollectionRun) -> None:
        """Создаёт запуск."""
        await self._db.pool.execute(
            sql_template(
                "INSERT INTO ingestion_run ({cols}) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)",
                cols=_COLUMNS,
            ),
            *_args(run),
        )

    async def update(self, run: CollectionRun) -> None:
        """Обновляет запуск."""
        await self._db.pool.execute(
            "UPDATE ingestion_run SET mode = $2, snapshot_at = $3, modified_from = $4, complete = $5, "
            "started_at = $6, finished_at = $7, status = $8, pages_fetched = $9, received = $10, inserted = $11, "
            "updated = $12, unchanged = $13, deactivated = $14, failed = $15, error_message = $16 WHERE id = $1",
            *_args(run),
        )

    async def get_running(self) -> CollectionRun | None:
        """Возвращает идущий запуск."""
        row = await self._db.pool.fetchrow(
            sql_template("SELECT {cols} FROM ingestion_run WHERE status = 'running' LIMIT 1", cols=_COLUMNS)
        )
        return _run(row) if row else None

    async def get_last_complete(self) -> CollectionRun | None:
        """Последний запуск с ``complete = true``."""
        row = await self._db.pool.fetchrow(
            sql_template(
                """SELECT {cols} FROM ingestion_run WHERE complete AND status='success'
                ORDER BY snapshot_at DESC LIMIT 1""",
                cols=_COLUMNS,
            )
        )
        return _run(row) if row else None

    async def list_started_since(self, moment: datetime) -> list[CollectionRun]:
        """Запуски, начатые не раньше ``moment``, от новых к старым."""
        rows = await self._db.pool.fetch(
            sql_template(
                "SELECT {cols} FROM ingestion_run WHERE started_at >= $1 ORDER BY started_at DESC", cols=_COLUMNS
            ),
            moment,
        )
        return [_run(r) for r in rows]

    async def fail_running(self, at: datetime, message: str) -> int:
        """Переводит зависшие запуски в ``failed``."""
        rows = await self._db.pool.fetch(
            "UPDATE ingestion_run SET status = 'failed', finished_at = $1, error_message = $2 "
            "WHERE status = 'running' RETURNING 1",
            at,
            message,
        )
        return len(rows)
