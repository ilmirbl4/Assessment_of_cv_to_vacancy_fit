"""Сопоставление требований вакансий с фразами резюме (логика поверх ``PairScorer``)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from app.domain.models import (
    MatchResult,
    RequirementStatus,
    RequirementType,
    RequirementVerdict,
    VacancyRequirement,
)
from app.ml.interfaces import BiEncoder, PairScorer


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

    def __init__(self, scorer: PairScorer, config: MatcherConfig, encoder: BiEncoder) -> None:
        """Создаёт сопоставитель."""
        self._scorer = scorer
        self._encoder = encoder
        self._config = config

    def match(
        self,
        vacancies: Sequence[tuple[str, Sequence[VacancyRequirement]]],
        phrases: Sequence[str],
        prepared_vectors: Mapping[str, Sequence[float]] | None = None,
    ) -> list[MatchResult]:
        """Сопоставляет вакансии (идентификатор и требования) с фразами резюме.

        Args:
            vacancies: пары «идентификатор вакансии — требования».
            phrases: тексты фрагментов резюме; позиция фразы равна ``ord`` фрагмента.
            prepared_vectors: заранее вычисленные векторы текстов, если есть.

        Returns:
            Результаты в порядке ``vacancies``.
        """
        unique_texts = list(dict.fromkeys([*phrases, *(r.text for _, reqs in vacancies for r in reqs)]))
        vectors = dict(prepared_vectors or {})
        missing_texts = [text for text in unique_texts if text not in vectors]
        if phrases and missing_texts:
            vectors.update(zip(missing_texts, self._encoder.encode(missing_texts), strict=True))
        phrase_vectors = np.asarray([vectors[p] for p in phrases], dtype=np.float32)
        pair_positions: dict[tuple[str, str], int] = {}
        pairs: list[tuple[str, str]] = []
        index: list[list[tuple[int, int]]] = []  # на каждое требование: (позиция фразы, позиция пары)
        for _, requirements in vacancies:
            for requirement in requirements:
                similarity = phrase_vectors @ np.asarray(vectors[requirement.text]) if phrases else []
                ranked = sorted(range(len(phrases)), key=lambda i: (-float(similarity[i]), i))[
                    : self._config.phrases_per_requirement
                ]
                item: list[tuple[int, int]] = []
                for phrase_pos in ranked:
                    pair = (requirement.text, phrases[phrase_pos])
                    if pair not in pair_positions:
                        pair_positions[pair] = len(pairs)
                        pairs.append(pair)
                    item.append((phrase_pos, pair_positions[pair]))
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
