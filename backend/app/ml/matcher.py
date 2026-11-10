"""Сопоставление требований вакансий с фразами резюме (логика поверх ``PairScorer``)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.domain.models import (
    MatchResult,
    RequirementStatus,
    RequirementType,
    RequirementVerdict,
    VacancyRequirement,
)
from app.ml.interfaces import PairScorer
from app.ml.text import stems


def round_half_up(value: float) -> int:
    """Округление «половина вверх» (в отличие от банковского ``round``)."""
    return math.floor(value + 0.5)


PARTIAL_CREDIT = 0.5


def _credit(status: RequirementStatus) -> float:
    if status == RequirementStatus.COVERED:
        return 1.0
    return PARTIAL_CREDIT if status == RequirementStatus.PARTIALLY_COVERED else 0.0


def _sums(
    verdicts: Sequence[RequirementVerdict], type_weights: Mapping[RequirementType, float] | None
) -> tuple[float, float]:
    """Числитель ``Σ_все w·credit`` и знаменатель ``Σ_обязательные w`` (если обязательных нет, сумма всех)."""
    weights = type_weights or {}
    gained = mandatory = total = 0.0
    for verdict in verdicts:
        req = verdict.requirement
        weight = weights.get(req.type, 1.0) if req is not None else 1.0
        gained += weight * _credit(verdict.status)
        total += weight
        if req is None or not req.is_preferred:
            mandatory += weight
    return gained, (mandatory if mandatory > 0 else total)


def coverage_score(
    verdicts: Sequence[RequirementVerdict], type_weights: Mapping[RequirementType, float] | None = None
) -> float:
    """Покрытие ``min(1, Σ_все w·credit / Σ_обязательные w)``; без вердиктов 0."""
    gained, denominator = _sums(verdicts, type_weights)
    return 0.0 if denominator <= 0 else min(1.0, gained / denominator)


def match_percent(
    verdicts: Sequence[RequirementVerdict], type_weights: Mapping[RequirementType, float] | None = None
) -> int:
    """Степень соответствия ``round_half_up(100 × покрытие)``, 0..100."""
    gained, denominator = _sums(verdicts, type_weights)
    if denominator <= 0:
        return 0
    return max(0, min(100, round_half_up(100 * min(gained, denominator) / denominator)))


@dataclass(frozen=True, slots=True)
class MatcherConfig:
    """Параметры сопоставления."""

    phrases_per_requirement: int = 5
    covered_threshold: float = 0.75
    partial_threshold: float = 0.45
    type_weights: Mapping[RequirementType, float] = field(default_factory=dict)


class RequirementMatcher:
    """Выносит вердикты по требованиям; все пары оцениваются одним пакетным вызовом."""

    def __init__(self, scorer: PairScorer, config: MatcherConfig) -> None:
        """Создаёт сопоставитель."""
        self._scorer = scorer
        self._config = config

    def match(
        self, vacancies: Sequence[tuple[str, Sequence[VacancyRequirement]]], phrases: Sequence[str]
    ) -> list[MatchResult]:
        """Сопоставляет вакансии (идентификатор и требования) с фразами резюме.

        Args:
            vacancies: пары «идентификатор вакансии — требования».
            phrases: тексты фрагментов резюме; позиция фразы равна ``ord`` фрагмента.

        Returns:
            Результаты в порядке ``vacancies``.
        """
        phrase_stems = [stems(p) for p in phrases]
        pairs: list[tuple[str, str]] = []
        index: list[list[tuple[int, int]]] = []  # на каждое требование: (позиция фразы, позиция пары)
        for _, requirements in vacancies:
            for requirement in requirements:
                req_stems = stems(requirement.text)
                overlaps = [(-len(req_stems & ps), i) for i, ps in enumerate(phrase_stems)]
                ranked = [i for _, i in sorted(overlaps)[: self._config.phrases_per_requirement]]
                item: list[tuple[int, int]] = []
                for phrase_pos in ranked:
                    item.append((phrase_pos, len(pairs)))
                    pairs.append((requirement.text, phrases[phrase_pos]))
                index.append(item)
        scores = self._scorer.score(pairs) if pairs else []

        results: list[MatchResult] = []
        cursor = 0
        for vacancy_id, requirements in vacancies:
            verdicts: list[RequirementVerdict] = []
            for number, requirement in enumerate(requirements, start=1):
                best_phrase: int | None = None
                best_score = -1.0
                for phrase_pos, pair_pos in index[cursor]:
                    if scores[pair_pos] > best_score:
                        best_score, best_phrase = scores[pair_pos], phrase_pos
                cursor += 1
                status = self._status(best_score)
                quote = (
                    phrases[best_phrase]
                    if best_phrase is not None and status != RequirementStatus.NOT_COVERED
                    else None
                )
                score = min(1.0, max(0.0, best_score))
                verdicts.append(
                    RequirementVerdict(
                        number,
                        requirement.text,
                        status,
                        quote,
                        requirement,
                        score,
                        best_phrase if status != RequirementStatus.NOT_COVERED else None,
                    )
                )
            weights = self._config.type_weights
            results.append(
                MatchResult(
                    vacancy_id,
                    match_percent(verdicts, weights),
                    tuple(verdicts),
                    coverage_score(verdicts, weights),
                )
            )
        return results

    def _status(self, score: float) -> RequirementStatus:
        if score >= self._config.covered_threshold:
            return RequirementStatus.COVERED
        if score >= self._config.partial_threshold:
            return RequirementStatus.PARTIALLY_COVERED
        return RequirementStatus.NOT_COVERED
