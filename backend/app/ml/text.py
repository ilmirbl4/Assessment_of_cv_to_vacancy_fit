"""Нормализация текста и разбиение на элементы (общие правила для базовых реализаций)."""

from __future__ import annotations

import html
import re
from functools import lru_cache

_TAG_RE = re.compile(r"<[^>]+>")
_TOKEN_RE = re.compile(r"[0-9a-zа-я][0-9a-zа-я+#]*")
_SPLIT_RE = re.compile(r"[\r\n;•·]+|(?<=[.!?])\s+(?=[A-ZА-ЯЁ0-9])")
_MARKER_RE = re.compile(r"^\s*(?:[-*–—]+|\d+[.)])\s+")
_STEM_LEN = 6

STOP_WORDS = frozenset(
    {
        "и",
        "в",
        "на",
        "с",
        "по",
        "для",
        "или",
        "от",
        "до",
        "не",
        "опыт",
        "работы",
        "знание",
        "умение",
        "навыки",
        "наличие",
        "требования",
    }
)


def strip_html(text: str) -> str:
    """Удаляет HTML-теги и раскодирует сущности."""
    return html.unescape(_TAG_RE.sub(" ", html.unescape(text)))


@lru_cache(maxsize=50_000)
def normalize(text: str) -> str:
    """Нижний регистр, ``ё`` → ``е``, без HTML и лишних пробелов."""
    return " ".join(strip_html(text).lower().replace("ё", "е").split())


def tokens(text: str) -> list[str]:
    """Токены нормализованного текста."""
    return _TOKEN_RE.findall(normalize(text))


def stem(token: str) -> str:
    """Основа слова: первые 6 символов длинного токена."""
    return token[:_STEM_LEN] if len(token) > _STEM_LEN else token


@lru_cache(maxsize=50_000)
def stems(text: str) -> frozenset[str]:
    """Множество основ значимых слов текста."""
    return frozenset(stem(t) for t in tokens(text) if t not in STOP_WORDS)


def split_items(text: str) -> list[str]:
    """Режет текст на элементы по переводам строк, маркерам и концам предложений; чистит маркеры и HTML."""
    prepared = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>", "\n", text)
    prepared = html.unescape(_TAG_RE.sub(" ", html.unescape(prepared)))
    items: list[str] = []
    for chunk in _SPLIT_RE.split(prepared):
        cleaned = _MARKER_RE.sub("", chunk or "")
        cleaned = " ".join(cleaned.split()).strip(" ,.;:-")
        if cleaned:
            items.append(cleaned)
    return items


def truncate_words(text: str, limit: int) -> str:
    """Обрезает текст до ``limit`` символов по границе слова."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut and text[limit] != " ":
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:-")
