"""Обход выдачи API в обход окна в 10 000 записей (раздел 8.2 инструкции).

Выдача делится по сферам деятельности, внутри сферы идёт обход окнами по ``date_modify``
(keyset-пагинация: API сортирует по этому полю по убыванию). Если в одну секунду изменено
больше 10 000 вакансий сферы, интервал обходится по регионам.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.collector.client import (
    MAX_WORKERS,
    PAGE_LIMIT,
    RESULT_WINDOW,
    ApiClient,
    PageFailedError,
    format_param_time,
    parse_date_modify,
    plus_seconds,
)

log = logging.getLogger("app.collector.crawler")

PAGES_PER_WINDOW = RESULT_WINDOW // PAGE_LIMIT
BatchCallback = Callable[[list[dict[str, Any]]], None]


@dataclass(slots=True)
class CrawlResult:
    """Итог обхода."""

    pages: int = 0
    api_total: int = 0
    failed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    complete: bool = False
    stopped: bool = False


@dataclass(slots=True)
class _Window:
    total: int = 0
    pages: int = 0
    min_modified: datetime | None = None
    failed: bool = False


class Crawler:
    """Обходит сферы параллельно и отдаёт пакеты сырых вакансий через колбэк."""

    def __init__(
        self,
        client: ApiClient,
        industries: list[str],
        regions: list[str],
        on_batch: BatchCallback,
        workers: int = MAX_WORKERS,
        stop: threading.Event | None = None,
    ) -> None:
        """Создаёт обходчик.

        Raises:
            ValueError: ``workers`` вне диапазона 1..4.
        """
        if not 1 <= workers <= MAX_WORKERS:
            raise ValueError(f"workers должен быть от 1 до {MAX_WORKERS}")
        self._client = client
        self._industries = industries
        self._regions = regions
        self._on_batch = on_batch
        self._workers = workers
        self._stop = stop or threading.Event()
        self._lock = threading.Lock()
        self._result = CrawlResult()
        self._done: set[str] = set()

    def run(self, snapshot: datetime, modified_from: datetime | None = None) -> CrawlResult:
        """Выполняет обход среза.

        Args:
            snapshot: верхняя граница ``modifiedTo``.
            modified_from: нижняя граница ``modifiedFrom`` (инкрементальный режим).
        """
        base: dict[str, Any] = {}
        if modified_from is not None:
            base["modifiedFrom"] = format_param_time(modified_from)
        self._result.api_total = self._client.count({**base, "modifiedTo": format_param_time(snapshot)})
        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            futures = [pool.submit(self._crawl_industry, code, snapshot, base) for code in self._industries]
            for future in futures:
                try:
                    future.result()
                except Exception as exc:
                    log.exception("Обход сферы прерван")
                    self._fail(f"сфера прервана: {exc}")
        self._result.stopped = self._stop.is_set()
        self._result.complete = not self._result.failed and len(self._done) == len(self._industries)
        return self._result

    def _fail(self, message: str) -> None:
        with self._lock:
            self._result.failed.append(message)

    def _warn(self, message: str) -> None:
        log.warning(message)
        with self._lock:
            self._result.warnings.append(message)

    def _crawl_industry(self, code: str, snapshot: datetime, base: dict[str, Any]) -> None:
        hi = snapshot
        window = 0
        while not self._stop.is_set():
            params = {**base, "industry": code, "modifiedTo": format_param_time(hi)}
            result = self._crawl_pages(code, window, "/vacancies", params)
            if result.failed and result.pages == 0:
                return
            if not result.failed and result.total <= RESULT_WINDOW:
                with self._lock:
                    self._done.add(code)
                return
            if result.min_modified is None:
                self._fail(f"{code}: в окне {window} нет вакансий с date_modify")
                return
            new_hi = plus_seconds(result.min_modified, 1)  # перекрытие на секунду, дубли уберёт upsert
            if new_hi >= hi:
                if result.failed:
                    return
                hi = self._crawl_by_regions(code, window, result.min_modified, hi, base)
            else:
                hi = new_hi
            window += 1

    def _crawl_by_regions(
        self, code: str, window: int, t_min: datetime, hi: datetime, base: dict[str, Any]
    ) -> datetime:
        """«Застревание»: больше 10 000 вакансий в одну секунду. Обход интервала по регионам."""
        self._warn(f"{code}: застревание на {format_param_time(t_min)}, обход по регионам")
        for region in self._regions:
            params = {"industry": code, "modifiedFrom": format_param_time(t_min), "modifiedTo": format_param_time(hi)}
            params.update({k: v for k, v in base.items() if k != "modifiedFrom"})
            result = self._crawl_pages(code, window, f"/vacancies/region/{region}", params)
            if result.total > RESULT_WINDOW:
                self._warn(f"{code}/{region}: {result.total} > 10000 в одну секунду, часть записей потеряна")
        return plus_seconds(t_min, -1)

    def _crawl_pages(self, code: str, window: int, path: str, params: dict[str, Any]) -> _Window:
        res = _Window()
        for offset in range(PAGES_PER_WINDOW):
            if self._stop.is_set():
                break
            try:
                resp = self._client.fetch(path, params, offset=offset)
            except PageFailedError as exc:
                self._fail(f"{code}: страница не загружена (окно {window}, offset {offset}): {exc}")
                res.failed = True
                break
            vacancies = resp.vacancies
            if offset == 0:
                res.total = resp.total
            res.pages += 1
            for vacancy in vacancies:
                try:
                    moment = parse_date_modify(vacancy["date_modify"])
                except (KeyError, ValueError):
                    continue
                if res.min_modified is None or moment < res.min_modified:
                    res.min_modified = moment
            if vacancies:
                self._on_batch(vacancies)
            if len(vacancies) < PAGE_LIMIT or resp.total <= (offset + 1) * PAGE_LIMIT:
                break
        with self._lock:
            self._result.pages += res.pages
        return res
