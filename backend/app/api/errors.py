"""Обработчики исключений: все ошибки приходят в формате ``ApiErrorBody``."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.errors import AppError

log = logging.getLogger("app.errors")

MSG_SERVER = "Произошла ошибка на сервере. Повторите попытку позже."
MSG_INVALID = "Проверьте введённые данные"
MSG_BAD_VALUE = "Некорректное значение"

FIELD_MESSAGES: dict[str, str] = {
    "email": "Введите корректный адрес электронной почты",
    "password": "Пароль должен содержать не менее 8 символов, буквы и цифры",
    "new_password": "Пароль должен содержать не менее 8 символов, буквы и цифры",
    "consent_accepted": "Для регистрации необходимо дать согласие на обработку персональных данных",
    "consent_version": "Для регистрации необходимо дать согласие на обработку персональных данных",
    "min_salary": "Введите целое число от 0 до 10 000 000",
    "region_code": "Выберите значение из списка",
    "employment_type": "Выберите значение из списка",
    "schedule": "Выберите значение из списка",
    "experience": "Выберите значение из списка",
    "page": "Некорректный номер страницы",
    "file": "Файл не передан",
    "vacancy_id": "Некорректный идентификатор вакансии",
}
_FIELD_KEYS = {"consent_version": "consent_accepted"}

_HTTP_CODES = {404: ("NOT_FOUND", "Ресурс не найден"), 405: ("METHOD_NOT_ALLOWED", "Метод не поддерживается")}


def error_body(code: str, message: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
    """Тело ошибки; ключа ``fields`` нет, если ошибок по полям нет."""
    error: dict[str, Any] = {"code": code, "message": message}
    if fields:
        error["fields"] = fields
    return {"error": error}


def error_response(status: int, code: str, message: str, fields: dict[str, str] | None = None) -> JSONResponse:
    """JSON-ответ с ошибкой."""
    return JSONResponse(error_body(code, message, fields), status_code=status)


def _field_name(loc: tuple[Any, ...]) -> str | None:
    names = [part for part in loc if isinstance(part, str)]
    return names[-1] if names else None


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    return error_response(exc.status, exc.code, exc.message, exc.fields)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    code, message = _HTTP_CODES.get(
        exc.status_code, (f"HTTP_{exc.status_code}", MSG_SERVER if exc.status_code >= 500 else str(exc.detail))
    )
    return error_response(exc.status_code, code, message)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    fields: dict[str, str] = {}
    for item in exc.errors():
        if item.get("type") == "json_invalid":
            return error_response(422, "VALIDATION_ERROR", MSG_INVALID)
        name = _field_name(tuple(item.get("loc", ())))
        if name in (None, "body"):
            continue
        name = _FIELD_KEYS.get(name, name)
        fields.setdefault(name, FIELD_MESSAGES.get(name, MSG_BAD_VALUE))
    return error_response(422, "VALIDATION_ERROR", MSG_INVALID, fields)


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.error("Необработанное исключение: %s", type(exc).__name__, exc_info=exc)
    return error_response(500, "SERVER_ERROR", MSG_SERVER)


def register_handlers(app: FastAPI) -> None:
    """Подключает обработчики исключений."""
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)
