"""Реестр ML-моделей в таблице ``ml_model`` и HNSW-индекс активного би-энкодера."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from app.db.database import Database
from app.domain.models import ModelSpec
from app.repositories.postgres._mapping import sanitize

log = logging.getLogger("app.repositories.postgres.registry")


@dataclass(slots=True)
class ActiveModels:
    """Идентификаторы активных моделей; один объект на все репозитории."""

    ner_id: int = 0
    bi_id: int = 0
    bi_dim: int = 0
    ce_id: int = 0


class PgModelRegistry:
    """Регистрирует модели и делает их активными."""

    def __init__(self, db: Database, active: ActiveModels) -> None:
        """Создаёт реестр."""
        self._db = db
        self._active = active

    async def activate(self, specs: Sequence[ModelSpec]) -> None:
        """Для каждой спецификации: upsert, архивация прежней активной модели вида, активация; затем HNSW-индекс."""
        async with self._db.pool.acquire() as conn:
            for spec in specs:
                async with conn.transaction():
                    model_id: int = await conn.fetchval(
                        "INSERT INTO ml_model (kind, name, version, artifact_uri, embedding_dim, config) "
                        "VALUES ($1, $2, $3, $4, $5, $6) "
                        "ON CONFLICT (name, version) DO UPDATE SET artifact_uri = EXCLUDED.artifact_uri, "
                        "config = EXCLUDED.config RETURNING id",
                        spec.kind,
                        spec.name,
                        spec.version,
                        spec.artifact_uri,
                        spec.embedding_dim,
                        sanitize(dict(spec.config)),
                    )
                    await conn.execute(
                        "UPDATE ml_model SET status = 'archived' WHERE kind = $1 AND status = 'active' AND id <> $2",
                        spec.kind,
                        model_id,
                    )
                    await conn.execute("UPDATE ml_model SET status = 'active' WHERE id = $1", model_id)
                if spec.kind == "ner":
                    self._active.ner_id = model_id
                elif spec.kind == "cross_encoder":
                    self._active.ce_id = model_id
                else:
                    self._active.bi_id = model_id
                    self._active.bi_dim = spec.embedding_dim or 0
                    # CREATE INDEX CONCURRENTLY нельзя выполнять внутри транзакции.
                    await conn.execute(
                        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_vemb_hnsw_m{model_id} ON vacancy_embedding "
                        f"USING hnsw ((embedding::halfvec({spec.embedding_dim})) halfvec_ip_ops) "
                        f"WITH (m = 16, ef_construction = 64) WHERE model_id = {model_id}"
                    )
        log.info("Активные модели: %s", self._active)
