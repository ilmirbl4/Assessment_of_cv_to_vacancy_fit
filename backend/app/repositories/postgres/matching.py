"""Избранное, текущий подбор и метрики на PostgreSQL."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import asdict
from datetime import UTC

import asyncpg

from app.config import MAX_RESULTS
from app.db.database import Database
from app.domain.models import (
    Favorite,
    FavoriteFromRunEvent,
    MatchFilters,
    MatchingEvent,
    MatchResult,
    MatchRun,
    RequirementType,
    RequirementVerdict,
    VacancyRequirement,
)
from app.repositories.errors import AlreadyExistsError
from app.repositories.postgres._mapping import status_from_db, status_to_db
from app.repositories.postgres.registry import ActiveModels


class PgFavoriteRepository:
    """Избранное в таблице ``favorite``."""

    def __init__(self, db: Database) -> None:
        """Создаёт репозиторий."""
        self._db = db

    async def list_for_user(self, user_id: str) -> list[Favorite]:
        """Избранное пользователя по убыванию даты добавления."""
        rows = await self._db.pool.fetch(
            "SELECT f.user_id, v.source_id, f.created_at FROM favorite f JOIN vacancy v ON v.id = f.vacancy_id "
            "WHERE f.user_id = $1 ORDER BY f.created_at DESC, v.id",
            user_id,
        )
        return [Favorite(str(r["user_id"]), r["source_id"], r["created_at"]) for r in rows]

    async def add(self, favorite: Favorite) -> None:
        """Добавляет запись (повтор даёт ``AlreadyExistsError``); вакансия из текущей выдачи растит ``favorites``."""
        try:
            async with self._db.pool.acquire() as conn, conn.transaction():
                status = await conn.execute(
                    "INSERT INTO favorite (user_id, vacancy_id, created_at) "
                    "SELECT $1, v.id, $3 FROM vacancy v WHERE v.source_id = $2",
                    favorite.user_id,
                    favorite.vacancy_id,
                    favorite.added_at,
                )
                if status == "INSERT 0 0":
                    raise LookupError(f"вакансия {favorite.vacancy_id} не найдена")
                await conn.execute(
                    "UPDATE quality_daily_stat q SET favorites = q.favorites + 1 "
                    "FROM recommendation_set s JOIN recommendation_item i ON i.user_id = s.user_id "
                    "JOIN vacancy v ON v.id = i.vacancy_id "
                    "WHERE s.user_id = $1 AND v.source_id = $2 AND q.day = (s.computed_at AT TIME ZONE 'UTC')::date "
                    "AND q.bi_encoder_id = s.bi_encoder_id AND q.cross_encoder_id = s.cross_encoder_id "
                    "AND q.rank = i.rank",
                    favorite.user_id,
                    favorite.vacancy_id,
                )
        except asyncpg.UniqueViolationError as exc:
            raise AlreadyExistsError(f"{favorite.user_id}:{favorite.vacancy_id}") from exc

    async def remove(self, user_id: str, vacancy_id: str) -> bool:
        """Удаляет запись; ``False``, если её не было."""
        rows = await self._db.pool.fetch(
            "DELETE FROM favorite f USING vacancy v WHERE f.vacancy_id = v.id AND f.user_id = $1 "
            "AND v.source_id = $2 RETURNING 1",
            user_id,
            vacancy_id,
        )
        return bool(rows)

    async def exists(self, user_id: str, vacancy_id: str) -> bool:
        """Есть ли вакансия в избранном."""
        found: bool = await self._db.pool.fetchval(
            "SELECT EXISTS (SELECT 1 FROM favorite f JOIN vacancy v ON v.id = f.vacancy_id "
            "WHERE f.user_id = $1 AND v.source_id = $2)",
            user_id,
            vacancy_id,
        )
        return found

    async def delete_all_for_user(self, user_id: str) -> None:
        """Удаляет всё избранное пользователя."""
        await self._db.pool.execute("DELETE FROM favorite WHERE user_id = $1", user_id)


class PgMatchRunRepository:
    """Текущая выдача пользователя: ``recommendation_set``, ``recommendation_item``, ``requirement_coverage``."""

    def __init__(self, db: Database, active: ActiveModels) -> None:
        """Создаёт репозиторий."""
        self._db = db
        self._active = active

    async def save_current(self, run: MatchRun) -> None:
        """Заменяет выдачу пользователя, пишет кэш покрытия и показы одной транзакцией."""
        bi_id, ce_id, ner_id = self._active.bi_id, self._active.ce_id, self._active.ner_id
        results = run.results
        async with self._db.pool.acquire() as conn, conn.transaction():
            await conn.execute("DELETE FROM recommendation_set WHERE user_id = $1", run.user_id)
            await conn.execute(
                "INSERT INTO recommendation_set (user_id, run_id, resume_id, bi_encoder_id, cross_encoder_id, "
                "filters, candidates_k, top_n, computed_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                run.user_id,
                run.id,
                run.resume_id,
                bi_id,
                ce_id,
                asdict(run.filters),
                run.candidates_k,
                min(MAX_RESULTS, run.candidates_k),
                run.created_at,
            )
            if results:
                await conn.execute(
                    "INSERT INTO recommendation_item (user_id, rank, vacancy_id, retrieval_score, coverage_score, "
                    "final_score, match_percent) "
                    "SELECT $1, t.rank, v.id, t.retrieval, t.coverage, t.coverage, t.percent "
                    "FROM unnest($2::int[], $3::text[], $4::real[], $5::real[], $6::smallint[]) "
                    "AS t(rank, source_id, retrieval, coverage, percent) JOIN vacancy v ON v.source_id = t.source_id",
                    run.user_id,
                    list(range(1, len(results) + 1)),
                    [r.vacancy_id for r in results],
                    [r.retrieval_score for r in results],
                    [min(1.0, max(0.0, r.coverage_score)) for r in results],
                    [r.match_percent for r in results],
                )
            rows = [(r.vacancy_id, v) for r in results for v in r.verdicts if v.requirement is not None]
            if rows:
                await conn.execute(
                    "INSERT INTO requirement_coverage (resume_id, requirement_id, model_id, status, score, "
                    "best_fragment_id, computed_at) "
                    "SELECT $1, q.id, $2, t.status, least(1, greatest(0, t.score)), f.id, $3 "
                    "FROM unnest($4::text[], $5::text[], $6::int[], $7::int[], $8::text[], $9::real[], $10::int[]) "
                    "AS t(source_id, field, s, e, status, score, ord) "
                    "JOIN vacancy v ON v.source_id = t.source_id "
                    "JOIN vacancy_requirement q ON q.vacancy_id = v.id AND q.extractor_model_id = $11 "
                    "AND q.source_field = t.field AND q.span_start = t.s AND q.span_end = t.e "
                    "LEFT JOIN resume_fragment f ON f.resume_id = $1 AND f.ord = t.ord "
                    "ON CONFLICT (resume_id, requirement_id, model_id) DO UPDATE SET status = EXCLUDED.status, "
                    "score = EXCLUDED.score, best_fragment_id = EXCLUDED.best_fragment_id, "
                    "computed_at = EXCLUDED.computed_at",
                    run.resume_id,
                    ce_id,
                    run.created_at,
                    [vid for vid, _ in rows],
                    [v.requirement.source_field for _, v in rows if v.requirement],
                    [v.requirement.span_start for _, v in rows if v.requirement],
                    [v.requirement.span_end for _, v in rows if v.requirement],
                    [status_to_db(v.status) for _, v in rows],
                    [v.score for _, v in rows],
                    [v.fragment_ord for _, v in rows],
                    ner_id,
                )
            if results:
                await conn.execute(
                    "INSERT INTO quality_daily_stat (day, bi_encoder_id, cross_encoder_id, rank, impressions) "
                    "SELECT $1, $2, $3, g, 1 FROM generate_series(1, $4::int) g "
                    "ON CONFLICT (day, bi_encoder_id, cross_encoder_id, rank) "
                    "DO UPDATE SET impressions = quality_daily_stat.impressions + 1",
                    run.created_at.astimezone(UTC).date(),
                    bi_id,
                    ce_id,
                    len(results),
                )

    async def get_current(self, user_id: str) -> MatchRun | None:
        """Восстанавливает выдачу одним запросом (``db_design.md``, разд. 8.5)."""
        async with self._db.pool.acquire() as conn:
            head = await conn.fetchrow(
                "SELECT run_id, resume_id, filters, candidates_k, computed_at, cross_encoder_id "
                "FROM recommendation_set WHERE user_id = $1",
                user_id,
            )
            if head is None:
                return None
            rows = await conn.fetch(
                "SELECT i.rank, v.source_id, i.match_percent, i.coverage_score, i.retrieval_score, "
                "r.requirement_type, r.text, r.source_field, r.span_start, r.span_end, r.is_preferred, "
                "c.status, c.score, f.ord, f.text AS quote "
                "FROM recommendation_item i JOIN vacancy v ON v.id = i.vacancy_id "
                "LEFT JOIN vacancy_requirement r ON r.vacancy_id = v.id AND r.extractor_model_id = $2 "
                "LEFT JOIN requirement_coverage c ON c.requirement_id = r.id AND c.resume_id = $3 AND c.model_id = $4 "
                "LEFT JOIN resume_fragment f ON f.id = c.best_fragment_id "
                "WHERE i.user_id = $1 ORDER BY i.rank, (r.source_field <> 'requirements'), r.span_start",
                user_id,
                self._active.ner_id,
                head["resume_id"],
                head["cross_encoder_id"],
            )
        results: dict[int, MatchResult] = {}
        verdicts: dict[int, list[RequirementVerdict]] = {}
        for row in rows:
            rank = row["rank"]
            if rank not in results:
                results[rank] = MatchResult(
                    row["source_id"], row["match_percent"], (), row["coverage_score"], row["retrieval_score"]
                )
                verdicts[rank] = []
            if row["text"] is None:
                continue
            requirement = VacancyRequirement(
                RequirementType(row["requirement_type"]),
                row["text"],
                row["source_field"],
                row["span_start"],
                row["span_end"],
                row["is_preferred"],
            )
            status = status_from_db(row["status"] or "not_covered")
            verdicts[rank].append(
                RequirementVerdict(
                    len(verdicts[rank]) + 1,
                    row["text"],
                    status,
                    row["quote"],
                    requirement,
                    row["score"] or 0.0,
                    row["ord"],
                )
            )
        ordered = tuple(
            MatchResult(r.vacancy_id, r.match_percent, tuple(verdicts[rank]), r.coverage_score, r.retrieval_score)
            for rank, r in sorted(results.items())
        )
        filters = MatchFilters(**head["filters"])
        return MatchRun(
            str(head["run_id"]),
            user_id,
            str(head["resume_id"]),
            head["computed_at"],
            filters,
            ordered,
            head["candidates_k"],
        )

    async def delete_for_user(self, user_id: str) -> None:
        """Удаляет выдачу пользователя."""
        await self._db.pool.execute("DELETE FROM recommendation_set WHERE user_id = $1", user_id)


class PgMetricsRepository:
    """Обезличенные события в ``matching_event`` и ``favorite_from_run_event``."""

    def __init__(self, db: Database) -> None:
        """Создаёт репозиторий."""
        self._db = db

    async def record_matching(self, event: MatchingEvent) -> None:
        """Записывает событие подбора."""
        await self._db.pool.execute(
            "INSERT INTO matching_event (run_id, at, duration_ms, results_count) VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (run_id) DO NOTHING",
            event.run_id,
            event.at,
            event.duration_ms,
            event.results_count,
        )

    async def record_favorite_from_run(self, event: FavoriteFromRunEvent) -> None:
        """Записывает событие «в избранное из подбора» (не более одного на подбор)."""
        await self._db.pool.execute(
            "INSERT INTO favorite_from_run_event (run_id, at) VALUES ($1, $2) ON CONFLICT (run_id) DO NOTHING",
            event.run_id,
            event.at,
        )

    async def count_favorites_from_run(self) -> int:
        """Число подборов, из которых что-то добавлено в избранное."""
        count: int = await self._db.pool.fetchval("SELECT count(*) FROM favorite_from_run_event")
        return count

    def _sync[T](self, coro: Awaitable[T]) -> T:
        loop = self._db.loop
        if loop is None:
            raise RuntimeError("Пул соединений не открыт")
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            raise RuntimeError("Синхронное чтение нельзя вызывать из цикла событий приложения")
        return asyncio.run_coroutine_threadsafe(_await(coro), loop).result(timeout=30)

    @property
    def matching(self) -> list[MatchingEvent]:
        """События подбора по возрасту; синхронное чтение для тестов и отладки (вне цикла событий приложения)."""
        rows = self._sync(
            self._db.pool.fetch("SELECT run_id, at, duration_ms, results_count FROM matching_event ORDER BY at")
        )
        return [MatchingEvent(str(r["run_id"]), r["at"], r["duration_ms"], r["results_count"]) for r in rows]

    @property
    def favorites_from_run(self) -> dict[str, FavoriteFromRunEvent]:
        """События «в избранное из подбора» по ``run_id``; синхронное чтение для тестов и отладки."""
        rows = self._sync(self._db.pool.fetch("SELECT run_id, at FROM favorite_from_run_event ORDER BY at"))
        return {str(r["run_id"]): FavoriteFromRunEvent(str(r["run_id"]), r["at"]) for r in rows}


async def _await[T](awaitable: Awaitable[T]) -> T:
    return await awaitable
