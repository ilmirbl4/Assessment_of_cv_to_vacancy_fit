"""Вакансии, требования и векторы на PostgreSQL."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from app.db.database import Database
from app.domain.models import (
    Embedding,
    Employer,
    IngestState,
    MatchFilters,
    RequirementType,
    SourceField,
    UpsertResult,
    Vacancy,
    VacancyCandidate,
    VacancyRequirement,
)
from app.repositories.postgres._mapping import NO_REGION, sanitize, sql_template, vector_to_text
from app.repositories.postgres.registry import ActiveModels

log = logging.getLogger("app.repositories.postgres.vacancies")

# (колонка, тип элемента массива, выражение в SELECT; ``{}`` — имя колонки t).
_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("source_id", "text", "{}"),
    ("company_id", "bigint", "{}"),
    ("region_code", "varchar", "{}"),
    ("category_id", "integer", "{}"),
    ("employment_code", "text", "{}"),
    ("schedule_code", "text", "{}"),
    ("experience_code", "text", "{}"),
    ("education", "text", "{}::education_level"),
    ("title", "text", "{}"),
    ("requirements", "text", "{}"),
    ("duties", "text", "{}"),
    ("qualification", "text", "{}"),
    ("experience_years", "smallint", "{}"),
    ("salary_min", "integer", "{}"),
    ("salary_max", "integer", "{}"),
    ("vacancy_url", "text", "{}"),
    ("published_at", "date", "{}"),
    ("source_modified_at", "timestamptz", "{}"),
    ("first_seen_at", "timestamptz", "{}"),
    ("last_seen_at", "timestamptz", "{}"),
    ("updated_at", "timestamptz", "{}"),
    ("is_active", "boolean", "{}"),
    ("closed_at", "timestamptz", "{}"),
    ("content_hash", "bytea", "{}"),
    ("raw_payload", "text", "{}::jsonb"),
    ("source_fields", "text", "{}::jsonb"),
    ("model_version", "text", "{}"),
    ("last_ingestion_id", "uuid", "{}"),
)
_COL_NAMES = [c[0] for c in _COLUMNS]
_UNNEST = ", ".join(f"${i}::{t}[]" for i, (_, t, _) in enumerate(_COLUMNS, start=1))
_SELECT = ", ".join(expr.format(f"t.{name}") for name, _, expr in _COLUMNS)
_NAMES = ", ".join(_COL_NAMES)
_INSERT_SQL = sql_template(
    "INSERT INTO vacancy ({names}) SELECT {select} FROM unnest({unnest}) AS t({names}) "
    "ORDER BY t.source_id RETURNING id, source_id",
    names=_NAMES,
    select=_SELECT,
    unnest=_UNNEST,
)
_UPDATE_SQL = sql_template(
    "UPDATE vacancy v SET {assign} FROM (SELECT {select} FROM unnest({unnest}) AS t({names})) s "
    "WHERE v.source_id = s.source_id RETURNING v.id, v.source_id",
    assign=", ".join(f"{name} = s.{name}" for name in _COL_NAMES if name not in ("source_id", "first_seen_at")),
    select=_SELECT,
    unnest=_UNNEST,
    names=_NAMES,
)


@dataclass(slots=True)
class _Refs:
    """Идентификаторы справочников, нужные строкам пакета."""

    companies: dict[str, int]
    categories: dict[str, int]


def _company_code(vac: Vacancy) -> str:
    if vac.employer is not None:
        return vac.employer.source_code
    return "name:" + hashlib.sha1(vac.employer_name.encode("utf-8"), usedforsecurity=False).hexdigest()


class PgVacancyRepository:
    """Вакансии в таблицах ``vacancy``, ``vacancy_requirement``, ``vacancy_embedding``."""

    def __init__(self, db: Database, active: ActiveModels, ef_search: int) -> None:
        """Создаёт репозиторий; ``ef_search`` — значение ``hnsw.ef_search`` при отборе кандидатов."""
        self._db = db
        self._active = active
        self._ef_search = ef_search
        self._categories: dict[str, int] = {}

    # ---------- чтение ----------

    async def get(self, vacancy_id: str) -> Vacancy | None:
        """Возвращает вакансию по идентификатору источника."""
        return (await self.get_many([vacancy_id])).get(vacancy_id)

    async def get_many(self, ids: Collection[str]) -> dict[str, Vacancy]:
        """Возвращает найденные вакансии; ``raw`` не загружается."""
        if not ids:
            return {}
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT v.id, v.source_id, v.title, v.salary_min, v.salary_max, v.published_at, v.region_code, "
                "v.employment_code, v.schedule_code, v.experience_code, v.vacancy_url, v.source_fields, "
                "v.model_version, v.source_modified_at, v.is_active, v.first_seen_at, v.updated_at, v.closed_at, "
                "v.requirements, v.duties, v.qualification, v.education::text AS education, v.experience_years, "
                "v.content_hash, c.name AS company_name, c.source_code, c.inn, c.ogrn, c.kpp, c.site_url, "
                "r.name AS region_name, pc.name AS category "
                "FROM vacancy v JOIN company c ON c.id = v.company_id "
                "LEFT JOIN region r ON r.code = v.region_code "
                "LEFT JOIN profession_category pc ON pc.id = v.category_id "
                "WHERE v.source_id = ANY($1::text[])",
                list(ids),
            )
            reqs = await conn.fetch(
                "SELECT vacancy_id, requirement_type, text, source_field, span_start, span_end, is_preferred "
                "FROM vacancy_requirement WHERE vacancy_id = ANY($1::bigint[]) AND extractor_model_id = $2 "
                "ORDER BY vacancy_id, (source_field <> 'requirements'), span_start",
                [r["id"] for r in rows],
                self._active.ner_id,
            )
        by_vacancy: dict[int, list[VacancyRequirement]] = {}
        for req in reqs:
            by_vacancy.setdefault(req["vacancy_id"], []).append(
                VacancyRequirement(
                    RequirementType(req["requirement_type"]),
                    req["text"],
                    req["source_field"],
                    req["span_start"],
                    req["span_end"],
                    req["is_preferred"],
                )
            )
        return {r["source_id"]: self._vacancy(r, tuple(by_vacancy.get(r["id"], ()))) for r in rows}

    @staticmethod
    def _vacancy(row: asyncpg.Record, requirements: tuple[VacancyRequirement, ...]) -> Vacancy:
        return Vacancy(
            id=row["source_id"],
            title=row["title"],
            salary_from=row["salary_min"],
            salary_to=row["salary_max"],
            employer_name=row["company_name"],
            published_at=row["published_at"],
            region_code=row["region_code"],
            region_name=row["region_name"] or NO_REGION,
            employment_code=row["employment_code"],
            schedule_code=row["schedule_code"],
            experience_code=row["experience_code"],
            professional_area=row["category"],
            source_url=row["vacancy_url"],
            source_fields=tuple(SourceField(f["label"], f["value"]) for f in row["source_fields"]),
            requirements=requirements,
            embedding=None,
            model_version=row["model_version"],
            date_modify=row["source_modified_at"],
            is_active=row["is_active"],
            first_seen_at=row["first_seen_at"],
            updated_at=row["updated_at"],
            deactivated_at=row["closed_at"],
            requirements_section=row["requirements"] or "",
            duties_section=row["duties"] or "",
            qualification=row["qualification"],
            education=row["education"],
            experience_years=row["experience_years"],
            employer=Employer(row["source_code"], row["inn"], row["ogrn"], row["kpp"], row["site_url"]),
            content_hash=bytes(row["content_hash"]),
        )

    def search_sql(self, query: Embedding, filters: MatchFilters, limit: int) -> tuple[str, list[Any]]:
        """Собирает запрос отбора и его параметры; в запросе только заданные фильтры."""
        dim, model_id = self._active.bi_dim, self._active.bi_id
        args: list[Any] = [vector_to_text(query)]
        conditions = ["e.model_id = {model_id}", "v.is_active"]

        def param(value: Any) -> str:
            args.append(value)
            return f"${len(args)}"

        if filters.region_code is not None:
            conditions.append(f"v.region_code = {param(filters.region_code)}")
        if filters.employment_type is not None:
            conditions.append(f"v.employment_code = {param(filters.employment_type)}")
        if filters.schedule is not None:
            conditions.append(f"v.schedule_code = {param(filters.schedule)}")
        if filters.experience is not None:
            conditions.append(f"v.experience_code = {param(filters.experience)}")
        if filters.only_with_salary:
            conditions.append("(v.salary_min IS NOT NULL OR v.salary_max IS NOT NULL)")
        if filters.min_salary is not None:
            conditions.append(f"coalesce(v.salary_max, v.salary_min) >= {param(filters.min_salary)}")
        distance = "e.embedding::halfvec({dim}) <#> $1::text::halfvec({dim})"
        sql = sql_template(
            "SELECT v.source_id, v.published_at, -(" + distance + ") AS score "
            "FROM vacancy_embedding e JOIN vacancy v ON v.id = e.vacancy_id "
            "WHERE " + " AND ".join(conditions) + " ORDER BY " + distance + " LIMIT " + param(limit),
            model_id=model_id,
            dim=dim,
        )
        return sql, args

    async def search_candidates(self, query: Embedding, filters: MatchFilters, limit: int) -> list[VacancyCandidate]:
        """Отбор через HNSW-индекс активного би-энкодера."""
        sql, args = self.search_sql(query, filters, limit)
        async with self._db.pool.acquire() as conn, conn.transaction():
            await conn.execute(f"SET LOCAL hnsw.ef_search = {int(self._ef_search)}")
            await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
            await conn.execute("SET LOCAL plan_cache_mode = force_custom_plan")
            rows = await conn.fetch(sql, *args)
        found = [VacancyCandidate(r["source_id"], r["published_at"], float(r["score"])) for r in rows]
        found.sort(key=lambda c: (-c.score, -c.published_at.toordinal(), c.id))
        return found

    async def get_ingest_states(self, ids: Collection[str], model_version: str) -> dict[str, IngestState]:
        """Состояние вакансий; ``analysis_fresh`` — активна, совпала ``model_version`` и есть вектор активной модели."""
        if not ids:
            return {}
        rows = await self._db.pool.fetch(
            "SELECT v.source_id, v.source_modified_at, v.content_hash, v.is_active, "
            "(v.is_active AND v.model_version = $2 AND EXISTS ("
            "SELECT 1 FROM vacancy_embedding e WHERE e.vacancy_id = v.id AND e.model_id = $3)) AS fresh "
            "FROM vacancy v WHERE v.source_id = ANY($1::text[])",
            list(ids),
            model_version,
            self._active.bi_id,
        )
        return {
            r["source_id"]: IngestState(r["source_modified_at"], bytes(r["content_hash"]), r["is_active"], r["fresh"])
            for r in rows
        }

    # ---------- запись ----------

    async def upsert_batch(
        self,
        vacancies: Sequence[Vacancy],
        *,
        keep_analysis: Collection[str] = (),
        ingestion_run_id: str | None = None,
    ) -> UpsertResult:
        """Пишет пакет одной транзакцией; при ошибке данных повторяет построчно в отдельных savepoint."""
        batch = sorted(vacancies, key=lambda v: v.id)
        if not batch:
            return UpsertResult(0, 0, 0)
        keep = set(keep_analysis)
        try:
            async with self._db.pool.acquire() as conn, conn.transaction():
                result, fresh = await self._write(conn, batch, keep, ingestion_run_id)
            self._categories.update(fresh)
            return result
        except (asyncpg.DataError, asyncpg.IntegrityConstraintViolationError) as exc:
            log.warning("Пакет вакансий не записан целиком (%s), повтор построчно", type(exc).__name__)
        new = updated = unchanged = 0
        failed: list[str] = []
        async with self._db.pool.acquire() as conn, conn.transaction():
            for vac in batch:
                try:
                    async with conn.transaction():
                        part, fresh = await self._write(conn, [vac], keep, ingestion_run_id)
                except (asyncpg.DataError, asyncpg.IntegrityConstraintViolationError) as exc:
                    log.warning("Вакансия %s не записана: %s", vac.id, exc)
                    failed.append(vac.id)
                    continue
                new, updated, unchanged = new + part.new, updated + part.updated, unchanged + part.unchanged
                self._categories.update(fresh)
        return UpsertResult(new, updated, unchanged, tuple(failed))

    async def _write(
        self, conn: asyncpg.Connection, batch: list[Vacancy], keep: set[str], run_id: str | None
    ) -> tuple[UpsertResult, dict[str, int]]:
        refs, fresh = await self._reference_rows(conn, batch)
        existing = {
            r["source_id"]: r
            for r in await conn.fetch(
                "SELECT id, source_id, source_modified_at, content_hash, model_version, is_active FROM vacancy "
                "WHERE source_id = ANY($1::text[]) ORDER BY source_id FOR UPDATE",
                [v.id for v in batch],
            )
        }
        to_insert: list[Vacancy] = []
        to_update: list[Vacancy] = []
        unchanged: list[Vacancy] = []
        for vac in batch:
            old = existing.get(vac.id)
            if old is None:
                to_insert.append(vac)
            elif (
                old["source_modified_at"] != vac.date_modify
                or bytes(old["content_hash"]) != vac.content_hash
                or old["model_version"] != vac.model_version
                or not old["is_active"]
            ):
                to_update.append(vac)
            else:
                unchanged.append(vac)
        ids: dict[str, int] = {}
        for rows, sql in ((to_insert, _INSERT_SQL), (to_update, _UPDATE_SQL)):
            if rows:
                columns = self._columns(rows, refs, existing, keep, run_id)
                ids.update({r["source_id"]: r["id"] for r in await conn.fetch(sql, *columns)})
        if unchanged:
            await conn.execute(
                "UPDATE vacancy SET last_seen_at = $2, last_ingestion_id = coalesce($3, last_ingestion_id) "
                "WHERE source_id = ANY($1::text[])",
                [v.id for v in unchanged],
                max(v.updated_at for v in unchanged),
                run_id,
            )
        await self._write_analysis(conn, [v for v in (*to_insert, *to_update) if v.id not in keep], ids)
        return UpsertResult(len(to_insert), len(to_update), len(unchanged)), fresh

    async def _reference_rows(self, conn: asyncpg.Connection, batch: list[Vacancy]) -> tuple[_Refs, dict[str, int]]:
        regions: dict[str, str] = {}
        for vac in batch:
            if vac.region_code is not None and (vac.region_code not in regions or vac.region_name != NO_REGION):
                regions[vac.region_code] = vac.region_name or NO_REGION
        if regions:
            codes = sorted(regions)
            await conn.execute(
                "INSERT INTO region (code, name) SELECT * FROM unnest($1::varchar[], $2::text[]) "
                "ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name "
                "WHERE EXCLUDED.name <> $3 AND region.name <> EXCLUDED.name",
                codes,
                [sanitize(regions[c]) for c in codes],
                NO_REGION,
            )
        employers: dict[str, tuple[str, Employer]] = {}
        for vac in batch:
            code = _company_code(vac)
            employers.setdefault(code, (vac.employer_name, vac.employer or Employer(code)))
        codes = sorted(employers)
        stamp = max(v.updated_at for v in batch)
        company_rows = await conn.fetch(
            "INSERT INTO company (source_code, name, inn, ogrn, kpp, site_url, updated_at) "
            "SELECT * FROM unnest($1::text[], $2::text[], $3::varchar[], $4::varchar[], $5::varchar[], $6::text[], "
            "$7::timestamptz[]) ORDER BY 1 "
            "ON CONFLICT (source_code) DO UPDATE SET name = EXCLUDED.name, "
            "inn = coalesce(EXCLUDED.inn, company.inn), ogrn = coalesce(EXCLUDED.ogrn, company.ogrn), "
            "kpp = coalesce(EXCLUDED.kpp, company.kpp), site_url = coalesce(EXCLUDED.site_url, company.site_url), "
            "updated_at = EXCLUDED.updated_at RETURNING id, source_code",
            codes,
            [sanitize(employers[c][0]) for c in codes],
            [employers[c][1].inn for c in codes],
            [employers[c][1].ogrn for c in codes],
            [employers[c][1].kpp for c in codes],
            [sanitize(employers[c][1].site_url) for c in codes],
            [stamp] * len(codes),
        )
        names = sorted({sanitize(v.professional_area) for v in batch if v.professional_area})
        missing = [n for n in names if n not in self._categories]
        fresh: dict[str, int] = {}
        if missing:
            await conn.execute(
                "INSERT INTO profession_category (name) SELECT n FROM unnest($1::text[]) AS n "
                "WHERE NOT EXISTS (SELECT 1 FROM profession_category c WHERE c.name = n) ORDER BY n "
                "ON CONFLICT DO NOTHING",
                missing,
            )
            fresh = {
                r["name"]: r["id"]
                for r in await conn.fetch(
                    "SELECT id, name FROM profession_category WHERE name = ANY($1::text[])", missing
                )
            }
        categories = {**{n: self._categories[n] for n in names if n in self._categories}, **fresh}
        return _Refs({r["source_code"]: r["id"] for r in company_rows}, categories), fresh

    @staticmethod
    def _columns(
        rows: list[Vacancy], refs: _Refs, existing: dict[str, asyncpg.Record], keep: set[str], run_id: str | None
    ) -> list[list[Any]]:
        values: dict[str, list[Any]] = {name: [] for name in _COL_NAMES}
        for vac in rows:
            old = existing.get(vac.id)
            kept = vac.id in keep and old is not None
            closed = None if vac.is_active else (vac.deactivated_at or vac.updated_at)
            row = {
                "source_id": vac.id,
                "company_id": refs.companies[_company_code(vac)],
                "region_code": vac.region_code,
                "category_id": refs.categories.get(sanitize(vac.professional_area)) if vac.professional_area else None,
                "employment_code": vac.employment_code,
                "schedule_code": vac.schedule_code,
                "experience_code": vac.experience_code,
                "education": vac.education,
                "title": sanitize(vac.title),
                "requirements": sanitize(vac.requirements_section) or None,
                "duties": sanitize(vac.duties_section) or None,
                "qualification": sanitize(vac.qualification),
                "experience_years": vac.experience_years,
                "salary_min": vac.salary_from,
                "salary_max": vac.salary_to,
                "vacancy_url": vac.source_url,
                "published_at": vac.published_at,
                "source_modified_at": vac.date_modify,
                "first_seen_at": vac.first_seen_at,
                "last_seen_at": vac.updated_at,
                "updated_at": vac.updated_at,
                "is_active": vac.is_active,
                "closed_at": closed,
                "content_hash": vac.content_hash,
                "raw_payload": _json(sanitize(dict(vac.raw))),
                "source_fields": _json([{"label": f.label, "value": sanitize(f.value)} for f in vac.source_fields]),
                "model_version": old["model_version"] if kept and old is not None else vac.model_version,
                "last_ingestion_id": run_id,
            }
            for name in _COL_NAMES:
                values[name].append(row[name])
        return [values[name] for name in _COL_NAMES]

    async def _write_analysis(self, conn: asyncpg.Connection, rows: list[Vacancy], ids: dict[str, int]) -> None:
        """Заменяет требования и вектор активных моделей у вакансий вне ``keep_analysis``."""
        if not rows:
            return
        all_ids = [ids[v.id] for v in rows]
        await conn.execute(
            "DELETE FROM vacancy_requirement WHERE vacancy_id = ANY($1::bigint[]) AND extractor_model_id = $2",
            all_ids,
            self._active.ner_id,
        )
        flat = [(ids[v.id], r) for v in rows for r in v.requirements]
        if flat:
            await conn.execute(
                "INSERT INTO vacancy_requirement (vacancy_id, requirement_type, is_preferred, extractor_model_id, "
                "text, source_field, span_start, span_end) "
                "SELECT t.vid, t.rtype, t.pref, $1, t.text, t.field, t.s, t.e "
                "FROM unnest($2::bigint[], $3::text[], $4::boolean[], $5::text[], $6::text[], $7::int[], $8::int[]) "
                "AS t(vid, rtype, pref, text, field, s, e) ORDER BY t.vid, t.field DESC, t.s",
                self._active.ner_id,
                [vid for vid, _ in flat],
                [r.type.value for _, r in flat],
                [r.is_preferred for _, r in flat],
                [sanitize(r.text) for _, r in flat],
                [r.source_field for _, r in flat],
                [r.span_start for _, r in flat],
                [r.span_end for _, r in flat],
            )
        with_vector = [v for v in rows if v.embedding is not None and v.is_active]
        with_ids = {v.id for v in with_vector}
        without = [ids[v.id] for v in rows if v.id not in with_ids]
        if without:
            await conn.execute("DELETE FROM vacancy_embedding WHERE vacancy_id = ANY($1::bigint[])", without)
        if with_vector:
            vectors = [v.embedding for v in with_vector if v.embedding is not None]
            await conn.execute(
                "INSERT INTO vacancy_embedding (vacancy_id, model_id, dim, embedding, content_hash) "
                "SELECT t.vid, $1, t.dim, t.emb::halfvec, t.hash "
                "FROM unnest($2::bigint[], $3::int[], $4::text[], $5::bytea[]) AS t(vid, dim, emb, hash) "
                "ORDER BY t.vid ON CONFLICT (vacancy_id, model_id) DO UPDATE SET dim = EXCLUDED.dim, "
                "embedding = EXCLUDED.embedding, content_hash = EXCLUDED.content_hash, created_at = now()",
                self._active.bi_id,
                [ids[v.id] for v in with_vector],
                [len(vec) for vec in vectors],
                [vector_to_text(vec) for vec in vectors],
                [v.content_hash for v in with_vector],
            )

    async def _close(self, conn: asyncpg.Connection, rows: list[asyncpg.Record]) -> int:
        if rows:
            ids = [r["id"] for r in rows]
            await conn.execute("DELETE FROM vacancy_embedding WHERE vacancy_id = ANY($1::bigint[])", ids)
        return len(rows)

    async def deactivate_missing(self, seen_ids: Collection[str], at: datetime) -> int:
        """Деактивирует активные вакансии вне ``seen_ids`` и удаляет их векторы."""
        async with self._db.pool.acquire() as conn, conn.transaction():
            rows = await conn.fetch(
                "UPDATE vacancy v SET is_active = false, closed_at = $2, updated_at = $2 "
                "WHERE v.is_active AND NOT EXISTS (SELECT 1 FROM unnest($1::text[]) s(id) WHERE s.id = v.source_id) "
                "RETURNING v.id",
                list(seen_ids),
                at,
            )
            return await self._close(conn, rows)

    async def deactivate_ids(self, ids: Collection[str], at: datetime) -> int:
        """Деактивирует перечисленные активные вакансии и удаляет их векторы."""
        if not ids:
            return 0
        async with self._db.pool.acquire() as conn, conn.transaction():
            rows = await conn.fetch(
                "UPDATE vacancy SET is_active = false, closed_at = $2, updated_at = $2 "
                "WHERE is_active AND source_id = ANY($1::text[]) RETURNING id",
                list(ids),
                at,
            )
            return await self._close(conn, rows)

    async def count_active(self) -> int:
        """Число активных вакансий."""
        count: int = await self._db.pool.fetchval("SELECT count(*) FROM vacancy WHERE is_active")
        return count


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
