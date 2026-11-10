"""Нарезка резюме на фрагменты по правилам инструкции разметки (раздел 2.2)."""

from __future__ import annotations

import re

from razdel import sentenize

from app.domain.models import ResumeFragment
from app.ml.text import normalize

MAX_FRAGMENTS = 400
MIN_WORDS = 3
MAX_WORDS = 64

_LIST_MARKER = re.compile(r"^\s*(?:[-*•–—]+|\d+[.)])\s+")
_SOFT_BREAK = re.compile(r"[,;]")


def _words(text: str) -> int:
    return len(text.split())


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _sentences(text: str) -> list[tuple[int, int]]:
    """Предложения по строкам: маркер списка отбрасывается, смещения сохраняются."""
    spans: list[tuple[int, int]] = []
    position = 0
    for line in text.split("\n"):
        line_start, position = position, position + len(line) + 1
        marker = _LIST_MARKER.match(line)
        body_start = line_start + (marker.end() if marker else 0)
        body = text[body_start : line_start + len(line)]
        for sentence in sentenize(body):
            start, end = _trim(text, body_start + sentence.start, body_start + sentence.stop)
            if end > start:
                spans.append((start, end))
    return spans


def _glue_short(text: str, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Фрагмент короче трёх слов приклеивается к следующему, последний короткий — к предыдущему."""
    merged: list[tuple[int, int]] = []
    carry: int | None = None
    for start, end in spans:
        if carry is not None:
            start, carry = carry, None
        if _words(text[start:end]) < MIN_WORDS:
            carry = start
            tail = end
            continue
        merged.append((start, end))
    if carry is not None:
        if merged:
            merged[-1] = (merged[-1][0], tail)
        else:
            merged.append((carry, tail))
    return merged


def _split_long(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Фрагмент длиннее 64 слов режется по запятым и точкам с запятой на части не длиннее 64 слов."""
    if _words(text[start:end]) <= MAX_WORDS:
        return [(start, end)]
    pieces: list[tuple[int, int]] = []
    cursor = start
    for match in _SOFT_BREAK.finditer(text, start, end):
        pieces.append((cursor, match.end()))
        cursor = match.end()
    pieces.append((cursor, end))
    parts: list[tuple[int, int]] = []
    current: tuple[int, int] | None = None
    for piece in pieces:
        for sub in _hard_split(text, *piece):
            if current is not None and _words(text[current[0] : sub[1]]) <= MAX_WORDS:
                current = (current[0], sub[1])
            else:
                if current is not None:
                    parts.append(current)
                current = sub
    if current is not None:
        parts.append(current)
    return parts


def _hard_split(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Кусок без запятых, всё ещё длиннее 64 слов, режется по границе слов."""
    words = list(re.finditer(r"\S+", text[start:end]))
    if len(words) <= MAX_WORDS:
        return [(start, end)]
    result: list[tuple[int, int]] = []
    for i in range(0, len(words), MAX_WORDS):
        chunk = words[i : i + MAX_WORDS]
        result.append((start + chunk[0].start(), start + chunk[-1].end()))
    return result


class RuleResumeSegmenter:
    """Правила инструкции разметки 2.2: строки, предложения (razdel), склейка коротких, разбиение длинных."""

    version = "rules-seg-2"

    def split(self, text: str) -> list[ResumeFragment]:
        """Нарезает резюме на фрагменты (не больше 400) с непрерывной нумерацией ``ord``."""
        spans: list[tuple[int, int]] = []
        for start, end in _glue_short(text, _sentences(text)):
            spans.extend(_split_long(text, start, end))
        result: list[ResumeFragment] = []
        seen: set[str] = set()
        for start, end in spans:
            start, end = _trim(text, start, end)
            fragment = " ".join(text[start:end].split())
            key = normalize(fragment)
            if not any(ch.isalpha() for ch in fragment) or key in seen:
                continue
            seen.add(key)
            result.append(ResumeFragment(len(result), fragment, start, end))
            if len(result) >= MAX_FRAGMENTS:
                break
        return result
