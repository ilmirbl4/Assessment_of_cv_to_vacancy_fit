"""Преобразования между доменом и PostgreSQL: очистка строк, векторы, статусы."""

from __future__ import annotations

import uuid
from array import array
from typing import Any

from app.domain.models import Embedding, RequirementStatus

NO_REGION = "Регион не указан"

_STATUS_TO_DB = {
    RequirementStatus.COVERED: "covered",
    RequirementStatus.PARTIALLY_COVERED: "partial",
    RequirementStatus.NOT_COVERED: "not_covered",
}
_STATUS_FROM_DB = {v: k for k, v in _STATUS_TO_DB.items()}


def status_to_db(status: RequirementStatus) -> str:
    """Статус покрытия домена в значение БД (``partially_covered`` → ``partial``)."""
    return _STATUS_TO_DB[status]


def status_from_db(value: str) -> RequirementStatus:
    """Значение БД в статус домена."""
    return _STATUS_FROM_DB[value]


def sanitize(value: Any) -> Any:
    """Рекурсивно удаляет символ NUL из строк, словарей и списков: PostgreSQL отвергает его в ``text`` и ``jsonb``."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {sanitize(k): sanitize(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [sanitize(v) for v in value]
    return value


def vector_to_text(vector: Embedding) -> str:
    """Вектор в текстовый литерал pgvector для ``$n::text::halfvec``."""
    return f"[{','.join(f'{x:.6g}' for x in vector)}]"


def vector_from_text(text: str) -> Embedding:
    """Текстовый литерал pgvector в вектор."""
    return array("f", (float(x) for x in text.strip("[]").split(",") if x))


def sql_template(template: str, **parts: object) -> str:
    """Подставляет в SQL доверенные константы ``{имя}`` (списки колонок, идентификаторы моделей, размерность).

    Значения из запроса пользователя сюда не передаются: они идут параметрами ``$n``.
    """
    for name, value in parts.items():
        template = template.replace("{" + name + "}", str(value))
    return template


_LEGACY_ID_NAMESPACE = uuid.UUID("5a1d3b0e-6d65-4c52-9a3f-0c7d1b6f2e11")
_ALIASES: dict[str, str] = {}


def as_uuid(value: str) -> str:
    """Идентификатор как uuid: настоящий uuid остаётся как есть, прочие строки получают стабильный uuid5.

    Сервисы всегда создают uuid4; нестандартные идентификаторы бывают только в тестах и ручных вызовах.
    Для них процесс запоминает исходную строку, чтобы :func:`from_uuid` вернул её при чтении.
    """
    try:
        return str(uuid.UUID(value))
    except ValueError:
        mapped = str(uuid.uuid5(_LEGACY_ID_NAMESPACE, value))
        _ALIASES[mapped] = value
        return mapped


def from_uuid(value: object) -> str:
    """Идентификатор из БД в домен: исходная строка для сохранённых псевдонимов, иначе текст uuid."""
    text = str(value)
    return _ALIASES.get(text, text)
