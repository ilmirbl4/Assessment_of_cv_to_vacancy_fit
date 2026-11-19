"""Нормализация сырой вакансии trudvsem (раздел 8.3 инструкции)."""

from __future__ import annotations

import html
import logging
import re
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.models import Employer, NormalizedVacancy, SourceField
from app.ml.normalization import prepare_text
from app.ml.vacancy_text import content_hash
from app.reference import (
    EMPLOYMENT_SOURCE,
    SCHEDULE_SOURCE,
    experience_code,
    normalize_label,
    parse_experience,
    region_names,
)

log = logging.getLogger("app.collector.normalizer")

DEFAULT_EMPLOYER = "Работодатель не указан"
INN_MAX, OGRN_MAX, KPP_MAX = 12, 15, 9

# Значения requirement.education источника → education_level схемы; ключ приведён ``normalize_label``.
# В источнике есть вариант с латинской «T» в слове «Требования».
EDUCATION_SOURCE: dict[str, str | None] = {
    normalize_label(key): value
    for key, value in {
        "Tребования не предъявляются": "Не требуется",
        "Требования не предъявляются": "Не требуется",
        "Общее образование": "Среднее",
        "Среднее общее образование": "Среднее",
        "Среднее общее": "Среднее",
        "Среднее профессиональное образование": "Среднее профессиональное",
        "Неполное высшее образование": "Незаконченное высшее",
        "Высшее образование": "Высшее",
        "Высшее образование — бакалавриат": "Высшее",
        "Высшее образование — специалитет, магистратура": "Высшее",
        "Высшее образование — подготовка кадров высшей квалификации": "Высшее",
        "Не указано": None,
    }.items()
}
REQUIRED_FIELDS = ("id", "job-name", "vac_url", "creation-date", "date_modify")

_KNOWN_KEYS = frozenset(
    {
        "duty", "requirements", "skills", "qualification", "requirement", "employment", "schedule",
        "scheduleTypeComment", "conditions", "benefit", "benefitDetails", "term", "hireDate", "work_places",
        "typicalPosition", "category", "addresses", "addressOffice", "medicalDocuments", "medicalCertificate",
        "social_protected", "contact_person", "contact_list", "company", "source", "creation-date", "date_modify",
        "id", "region", "salary", "salary_min", "salary_max", "currency", "job-name", "vac_url", "code_profession",
        "workPlaceType", "shift", "trainingDays",
    }
)  # fmt: skip


class InvalidVacancyError(ValueError):
    """Запись источника не содержит обязательных полей или повреждена."""


def parse_source_datetime(value: str) -> datetime:
    """Разбирает ``date_modify`` вида ``2026-10-19T13:40:00+0300`` и возвращает UTC."""
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").astimezone(UTC)


