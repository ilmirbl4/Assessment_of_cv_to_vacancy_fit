"""Справочники: регионы, сферы, согласие, коды фильтров."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_DIR = Path(__file__).parent


def _load(name: str) -> Any:
    return json.loads((_DIR / name).read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class Option:
    """Элемент справочника."""

    code: str
    name: str


def normalize_label(value: str) -> str:
    """Приводит значение источника к виду для сопоставления: нижний регистр, ``ё`` → ``е``, пробелы схлопнуты."""
    return re.sub(r"\s+", " ", value.lower().replace("ё", "е")).strip()


EMPLOYMENT: tuple[Option, ...] = (
    Option("full", "Полная занятость"),
    Option("part", "Частичная занятость"),
    Option("temporary", "Временная работа"),
    Option("seasonal", "Сезонная работа"),
    Option("internship", "Стажировка"),
    Option("remote", "Удалённая работа"),
)
EMPLOYMENT_SOURCE = {
    "полная занятость": "full",
    "частичная занятость": "part",
    "временная работа": "temporary",
    "сезонная работа": "seasonal",
    "стажировка": "internship",
    "дистанционная (удаленная) работа": "remote",
}

SCHEDULES: tuple[Option, ...] = (
    Option("fullDay", "Полный рабочий день"),
    Option("shift", "Сменный график"),
    Option("rotation", "Вахтовый метод"),
    Option("partTime", "Неполный рабочий день"),
    Option("flexible", "Гибкий график"),
    Option("irregular", "Ненормированный рабочий день"),
)
SCHEDULE_SOURCE = {
    "полный рабочий день": "fullDay",
    "сменная работа": "shift",
    "вахтовый метод": "rotation",
    "неполный рабочий день/неполная рабочая неделя": "partTime",
    "режим гибкого рабочего времени": "flexible",
    "ненормированный рабочий день": "irregular",
}

EXPERIENCE: tuple[Option, ...] = (
    Option("noExperience", "Без опыта"),
    Option("between1And3", "От 1 года до 3 лет"),
    Option("between3And6", "От 3 до 6 лет"),
    Option("moreThan6", "Более 6 лет"),
)


def experience_code(years: int | None) -> str | None:
    """Код требуемого опыта по числу лет."""
    if years is None or years < 0:
        return None
    if years == 0:
        return "noExperience"
    if years <= 2:
        return "between1And3"
    if years <= 5:
        return "between3And6"
    return "moreThan6"


def parse_experience(value: object) -> int | None:
    """Число лет из значения источника: целое или строка вида ``"от 0"``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        return int(match.group()) if match else None
    return None


@lru_cache(maxsize=1)
def regions() -> tuple[Option, ...]:
    """Регионы, отсортированные по названию."""
    items = [Option(r["code"], r["name"]) for r in _load("regions.json")]
    return tuple(sorted(items, key=lambda o: normalize_label(o.name)))


@lru_cache(maxsize=1)
def region_names() -> dict[str, str]:
    """Название региона по коду."""
    return {o.code: o.name for o in regions()}


@lru_cache(maxsize=1)
def industries() -> tuple[Option, ...]:
    """Сферы деятельности источника."""
    return tuple(Option(i["code"], i["name"]) for i in _load("industries.json"))


@lru_cache(maxsize=1)
def consent() -> dict[str, str]:
    """Текущее согласие на обработку ПДн."""
    data: dict[str, str] = _load("consent.json")
    return data
