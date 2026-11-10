"""Резюме и их фрагменты на PostgreSQL."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import asyncpg

from app.db.database import Database
from app.domain.models import Embedding, Resume, ResumeFragment, ResumeStatus
from app.repositories.postgres._mapping import (
    as_uuid,
    from_uuid,
    sanitize,
    sql_template,
    vector_from_text,
    vector_to_text,
)
from app.repositories.postgres.registry import ActiveModels

_COLUMNS = (
    "id, user_id, file_name, file_type, text, status, error_message, uploaded_at, processed_at, model_version, "
    "embedding::text AS embedding"
)


class PgResumeRepository:
    """Резюме в таблицах ``resume`` и ``resume_fragment`` (одно на пользователя)."""

    def __init__(self, db: Database, active: ActiveModels) -> None:
        """Создаёт репозиторий."""
        self._db = db
        self._active = active

    @staticmethod
    def _resume(row: asyncpg.Record, fragments: tuple[ResumeFragment, ...]) -> Resume:
        return Resume(
            id=from_uuid(row["id"]),
            user_id=str(row["user_id"]),
            file_name=row["file_name"],
            file_type=row["file_type"],
            uploaded_at=row["uploaded_at"],
            status=ResumeStatus(row["status"]),
            error_message=row["error_message"],
            text=row["text"],
            fragments=fragments,
            embedding=vector_from_text(row["embedding"]) if row["embedding"] is not None else None,
            model_version=row["model_version"],
            processed_at=row["processed_at"],
        )

    async def get(self, user_id: str) -> Resume | None:
        """Возвращает текущее резюме пользователя вместе с фрагментами."""
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                sql_template("SELECT {cols} FROM resume WHERE user_id = $1", cols=_COLUMNS), user_id
            )
            if row is None:
                return None
            frags = await conn.fetch(
                "SELECT ord, text, span_start, span_end FROM resume_fragment WHERE resume_id = $1 ORDER BY ord",
                row["id"],
            )
        return self._resume(
            row, tuple(ResumeFragment(f["ord"], f["text"], f["span_start"], f["span_end"]) for f in frags)
        )

    async def _insert_fragments(
        self, conn: asyncpg.Connection, resume_id: str, fragments: Sequence[ResumeFragment]
    ) -> None:
        if not fragments:
            return
        await conn.execute(
            "INSERT INTO resume_fragment (resume_id, ord, text, span_start, span_end) "
            "SELECT $1, t.ord, t.text, t.s, t.e FROM unnest($2::int[], $3::text[], $4::int[], $5::int[]) "
            "AS t(ord, text, s, e) ORDER BY t.ord",
            resume_id,
            [f.ord for f in fragments],
            [sanitize(f.text) for f in fragments],
            [f.span_start for f in fragments],
            [f.span_end for f in fragments],
        )

    def _embedding_args(self, embedding: Embedding | None) -> tuple[int | None, int | None, str | None]:
        if embedding is None:
            return None, None, None
        return self._active.bi_id, len(embedding), vector_to_text(embedding)

    async def replace(self, resume: Resume) -> None:
        """Замещает резюме пользователя; каскад удаляет прежние фрагменты, покрытие и выдачу."""
        model_id, dim, vector = self._embedding_args(resume.embedding)
        text = sanitize(resume.text)
        resume_id = as_uuid(resume.id)
        async with self._db.pool.acquire() as conn, conn.transaction():
            await conn.execute("DELETE FROM resume WHERE user_id = $1", resume.user_id)
            await conn.execute(
                "INSERT INTO resume (id, user_id, file_name, file_type, text, char_count, status, error_message, "
                "embedding_model_id, embedding_dim, embedding, model_version, uploaded_at, processed_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::text::halfvec, $12, $13, $14)",
                resume_id,
                resume.user_id,
                sanitize(resume.file_name),
                resume.file_type,
                text,
                len(text),
                resume.status.value,
                sanitize(resume.error_message),
                model_id,
                dim,
                vector,
                resume.model_version,
                resume.uploaded_at,
                resume.processed_at,
            )
            await self._insert_fragments(conn, resume_id, resume.fragments)

    async def complete_processing(
        self,
        user_id: str,
        resume_id: str,
        *,
        status: str,
        error_message: str | None,
        fragments: Sequence[ResumeFragment],
        embedding: Embedding | None,
        model_version: str | None,
        processed_at: datetime,
    ) -> bool:
        """Записывает результат обработки; ``False``, если ``resume_id`` уже не текущий."""
        model_id, dim, vector = self._embedding_args(embedding)
        resume_id = as_uuid(resume_id)
        async with self._db.pool.acquire() as conn, conn.transaction():
            updated = await conn.execute(
                "UPDATE resume SET status = $3, error_message = $4, embedding_model_id = $5, embedding_dim = $6, "
                "embedding = $7::text::halfvec, model_version = $8, processed_at = $9 "
                "WHERE id = $1 AND user_id = $2",
                resume_id,
                user_id,
                status,
                sanitize(error_message),
                model_id,
                dim,
                vector,
                model_version,
                processed_at,
            )
            if updated == "UPDATE 0":
                return False
            await conn.execute("DELETE FROM resume_fragment WHERE resume_id = $1", resume_id)
            await self._insert_fragments(conn, resume_id, fragments)
        return True

    async def delete(self, user_id: str) -> None:
        """Удаляет резюме пользователя."""
        await self._db.pool.execute("DELETE FROM resume WHERE user_id = $1", user_id)

    async def list_processing_started_before(self, moment: datetime) -> list[Resume]:
        """Резюме в обработке, загруженные раньше ``moment``."""
        rows = await self._db.pool.fetch(
            sql_template("SELECT {cols} FROM resume WHERE status = 'processing' AND uploaded_at < $1", cols=_COLUMNS),
            moment,
        )
        return [self._resume(row, ()) for row in rows]
