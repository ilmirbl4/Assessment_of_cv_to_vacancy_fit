"""Общие элементы роутеров."""

from __future__ import annotations

from typing import Any

from app.schemas.models import ApiErrorBody


def errors(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """Описание ответов с ошибками для OpenAPI."""
    names = {
        400: "Недействительный токен",
        401: "Требуется вход в систему",
        403: "Недостаточно прав",
        404: "Ресурс не найден",
        409: "Конфликт состояния",
        413: "Слишком большой запрос",
        415: "Неподдерживаемый формат",
        422: "Ошибка валидации",
        429: "Слишком много попыток",
    }
    return {s: {"model": ApiErrorBody, "description": names[s]} for s in statuses}
