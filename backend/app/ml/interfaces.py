"""Интерфейсы ML-компонентов (раздел 7.1 инструкции)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.domain.models import Embedding, NormalizedVacancy, ResumeFragment, VacancyRequirement


class RequirementExtractor(Protocol):
    """Выделяет требования из нормализованной вакансии (на этапе сбора, ТЗ п. 4.1.1.3)."""

    version: str

    def extract(self, vacancy: NormalizedVacancy) -> list[VacancyRequirement]:
        """Возвращает требования вакансии со спанами в нормализованном поле."""
        ...


class ResumeSegmenter(Protocol):
    """Разбивает текст резюме на фрагменты для сопоставления с требованиями."""

    version: str

    def split(self, text: str) -> list[ResumeFragment]:
        """Возвращает фрагменты резюме со смещениями."""
        ...


class BiEncoder(Protocol):
    """Би-энкодер: тексты вакансий и резюме в общем векторном пространстве."""

    version: str
    dim: int

    def encode(self, texts: Sequence[str]) -> list[Embedding]:
        """L2-нормированные векторы в порядке ``texts``."""
        ...


class PairScorer(Protocol):
    """Кросс-энкодер: оценка пары «требование — фраза резюме»."""

    version: str

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        """Оценки пар от 0 до 1 в порядке ``pairs``."""
        ...
