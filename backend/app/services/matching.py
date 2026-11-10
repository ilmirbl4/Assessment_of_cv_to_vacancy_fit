"""Подбор вакансий, страница вакансии и избранное (разделы 6.6–6.8 инструкции)."""

from __future__ import annotations

import asyncio
import logging
import math
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, replace

from app.config import MAX_PAGE, MAX_RESULTS, PAGE_SIZE, Settings
from app.domain.clock import Clock
from app.domain.models import (
    Favorite,
    FavoriteFromRunEvent,
    MatchFilters,
    MatchingEvent,
    MatchResult,
    MatchRun,
    RequirementVerdict,
    Resume,
    ResumeStatus,
    User,
    Vacancy,
)
from app.ml.factory import MlComponents
from app.ml.matcher import MatcherConfig, RequirementMatcher
from app.reference import EMPLOYMENT, EXPERIENCE, SCHEDULES, regions
from app.repositories.errors import AlreadyExistsError
from app.repositories.factory import Repositories
from app.services import errors
from app.services.resume import analyse_resume

log = logging.getLogger("app.matching")

_ID_RE_CHARS = frozenset("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-")
MAX_VACANCY_ID = 64


@dataclass(frozen=True, slots=True)
class MatchPageData:
    """Страница подбора."""

    run: MatchRun
    page: int
    total_pages: int
    items: list[tuple[Vacancy, int]]


@dataclass(frozen=True, slots=True)
class VacancyDetailData:
    """Данные страницы вакансии."""

    vacancy: Vacancy
    is_favorite: bool
    match_percent: int | None
    verdicts: tuple[RequirementVerdict, ...]


def validate_filters(filters: MatchFilters) -> None:
    """Проверяет коды справочников и зарплату.

    Raises:
        ValidationFailed: неизвестный код справочника или зарплата вне диапазона.
    """
    fields: dict[str, str] = {}
    pairs = (
        ("region_code", filters.region_code, {o.code for o in regions()}),
        ("employment_type", filters.employment_type, {o.code for o in EMPLOYMENT}),
        ("schedule", filters.schedule, {o.code for o in SCHEDULES}),
        ("experience", filters.experience, {o.code for o in EXPERIENCE}),
    )
    for name, value, allowed in pairs:
        if value is not None and value not in allowed:
            fields[name] = "Выберите значение из списка"
    if fields:
        raise errors.ValidationFailedError(fields=fields)


def is_valid_vacancy_id(value: str) -> bool:
    """Допустимый формат идентификатора вакансии."""
    return 0 < len(value) <= MAX_VACANCY_ID and all(ch in _ID_RE_CHARS for ch in value)


