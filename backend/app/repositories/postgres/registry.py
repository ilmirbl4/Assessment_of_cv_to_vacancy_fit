"""Staged model registry; activation is a single transaction after preparation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.database import Database
from app.repositories.postgres._mapping import sanitize


@dataclass(slots=True)
class ActiveModels:
    """IDs shared by repositories; HTTP writes are gated until activation."""

    ner_id: int = 0
    bi_id: int = 0
    bi_dim: int = 0
    ce_id: int = 0


class PgModelRegistry:
    """Register staging models without altering the active database set."""

    def __init__(self, db: Database, active: ActiveModels) -> None:
        """Binds the registry to the database and the shared active IDs."""
        self._db, self._active = db, active

    async def stage(self, specs: Any) -> dict[str, int]:
        """Registers artifact identities without activating them."""
        old = {
            r["kind"]: r["id"] for r in await self._db.pool.fetch("SELECT id,kind FROM ml_model WHERE status='active'")
        }
        async with self._db.pool.acquire() as conn, conn.transaction():
            for spec in specs:
                model_id = await conn.fetchval(
                    """INSERT INTO ml_model(kind,name,version,artifact_uri,embedding_dim,config)
                    VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(name,version) DO UPDATE
                    SET artifact_uri=excluded.artifact_uri RETURNING id""",
                    spec.kind,
                    spec.name,
                    spec.version,
                    spec.artifact_uri,
                    spec.embedding_dim,
                    sanitize(dict(spec.config)),
                )
                if spec.kind == "ner":
                    self._active.ner_id = model_id
                elif spec.kind == "cross_encoder":
                    self._active.ce_id = model_id
                else:
                    self._active.bi_id, self._active.bi_dim = model_id, spec.embedding_dim
        return old

    async def index(self) -> None:
        """Creates the HNSW index for the active encoder, repairing an invalid one."""
        model_id, dim = self._active.bi_id, self._active.bi_dim
        name = f"ix_vemb_hnsw_m{model_id}"
        async with self._db.pool.acquire() as conn:
            valid = await conn.fetchval(
                "SELECT indisvalid AND indisready FROM pg_index WHERE indexrelid=to_regclass($1)", name
            )
            if valid is False:
                await conn.execute(f"DROP INDEX {name}")
            await conn.execute(f"""CREATE INDEX IF NOT EXISTS {name} ON vacancy_embedding
                USING hnsw ((embedding::halfvec({dim})) halfvec_ip_ops)
                WITH(m=16,ef_construction=64) WHERE model_id={model_id}""")

    async def commit(self, conn: Any) -> None:
        """Switches model status inside the caller's transaction."""
        ids = [self._active.ner_id, self._active.bi_id, self._active.ce_id]
        await conn.execute("UPDATE ml_model SET status='archived' WHERE status='active' AND NOT id=ANY($1::int[])", ids)
        await conn.execute("UPDATE ml_model SET status='active' WHERE id=ANY($1::int[])", ids)

    async def activate(self, specs: Any) -> None:
        """Empty-database helper; populated databases use bootstrap rebuild."""
        await self.stage(specs)
        await self.index()
        async with self._db.pool.acquire() as conn, conn.transaction():
            await self.commit(conn)
