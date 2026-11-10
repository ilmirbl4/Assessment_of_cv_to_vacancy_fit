"""Единственная функция нормализации текста вакансии (разметка NER, обучение и сервис используют её же)."""

from __future__ import annotations

import hashlib
import html
import re

_ZERO_WIDTH = re.compile("[​‌‍⁠﻿­]")
_BLOCK_TAG = re.compile(r"(?i)<br\s*/?>|</p>|</li>|</div>")
_TAG = re.compile(r"<[^>]+>")
# Граница пункта по инструкции разметки 1.1: дефис после «; » или «. ». Дефис внутри слова пункт не делит.
_ITEM_BOUNDARY = re.compile(r"(?:(?<=[;.])\s+[-–—•]\s*|(?<=[;.])[-–—•]\s+)")
_LEADING_MARK = re.compile(r"^\s*[-–—•]+\s*")

PREFERRED_MARKER = re.compile(r"желательно|будет\s+плюсом|приветствуется|преимуществом\s+будет", re.IGNORECASE)


def normalize_section(value: object) -> str:
    """Приводит поле requirements или duty к виду «- пункт» по строкам; пустое поле даёт ""."""
    if not value:
        return ""
    text = _ZERO_WIDTH.sub("", html.unescape(str(value)))
    text = _TAG.sub(" ", _BLOCK_TAG.sub("\n", text))
    text = html.unescape(text).replace("\xa0", " ")
    items: list[str] = []
    for line in re.split(r"[\r\n]+", text):
        for item in _ITEM_BOUNDARY.split(" ".join(line.split())):
            cleaned = _LEADING_MARK.sub("", item).rstrip(" ;.").strip()
            if cleaned:
                items.append(cleaned)
    return "\n".join(f"- {item}" for item in items)


def compose_sections(requirements: str, duties: str) -> str:
    """Склеивает секции в «Требования:», затем «Обязанности:» через пустую строку; пустая секция не выводится."""
    parts: list[str] = []
    if requirements:
        parts.append(f"Требования:\n{requirements}")
    if duties:
        parts.append(f"Обязанности:\n{duties}")
    return "\n\n".join(parts)


def vacancy_embedding_text(title: str, requirements: str, duties: str) -> str:
    """Текст для би-энкодера: название, пустая строка, секции."""
    return f"{title}\n\n{compose_sections(requirements, duties)}"


def content_hash(title: str, requirements: str, duties: str) -> bytes:
    """SHA-256 от названия и нормализованных секций."""
    return hashlib.sha256("\x1f".join((title, requirements, duties)).encode("utf-8")).digest()