def clean_text(value: object) -> str:
    """Очищает текст источника от HTML, схлопывает пробелы, сохраняет переводы строк."""
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [" ".join(line.split()) for line in text.replace("\r", "\n").split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _salary(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = int(value)
    return number if number > 0 else None


def _years(years: int) -> str:
    if years == 0:
        return "Без опыта"
    word = "года" if years % 10 == 1 and years % 100 != 11 else "лет"
    return f"от {years} {word}"


def _date_ru(value: str) -> str:
    try:
        return date.fromisoformat(value[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return value


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _skills(raw: Mapping[str, Any]) -> tuple[str, ...]:
    value = raw.get("skills")
    if not isinstance(value, list):
        return ()
    result: list[str] = []
    for item in value:
        text = clean_text(item.get("name") if isinstance(item, Mapping) else item)
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _addresses(raw: Mapping[str, Any]) -> str:
    items = _as_mapping(raw.get("addresses")).get("address")
    lines = []
    for item in items if isinstance(items, list) else []:
        location = clean_text(_as_mapping(item).get("location")).rstrip(";").strip()
        if location:
            lines.append(location)
    return "\n".join(lines)


def _contacts(raw: Mapping[str, Any]) -> str:
    items = raw.get("contact_list")
    lines = []
    for item in items if isinstance(items, list) else []:
        data = _as_mapping(item)
        kind, value = clean_text(data.get("contact_type")), clean_text(data.get("contact_value"))
        if value:
            lines.append(f"{kind}: {value}" if kind else value)
    return "\n".join(lines)


def build_source_fields(raw: Mapping[str, Any], timezone: str = "Europe/Moscow") -> tuple[SourceField, ...]:
    """Собирает поля страницы вакансии в порядке таблицы 8.3."""
    requirement = _as_mapping(raw.get("requirement"))
    company = _as_mapping(raw.get("company"))
    years = parse_experience(requirement.get("experience"))
    work_places = raw.get("work_places")
    places = str(int(work_places)) if isinstance(work_places, int | float) and work_places > 0 else ""
    modified = ""
    if raw.get("date_modify"):
        try:
            modified = (
                parse_source_datetime(str(raw["date_modify"])).astimezone(ZoneInfo(timezone)).strftime("%d.%m.%Y %H:%M")
            )
        except ValueError:
            modified = ""
    hire = clean_text(raw.get("hireDate"))
    rows: list[tuple[str, str]] = [
        ("Обязанности", clean_text(raw.get("duty"))),
        ("Требования", clean_text(raw.get("requirements"))),
        ("Навыки", ", ".join(_skills(raw))),
        ("Квалификация", clean_text(raw.get("qualification"))),
        ("Образование", clean_text(requirement.get("education"))),
        ("Требуемый опыт", _years(years) if years is not None else ""),
        ("Тип занятости", clean_text(raw.get("employment"))),
        ("График работы", clean_text(raw.get("schedule"))),
        ("Комментарий к графику", clean_text(raw.get("scheduleTypeComment"))),
        ("Условия", clean_text(raw.get("conditions"))),
        ("Социальные гарантии", clean_text(raw.get("benefit"))),
        ("Подробнее о гарантиях", clean_text(raw.get("benefitDetails"))),
        ("Премии", clean_text(_as_mapping(raw.get("term")).get("text"))),
        ("Дата выхода на работу", _date_ru(hire) if re.match(r"^\d{4}-\d{2}-\d{2}", hire) else hire),
        ("Количество рабочих мест", places),
        ("Типовая должность", clean_text(raw.get("typicalPosition"))),
        ("Профессиональная область", clean_text(_as_mapping(raw.get("category")).get("specialisation"))),
        ("Адрес", _addresses(raw)),
        ("Офис", clean_text(raw.get("addressOffice"))),
        ("Медицинские документы", clean_text(raw.get("medicalDocuments"))),
        ("Медицинская справка", clean_text(raw.get("medicalCertificate"))),
        ("Квотируемое место для социально защищённых категорий", clean_text(raw.get("social_protected"))),
        ("Контактное лицо", clean_text(raw.get("contact_person"))),
        ("Контакты", _contacts(raw)),
        ("ИНН работодателя", clean_text(company.get("inn"))),
        ("ОГРН работодателя", clean_text(company.get("ogrn"))),
        ("Источник", clean_text(raw.get("source"))),
        ("Дата создания", _date_ru(str(raw.get("creation-date") or ""))),
        ("Дата изменения", modified),
    ]  # fmt: skip
    return tuple(SourceField(label, value) for label, value in rows if value)


def normalize(
    raw: Mapping[str, Any],
    seen_values: set[str] | None = None,
    timezone: str = "Europe/Moscow",
) -> NormalizedVacancy:
    """Приводит сырую вакансию к доменному виду.

    Args:
        raw: запись источника.
        seen_values: множество уже залогированных неизвестных значений и ключей (на процесс).
        timezone: пояс для поля «Дата изменения».

    Raises:
        InvalidVacancyError: нет обязательных полей или они некорректны.
    """
    sink = seen_values if seen_values is not None else set()
    for key in REQUIRED_FIELDS:
        if not raw.get(key):
            raise InvalidVacancyError(f"нет обязательного поля {key}")
    try:
        published = date.fromisoformat(str(raw["creation-date"])[:10])
        modified = parse_source_datetime(str(raw["date_modify"]))
    except ValueError as exc:
        raise InvalidVacancyError("некорректная дата") from exc

    title = str(raw["job-name"]).strip()
    if not title:
        raise InvalidVacancyError("пустое название")
    salary_from, salary_to = _salary(raw.get("salary_min")), _salary(raw.get("salary_max"))
    if salary_from is not None and salary_to is not None and salary_from > salary_to:
        salary_from, salary_to = salary_to, salary_from

    company = _as_mapping(raw.get("company"))
    employer = " ".join(html.unescape(str(company.get("name") or "")).split()) or DEFAULT_EMPLOYER
    region = _as_mapping(raw.get("region"))
    region_code = str(region["region_code"]) if region.get("region_code") else None
    region_name = clean_text(region.get("name")) or region_names().get(region_code or "", "") or "Регион не указан"

    def mapped(field: str, table: Mapping[str, str]) -> str | None:
        value = raw.get(field)
        if not value:
            return None
        code = table.get(normalize_label(str(value)))
        if code is None:
            _log_once(sink, f"{field}={value}", f"Неизвестное значение поля {field}: {value!r}")
        return code

    requirement = _as_mapping(raw.get("requirement"))
    years = parse_experience(requirement.get("experience"))
    education = _education(requirement.get("education"), sink)
    _, bodies, _ = prepare_text(raw.get("requirements"), raw.get("duty"))
    requirements_text = bodies["requirements"]
    duties_text = bodies["duties"]
    for key in raw:
        if key not in _KNOWN_KEYS:
            _log_once(sink, f"key:{key}", f"Новый ключ источника: {key}")

    return NormalizedVacancy(
        id=str(raw["id"]),
        title=title,
        salary_from=salary_from,
        salary_to=salary_to,
        employer_name=employer,
        published_at=published,
        region_code=region_code,
        region_name=region_name,
        employment_code=mapped("employment", EMPLOYMENT_SOURCE),
        schedule_code=mapped("schedule", SCHEDULE_SOURCE),
        experience_code=experience_code(years),
        professional_area=clean_text(_as_mapping(raw.get("category")).get("specialisation")) or None,
        source_url=str(raw["vac_url"]),
        source_fields=build_source_fields(raw, timezone),
        requirements=requirements_text,
        duties=duties_text,
        skills=_skills(raw),
        date_modify=modified,
        raw=dict(raw),
        qualification=clean_text(raw.get("qualification")) or None,
        education=education,
        experience_years=years,
        employer=_employer(company, sink),
        content_hash=content_hash(title, requirements_text, duties_text),
    )


def _education(value: object, sink: set[str]) -> str | None:
    if not value:
        return None
    label = normalize_label(str(value))
    if label not in EDUCATION_SOURCE:
        _log_once(sink, f"education={value}", f"Неизвестное значение поля education: {value!r}")
        return None
    return EDUCATION_SOURCE[label]


def _bounded(company: Mapping[str, Any], key: str, limit: int, sink: set[str]) -> str | None:
    value = clean_text(company.get(key)) or None
    if value is not None and len(value) > limit:
        _log_once(sink, f"len:{key}={value}", f"Значение company.{key} длиннее {limit} символов: {value!r}")
        return None
    return value


def _employer(company: Mapping[str, Any], sink: set[str]) -> Employer | None:
    code = clean_text(company.get("companycode"))
    if not code:
        return None
    return Employer(
        source_code=code,
        inn=_bounded(company, "inn", INN_MAX, sink),
        ogrn=_bounded(company, "ogrn", OGRN_MAX, sink),
        kpp=_bounded(company, "kpp", KPP_MAX, sink),
        site_url=clean_text(company.get("url")) or None,
    )


def _log_once(sink: set[str], key: str, message: str, emit: Callable[..., None] = log.info) -> None:
    if key not in sink:
        sink.add(key)
        emit(message)
