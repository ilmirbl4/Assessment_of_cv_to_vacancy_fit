"""HTTP-клиент открытого API портала «Работа России» (opendata.trudvsem.ru)."""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

USER_AGENT = "cv-vacancy-fit-coursework/1.0 (BMSTU IU6)"
PAGE_LIMIT = 100
RESULT_WINDOW = 10_000  # (offset + 1) * limit не должно превышать это число
MAX_WORKERS = 4
TIMEOUT = httpx.Timeout(60.0, connect=10.0)
MAX_ATTEMPTS = 5

log = logging.getLogger("app.collector.client")


class ApiError(Exception):
    """Базовая ошибка работы с API."""


class WindowExceededError(ApiError):
    """Запрошена страница за пределами окна выдачи в 10 000 записей."""


class NonJsonError(ApiError):
    """Ответ не является JSON. Повторять бессмысленно."""


class PageFailedError(ApiError):
    """Страница не получена после всех повторов."""


def parse_date_modify(value: str) -> datetime:
    """Переводит ``date_modify`` вида ``2026-10-19T13:40:00+0300`` в UTC."""
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").astimezone(UTC)


def format_param_time(moment: datetime) -> str:
    """Формат параметров ``modifiedFrom``/``modifiedTo``: ``2026-10-19T10:40:00Z``."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_param_time(value: str) -> datetime:
    """Обратное преобразование к :func:`format_param_time`."""
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def plus_seconds(moment: datetime, seconds: int) -> datetime:
    """Сдвиг момента времени на заданное число секунд."""
    return moment + timedelta(seconds=seconds)


def check_window(offset: int, limit: int) -> None:
    """Бросает :class:`WindowExceededError`, если страница вне окна выдачи."""
    if offset < 0 or limit < 1 or limit > PAGE_LIMIT:
        raise ValueError(f"Недопустимые limit={limit}, offset={offset}")
    if (offset + 1) * limit > RESULT_WINDOW:
        raise WindowExceededError(f"(offset+1)*limit = {(offset + 1) * limit} > {RESULT_WINDOW}")


@dataclass
class Response:
    """Успешный ответ API."""

    url: str
    body: dict[str, Any]
    total: int

    @property
    def vacancies(self) -> list[dict[str, Any]]:
        """Объекты ``vacancy`` страницы."""
        items = (self.body.get("results") or {}).get("vacancies") or []
        return [item["vacancy"] for item in items if "vacancy" in item]


@dataclass
class Stats:
    """Счётчики запросов (изменяются из нескольких потоков)."""

    requests: int = 0
    retries: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, requests_: int = 0, retries: int = 0) -> None:
        """Увеличивает счётчики."""
        with self.lock:
            self.requests += requests_
            self.retries += retries


class ApiClient:
    """Клиент API с повторами и экспоненциальной задержкой."""

    def __init__(
        self,
        base_url: str,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        """Создаёт клиент; ``transport`` подменяется в тестах (``httpx.MockTransport``)."""
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            transport=transport,
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        self._sleep = sleep
        self.max_attempts = max_attempts
        self.stats = Stats()

    def close(self) -> None:
        """Закрывает соединения."""
        self._http.close()

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> tuple[str, dict[str, Any], httpx.Headers]:
        """GET с повторами. Возвращает итоговый url, тело JSON и заголовки."""
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            self.stats.add(requests_=1)
            try:
                resp = self._http.get(url, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
            else:
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_error = ApiError(f"HTTP {resp.status_code}")
                    if resp.status_code == 500 and params and _beyond_window(params):
                        raise WindowExceededError(f"HTTP 500 при выходе за окно выдачи: {resp.url}")
                elif resp.status_code != 200:
                    raise NonJsonError(f"HTTP {resp.status_code}: {resp.url}")
                else:
                    try:
                        body = resp.json()
                    except ValueError as exc:
                        raise NonJsonError(f"Ответ не JSON: {resp.url}") from exc
                    return str(resp.url), body, resp.headers
            if attempt < self.max_attempts:
                self.stats.add(retries=1)
                self._sleep(2**attempt + random.SystemRandom().random())
        raise PageFailedError(f"{url} {params}: {last_error}")

    def fetch(
        self, path: str, params: dict[str, Any] | None = None, offset: int = 0, limit: int = PAGE_LIMIT
    ) -> Response:
        """Запрашивает страницу вакансий. ``path`` — например ``/vacancies``."""
        check_window(offset, limit)
        query = dict(params or {})
        query.update(limit=limit, offset=offset)
        url, body, headers = self.get_json(self.base_url + path, query)
        return Response(url=url, body=body, total=_total(body, headers))

    def count(self, params: dict[str, Any] | None = None, path: str = "/vacancies") -> int:
        """Число записей по фильтру (запрос с ``limit=1``)."""
        return self.fetch(path, params, offset=0, limit=1).total


def _beyond_window(params: dict[str, Any]) -> bool:
    try:
        return (int(params.get("offset", 0)) + 1) * int(params.get("limit", PAGE_LIMIT)) > RESULT_WINDOW
    except (TypeError, ValueError):
        return False


def _total(body: dict[str, Any], headers: httpx.Headers) -> int:
    meta_total = (body.get("meta") or {}).get("total")
    if meta_total is not None:
        return int(meta_total)
    header_total = headers.get("TotalResultCount")
    if header_total is None:
        raise ApiError("В ответе API отсутствует общее число вакансий")
    return int(header_total)
