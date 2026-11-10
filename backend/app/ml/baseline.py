"""Базовые детерминированные реализации ML-интерфейсов, пока нет обученных моделей."""

from __future__ import annotations

import math
import re
import zlib
from array import array
from collections.abc import Sequence

from app.domain.models import Embedding, NormalizedVacancy, RequirementType, VacancyRequirement
from app.ml.text import normalize, stems, truncate_words
from app.ml.vacancy_text import PREFERRED_MARKER

MAX_REQUIREMENTS = 20
MAX_REQUIREMENT_LEN = 200
MIN_PHRASE_LEN = 3
HASH_DIM = 312

_PIECE_SEPARATOR = re.compile(r";|(?<=[.!?])\s+(?=[A-ZА-ЯЁ0-9])")
_TRIM_CHARS = " ,.;:-"


def _has_letters(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


def _pieces(line: str, offset: int) -> list[tuple[int, int]]:
    """Режет строку по ``;`` и концам предложений, возвращая абсолютные смещения кусков."""
    result: list[tuple[int, int]] = []
    start = 0
    for match in _PIECE_SEPARATOR.finditer(line):
        result.append((offset + start, offset + match.start()))
        start = match.end()
    result.append((offset + start, offset + len(line)))
    return result


def _trim(field: str, start: int, end: int) -> tuple[int, int]:
    while start < end and field[start] in _TRIM_CHARS:
        start += 1
    while end > start and field[end - 1] in _TRIM_CHARS:
        end -= 1
    return start, end


class BaselineRequirementExtractor:
    """TODO(ML): заменить моделью выделения требований; сейчас правила разбиения текста."""

    version = "baseline-req-2"

    def extract(self, vacancy: NormalizedVacancy) -> list[VacancyRequirement]:
        """Выделяет требования из ``vacancy.requirements`` (не больше 20); навыки и обязанности не используются."""
        field = vacancy.requirements
        result: list[VacancyRequirement] = []
        seen: set[str] = set()
        group_preferred = False
        position = 0
        for line in field.split("\n"):
            line_start, position = position, position + len(line) + 1
            start = line_start + 2 if line.startswith("- ") else line_start
            line_end = line_start + len(line)
            body = field[start:line_end]
            if body.rstrip().endswith(":"):
                group_preferred = PREFERRED_MARKER.search(body) is not None
                continue
            preferred = group_preferred or PREFERRED_MARKER.search(body) is not None
            for piece_start, piece_end in _pieces(body, start):
                for item_start, item_end in self._items(field, piece_start, piece_end):
                    text = field[item_start:item_end]
                    key = normalize(text)
                    if len(text) < MIN_PHRASE_LEN or not _has_letters(text) or key in seen:
                        continue
                    seen.add(key)
                    result.append(
                        VacancyRequirement(
                            RequirementType.HARD_SKILL, text, "requirements", item_start, item_end, preferred
                        )
                    )
                    if len(result) >= MAX_REQUIREMENTS:
                        return result
        return result

    @staticmethod
    def _items(field: str, start: int, end: int) -> list[tuple[int, int]]:
        piece = field[start:end]
        marker = PREFERRED_MARKER.search(piece)
        if marker is not None:
            left = (start, start + marker.start())
            right = (start + marker.end(), end)
            left_len = len(field[left[0] : left[1]].strip(_TRIM_CHARS))
            right_len = len(field[right[0] : right[1]].strip(_TRIM_CHARS))
            start, end = left if left_len >= right_len else right
        start, end = _trim(field, start, end)
        if end - start > MAX_REQUIREMENT_LEN:
            end = start + len(truncate_words(field[start:end], MAX_REQUIREMENT_LEN))
        return [(start, end)] if end > start else []


class HashingBiEncoder:
    """TODO(ML): базовый би-энкодер на хешировании основ слов; для тестов без torch, размерность как у rubert-tiny2."""

    version = "baseline-hash-1"
    dim = HASH_DIM

    def encode(self, texts: Sequence[str]) -> list[Embedding]:
        """Мешок основ слов в вектор фиксированной длины с знаком от хеша; результат нормирован."""
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> Embedding:
        values = [0.0] * self.dim
        for stem in stems(text):
            digest = zlib.crc32(stem.encode("utf-8"))
            values[digest % self.dim] += 1.0 if (digest >> 16) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in values))
        if norm > 0:
            values = [v / norm for v in values]
        return array("f", values)


class LexicalPairScorer:
    """TODO(ML): заменить кросс-энкодером; сейчас лексическое пересечение."""

    version = "baseline-pair-1"

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        """Оценка пар: вхождение требования во фразу → 1, иначе доля общих основ."""
        return [self._one(req, phrase) for req, phrase in pairs]

    @staticmethod
    def _one(requirement: str, phrase: str) -> float:
        norm_req = normalize(requirement)
        if norm_req and norm_req in normalize(phrase):
            return 1.0
        req = stems(requirement)
        if not req:
            return 0.0
        return len(req & stems(phrase)) / len(req)
