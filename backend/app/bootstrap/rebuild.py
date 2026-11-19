"""Prepare changed analysis separately; switch the corpus atomically."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.collector.normalizer import normalize
from app.ml.vacancy_text import vacancy_embedding_text
from app.repositories.postgres._mapping import vector_to_text


def prepare(raw: Any, ml: Any, need_bi: Any, need_ner: Any) -> Any:
    """Only recompute affected neural stages."""
    norm = normalize(raw)
    result: dict[str, Any] = {
        "hash": norm.content_hash.hex(),
        "requirements_text": norm.requirements,
        "duties_text": norm.duties,
    }
    if need_bi:
        result["embedding"] = list(
            ml.bi_encoder.encode([vacancy_embedding_text(norm.title, norm.requirements, norm.duties)])[0]
        )
    if need_ner:
        result["requirements"] = [{**asdict(r), "type": r.type.value} for r in ml.extractor.extract(norm)]
    return result


async def rebuild(container: Any, old: Any, pid: Any) -> Any:
    """Checkpoint each staged item; no active vectors or resume data are overwritten."""
    db, ml = container.database, container.ml
    models = container.repos.models
    ids = models._active
    job = "rebuild:" + pid
    await db.pool.execute(
        """INSERT INTO processing_job(id,kind,total)
        SELECT $1,'rebuild',count(*) FROM vacancy ON CONFLICT(id) DO NOTHING""",
        job,
    )
    total = await db.pool.fetchval("SELECT count(*) FROM vacancy")
    await db.pool.execute("UPDATE pipeline_state SET phase='rebuild',total=$1,progress=0", total)
    cursor = 0
    while True:
        rows = await db.pool.fetch(
            """SELECT v.id,v.raw_payload,v.content_hash,v.model_version,
            EXISTS(SELECT FROM vacancy_embedding e WHERE e.vacancy_id=v.id AND e.model_id=$2
                AND e.content_hash=v.content_hash) has_vector,
            EXISTS(SELECT FROM vacancy_analysis a WHERE a.vacancy_id=v.id AND a.pipeline_id=$3
                AND a.content_hash=v.content_hash) analysed,
            s.content_hash staged_hash
            FROM vacancy v LEFT JOIN staged_vacancy s ON s.vacancy_id=v.id AND s.job_id=$4
            WHERE v.id>$1 ORDER BY v.id LIMIT 32""",
            cursor,
            ids.bi_id,
            ml.vacancy_model_version,
            job,
        )
        if not rows:
            break
        for row in rows:
            need_bi = not row["has_vector"]
            legacy = row["model_version"] == ml.vacancy_model_version and old.get("ner") == ids.ner_id
            need_ner = not (row["analysed"] or legacy)
            if (need_bi or need_ner) and row["staged_hash"] != row["content_hash"]:
                analysis = await ml.run(prepare, row["raw_payload"], ml, need_bi, need_ner)
                async with db.pool.acquire() as conn, conn.transaction():
                    await conn.execute(
                        """INSERT INTO staged_vacancy(job_id,vacancy_id,content_hash,analysis)
                        VALUES($1,$2,$3,$4) ON CONFLICT(job_id,vacancy_id) DO UPDATE
                        SET content_hash=excluded.content_hash,analysis=excluded.analysis""",
                        job,
                        row["id"],
                        row["content_hash"],
                        analysis,
                    )
                    await conn.execute(
                        "UPDATE processing_job SET cursor=$2,updated_at=now() WHERE id=$1", job, row["id"]
                    )
            cursor = row["id"]
        await db.pool.execute(
            "UPDATE pipeline_state SET progress=(SELECT count(*) FROM vacancy WHERE id<=$1),updated_at=now()", cursor
        )
    # Store new resume vectors and fragments before activation.
    resumes = await db.pool.fetch("SELECT id,text FROM resume WHERE status='ready'")
    for row in resumes:
        await container.resumes.stage_analysis(row["id"], row["text"])
    return job


async def apply_staged(container: Any, job: Any, pid: Any) -> Any:
    """Validate hashes and atomically switch all derived values and model IDs."""
    db, ml, registry = container.database, container.ml, container.repos.models
    ids = registry._active
    async with db.pool.acquire() as conn, conn.transaction():
        changed = await conn.fetchval(
            """SELECT count(*) FROM staged_vacancy s JOIN vacancy v ON v.id=s.vacancy_id
            WHERE s.job_id=$1 AND s.content_hash<>v.content_hash""",
            job,
        )
        if changed:
            raise RuntimeError("Корпус изменился во время пересчёта; повторите запуск")
        async for row in conn.cursor(
            "SELECT vacancy_id,analysis FROM staged_vacancy WHERE job_id=$1 ORDER BY vacancy_id", job, prefetch=32
        ):
            vid, a = row["vacancy_id"], row["analysis"]
            if "embedding" in a:
                await conn.execute(
                    """INSERT INTO vacancy_embedding(vacancy_id,model_id,dim,embedding,content_hash)
                    VALUES($1,$2,$3,$4::text::halfvec,$5) ON CONFLICT(vacancy_id,model_id) DO UPDATE
                    SET dim=excluded.dim,embedding=excluded.embedding,content_hash=excluded.content_hash""",
                    vid,
                    ids.bi_id,
                    ids.bi_dim,
                    vector_to_text(a["embedding"]),
                    bytes.fromhex(a["hash"]),
                )
            if "requirements" in a:
                await conn.execute(
                    "DELETE FROM vacancy_requirement WHERE vacancy_id=$1 AND extractor_model_id=$2", vid, ids.ner_id
                )
                for r in a["requirements"]:
                    await conn.execute(
                        """INSERT INTO vacancy_requirement(vacancy_id,extractor_model_id,requirement_type,
                        text,source_field,span_start,span_end,is_preferred) VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",
                        vid,
                        ids.ner_id,
                        r["type"],
                        r["text"],
                        r["source_field"],
                        r["span_start"],
                        r["span_end"],
                        r["is_preferred"],
                    )
            await conn.execute(
                "UPDATE vacancy SET requirements=$2,duties=$3,content_hash=$4 WHERE id=$1",
                vid,
                a["requirements_text"],
                a["duties_text"],
                bytes.fromhex(a["hash"]),
            )
        await conn.execute("UPDATE vacancy SET model_version=$1", ml.vacancy_model_version)
        await conn.execute(
            """INSERT INTO vacancy_analysis(vacancy_id,pipeline_id,content_hash,ner_id,bi_id)
            SELECT id,$1,content_hash,$2,$3 FROM vacancy ON CONFLICT(vacancy_id,pipeline_id) DO UPDATE
            SET content_hash=excluded.content_hash""",
            ml.vacancy_model_version,
            ids.ner_id,
            ids.bi_id,
        )
        missing = await conn.fetchval(
            """SELECT count(*) FROM vacancy v WHERE v.is_active AND NOT EXISTS
            (SELECT FROM vacancy_embedding e WHERE e.vacancy_id=v.id AND e.model_id=$1
                AND e.content_hash=v.content_hash AND e.dim=$2)""",
            ids.bi_id,
            ids.bi_dim,
        )
        if missing:
            raise RuntimeError(f"Не готовы векторы {missing} вакансий")
        from app.domain.models import ResumeFragment

        resume_rows = await conn.fetch(
            """SELECT r.id,a.fragments FROM resume r JOIN resume_analysis a ON a.resume_id=r.id
            WHERE a.pipeline_id=$1 AND r.model_version IS DISTINCT FROM a.pipeline_id""",
            ml.resume_model_version,
        )
        for row in resume_rows:
            await conn.execute("DELETE FROM resume_fragment WHERE resume_id=$1", row["id"])
            await container.repos.resumes._insert_fragments(
                conn,
                row["id"],
                [ResumeFragment(f["ord"], f["text"], f["span_start"], f["span_end"]) for f in row["fragments"]],
            )
        await conn.execute(
            """UPDATE resume r SET embedding=a.embedding,embedding_model_id=a.model_id,
            embedding_dim=a.dim,model_version=a.pipeline_id FROM resume_analysis a
            WHERE a.resume_id=r.id AND a.pipeline_id=$1""",
            ml.resume_model_version,
        )
        previous = await conn.fetchval("SELECT pipeline_id FROM pipeline_state")
        if previous != pid:
            await conn.execute("DELETE FROM recommendation_set")
            await conn.execute("DELETE FROM requirement_coverage")
            await conn.execute("DELETE FROM match_cache WHERE pipeline_id<>$1", pid)
        model_id, dim = ids.bi_id, ids.bi_dim
        index_name = f"ix_vemb_hnsw_m{model_id}"
        valid = await conn.fetchval(
            "SELECT indisvalid AND indisready FROM pg_index WHERE indexrelid=to_regclass($1)", index_name
        )
        if valid is False:
            await conn.execute(f"DROP INDEX {index_name}")
        await conn.execute(
            f"""CREATE INDEX IF NOT EXISTS {index_name} ON vacancy_embedding
            USING hnsw ((embedding::halfvec({dim})) halfvec_ip_ops)
            WITH(m=16,ef_construction=64) WHERE model_id={model_id}"""
        )
        await registry.commit(conn)
        await conn.execute("UPDATE processing_job SET status='success',updated_at=now() WHERE id=$1", job)
        await conn.execute(
            "UPDATE pipeline_state SET pipeline_id=$1,phase='ready',progress=total,error=NULL,updated_at=now()", pid
        )
