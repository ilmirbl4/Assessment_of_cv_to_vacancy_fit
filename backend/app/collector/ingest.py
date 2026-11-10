"""Загрузка пакета сырых вакансий: нормализация, выделение требований, запись (раздел 8.4)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from app.collector.normalizer import InvalidVacancyError, normalize
from app.domain.clock import Clock
from app.domain.models import NormalizedVacancy, Vacancy
from app.ml.factory import MlComponents
from app.ml.vacancy_text import vacancy_embedding_text
from app.repositories.interfaces import VacancyRepository

log = logging.getLogger("app.collector.ingest")


@dataclass(slots=True)
class IngestResult:
    """Итог загрузки пакета."""

    new: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: int = 0
    seen_ids: set[str] = field(default_factory=set)


def base_vacancy(norm: NormalizedVacancy, ml: MlComponents, now: datetime) -> Vacancy:
    """Доменная вакансия без требований и вектора (для неизменённых: анализ остаётся прежним)."""
    return Vacancy(
        id=norm.id,
        title=norm.title,
        salary_from=norm.salary_from,
        salary_to=norm.salary_to,
        employer_name=norm.employer_name,
        published_at=norm.published_at,
        region_code=norm.region_code,
        region_name=norm.region_name,
        employment_code=norm.employment_code,
        schedule_code=norm.schedule_code,
        experience_code=norm.experience_code,
        professional_area=norm.professional_area,
        source_url=norm.source_url,
        source_fields=norm.source_fields,
        requirements=(),
        embedding=None,
        model_version=ml.vacancy_model_version,
        date_modify=norm.date_modify,
        is_active=True,
        first_seen_at=now,
        updated_at=now,
        raw=norm.raw,
        requirements_section=norm.requirements,
        duties_section=norm.duties,
        qualification=norm.qualification,
        education=norm.education,
        experience_years=norm.experience_years,
        employer=norm.employer,
        content_hash=norm.content_hash,
    )


def analyse_vacancies(norms: Sequence[NormalizedVacancy], ml: MlComponents, now: datetime) -> list[Vacancy]:
    """Выделяет требования и считает векторы одним вызовом би-энкодера (синхронно: вызывать в потоке)."""
    if not norms:
        return []
    texts = [vacancy_embedding_text(n.title, n.requirements, n.duties) for n in norms]
    vectors = ml.bi_encoder.encode(texts)
    return [
        replace(base_vacancy(norm, ml, now), requirements=tuple(ml.extractor.extract(norm)), embedding=vector)
        for norm, vector in zip(norms, vectors, strict=True)
    ]


class VacancyIngestor:
    """Конвейер загрузки пакетов вакансий (общий для сбора и демо-данных)."""

    def __init__(self, repo: VacancyRepository, ml: MlComponents, clock: Clock, timezone: str) -> None:
        """Создаёт конвейер."""
        self._repo = repo
        self._ml = ml
        self._clock = clock
        self._timezone = timezone
        self._seen_values: set[str] = set()

    async def ingest(self, batch: Sequence[Mapping[str, Any]], run_id: str | None = None) -> IngestResult:
        """Нормализует и сохраняет пакет; неизменённые не пересчитываются, ошибочные считаются и пропускаются."""
        result = IngestResult()
        now = self._clock.now()
        unique: dict[str, NormalizedVacancy] = {}
        for raw in batch:
            try:
                norm = normalize(raw, self._seen_values, self._timezone)
            except InvalidVacancyError as exc:
                result.errors += 1
                log.warning("Запись %s пропущена: %s", raw.get("id"), exc)
                continue
            result.seen_ids.add(norm.id)
            known = unique.get(norm.id)
            if known is None or norm.date_modify > known.date_modify:
                unique[norm.id] = norm
        if not unique:
            return result
        states = await self._repo.get_ingest_states(list(unique), self._ml.vacancy_model_version)
        fresh = {
            vid
            for vid, norm in unique.items()
            if (state := states.get(vid)) is not None
            and state.analysis_fresh
            and state.content_hash == norm.content_hash
        }
        analysed = await asyncio.to_thread(
            analyse_vacancies, [n for vid, n in unique.items() if vid not in fresh], self._ml, now
        )
        kept = [base_vacancy(unique[vid], self._ml, now) for vid in fresh]
        stored = await self._repo.upsert_batch([*analysed, *kept], keep_analysis=fresh, ingestion_run_id=run_id)
        result.new, result.updated, result.unchanged = stored.new, stored.updated, stored.unchanged
        result.errors += len(stored.failed_ids)
        return result