class MatchingService:
    """Подбор, страница вакансии, избранное."""

    def __init__(self, repos: Repositories, ml: MlComponents, clock: Clock, settings: Settings) -> None:
        """Создаёт сервис."""
        self._repos = repos
        self._ml = ml
        self._clock = clock
        self._settings = settings
        self._matcher = RequirementMatcher(
            ml.scorer,
            MatcherConfig(
                settings.match_phrases_per_requirement,
                settings.ml_covered_threshold,
                settings.ml_partial_threshold,
            ),
        )
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def _ready_resume(self, user: User) -> Resume:
        resume = await self._repos.resumes.get(user.id)
        if resume is None:
            raise errors.ResumeMissingForMatchError
        if resume.status == ResumeStatus.PROCESSING:
            raise errors.ResumeNotReadyError
        if resume.status == ResumeStatus.FAILED or resume.embedding is None:
            raise errors.ResumeFailedError
        return resume

    async def _refresh_resume(self, resume: Resume) -> Resume:
        """Пересчитывает фрагменты и вектор резюме, если версия обработки устарела (иначе другая размерность)."""
        if resume.model_version == self._ml.resume_model_version:
            return resume
        fragments, embedding = await asyncio.to_thread(analyse_resume, self._ml, resume.text)
        now = self._clock.now()
        await self._repos.resumes.complete_processing(
            resume.user_id,
            resume.id,
            status=ResumeStatus.READY.value,
            error_message=None,
            fragments=fragments,
            embedding=embedding,
            model_version=self._ml.resume_model_version,
            processed_at=now,
        )
        return replace(
            resume,
            fragments=fragments,
            embedding=embedding,
            model_version=self._ml.resume_model_version,
            processed_at=now,
        )

    # ---------- подбор ----------

    async def start(self, user: User, filters: MatchFilters) -> MatchPageData:
        """Выполняет подбор и возвращает первую страницу."""
        validate_filters(filters)
        async with self._locks[user.id]:
            resume = await self._refresh_resume(await self._ready_resume(user))
            started = time.perf_counter()
            top_n = self._settings.match_rerank_top_n
            if resume.embedding is None:
                raise errors.ResumeFailedError
            candidates = await self._repos.vacancies.search_candidates(resume.embedding, filters, top_n)
            vacancies = await self._repos.vacancies.get_many([c.id for c in candidates])
            ordered = [vacancies[c.id] for c in candidates if c.id in vacancies]
            scores = {c.id: c.score for c in candidates}
            results = await asyncio.to_thread(self._rank, ordered, resume, scores)
            now = self._clock.now()
            run = MatchRun(str(uuid.uuid4()), user.id, resume.id, now, filters, results, top_n)
            await self._repos.match_runs.save_current(run)
            duration = int((time.perf_counter() - started) * 1000)
            await self._repos.metrics.record_matching(MatchingEvent(run.id, now, duration, len(results)))
        return await self._page(run, 1)

    def _rank(self, vacancies: list[Vacancy], resume: Resume, scores: dict[str, float]) -> tuple[MatchResult, ...]:
        dates = {v.id: v.published_at.toordinal() for v in vacancies}
        results = self._matcher.match([(v.id, v.requirements) for v in vacancies], resume.phrases)
        results.sort(key=lambda r: (-r.match_percent, -dates[r.vacancy_id], r.vacancy_id))
        return tuple(replace(r, retrieval_score=scores.get(r.vacancy_id, 0.0)) for r in results[:MAX_RESULTS])

    async def current(self, user: User, page: int) -> MatchPageData:
        """Страница текущего подбора.

        Raises:
            NoMatchRun: подбор ещё не запускался.
        """
        run = await self._repos.match_runs.get_current(user.id)
        if run is None:
            raise errors.NoMatchRunError
        return await self._page(run, page)

    async def _page(self, run: MatchRun, page: int) -> MatchPageData:
        total = len(run.results)
        total_pages = math.ceil(total / PAGE_SIZE)
        safe = min(max(page, 1), max(total_pages, 1))
        chunk = run.results[(safe - 1) * PAGE_SIZE : safe * PAGE_SIZE]
        vacancies = await self._repos.vacancies.get_many([r.vacancy_id for r in chunk])
        items = [(vacancies[r.vacancy_id], r.match_percent) for r in chunk if r.vacancy_id in vacancies]
        return MatchPageData(run, safe, total_pages, items)

    # ---------- вакансия ----------

    async def detail(self, user: User, vacancy_id: str) -> VacancyDetailData:
        """Страница вакансии с вердиктами по требованиям.

        Raises:
            VacancyNotFound: вакансии нет.
        """
        if not is_valid_vacancy_id(vacancy_id):
            raise errors.VacancyNotFoundError
        vacancy = await self._repos.vacancies.get(vacancy_id)
        if vacancy is None:
            raise errors.VacancyNotFoundError
        favorite = await self._repos.favorites.exists(user.id, vacancy_id)
        resume = await self._repos.resumes.get(user.id)
        if resume is None or resume.status != ResumeStatus.READY:
            return VacancyDetailData(vacancy, favorite, None, ())
        run = await self._repos.match_runs.get_current(user.id)
        if run is not None and run.resume_id == resume.id:
            stored = next((r for r in run.results if r.vacancy_id == vacancy_id), None)
            if stored is not None:
                return VacancyDetailData(vacancy, favorite, stored.match_percent, stored.verdicts)
        result = (await asyncio.to_thread(self._matcher.match, [(vacancy.id, vacancy.requirements)], resume.phrases))[0]
        return VacancyDetailData(vacancy, favorite, result.match_percent, result.verdicts)

    # ---------- избранное ----------

    async def favorites(self, user: User) -> list[tuple[Favorite, Vacancy]]:
        """Избранное пользователя по убыванию даты добавления."""
        items = await self._repos.favorites.list_for_user(user.id)
        vacancies = await self._repos.vacancies.get_many([f.vacancy_id for f in items])
        result: list[tuple[Favorite, Vacancy]] = []
        for fav in items:
            vacancy = vacancies.get(fav.vacancy_id)
            if vacancy is None:
                log.warning("Вакансия из избранного не найдена: %s", fav.vacancy_id)
                continue
            result.append((fav, vacancy))
        return result

    async def add_favorite(self, user: User, vacancy_id: str) -> None:
        """Добавляет вакансию в избранное.

        Raises:
            VacancyNotFound: вакансии нет.
            AlreadyInFavorites: уже в избранном.
        """
        if not is_valid_vacancy_id(vacancy_id) or await self._repos.vacancies.get(vacancy_id) is None:
            raise errors.VacancyNotFoundError
        now = self._clock.now()
        try:
            await self._repos.favorites.add(Favorite(user.id, vacancy_id, now))
        except AlreadyExistsError as exc:
            raise errors.AlreadyInFavoritesError from exc
        run = await self._repos.match_runs.get_current(user.id)
        if run is not None and any(r.vacancy_id == vacancy_id for r in run.results):
            await self._repos.metrics.record_favorite_from_run(FavoriteFromRunEvent(run.id, now))

    async def remove_favorite(self, user: User, vacancy_id: str) -> None:
        """Удаляет вакансию из избранного (без ошибки, если её там не было)."""
        await self._repos.favorites.remove(user.id, vacancy_id)


__all__ = ["MAX_PAGE", "MatchPageData", "MatchingService", "VacancyDetailData", "is_valid_vacancy_id"]
