"""Запуск сбора вакансий (раздел 8.5 инструкции)."""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from typing import Any

from app.collector.client import ApiClient
from app.collector.crawler import Crawler
from app.collector.ingest import VacancyIngestor
from app.config import Settings
from app.domain.clock import Clock
from app.domain.models import CollectionRun, RunMode, RunStatus
from app.reference import industries, regions
from app.repositories.interfaces import CollectionRunRepository, VacancyRepository
from app.services.errors import CollectionAlreadyRunningError
from app.services.tasks import TaskRegistry

log = logging.getLogger("app.collector.service")

INCREMENTAL_OVERLAP = timedelta(minutes=10)
INTERRUPTED_MESSAGE = "Сбор прерван перезапуском системы"

ClientFactory = Callable[[], ApiClient]


class CollectionService:
    """Запускает сбор; одновременно идёт не больше одного запуска."""

    def __init__(
        self,
        runs: CollectionRunRepository,
        vacancies: VacancyRepository,
        ingestor: VacancyIngestor,
        client_factory: ClientFactory,
        clock: Clock,
        settings: Settings,
        tasks: TaskRegistry,
    ) -> None:
        """Создаёт сервис."""
        self._runs = runs
        self._vacancies = vacancies
        self._ingestor = ingestor
        self._client_factory = client_factory
        self._clock = clock
        self._settings = settings
        self._tasks = tasks
        self._guard = asyncio.Lock()
        self._stop = threading.Event()
        self._current: asyncio.Task[Any] | None = None

    async def recover(self) -> None:
        """При старте переводит запуски, оставшиеся в ``running``, в ``failed``."""
        await self._runs.fail_running(self._clock.now(), INTERRUPTED_MESSAGE)

    def request_stop(self) -> None:
        """Просит текущий обход остановиться между страницами."""
        self._stop.set()

    async def start_run(self, mode: RunMode) -> CollectionRun:
        """Создаёт запуск и выполняет сбор в фоне.

        Raises:
            CollectionAlreadyRunningError: сбор уже идёт.
        """
        async with self._guard:
            if await self._runs.get_running() is not None:
                raise CollectionAlreadyRunningError
            last = await self._runs.get_last_complete()
            effective = mode if last is not None else RunMode.FULL
            now = self._clock.now()
            modified_from = (
                last.snapshot_at - INCREMENTAL_OVERLAP if (last and effective == RunMode.INCREMENTAL) else None
            )
            run = CollectionRun(
                id=str(uuid.uuid4()),
                mode=effective,
                started_at=now,
                finished_at=None,
                status=RunStatus.RUNNING,
                snapshot_at=now,
                modified_from=modified_from,
            )
            await self._runs.create(run)
            self._stop.clear()
        self._current = self._tasks.spawn(self._execute(run), name="collection")
        return run

    async def run_blocking(self, mode: RunMode) -> CollectionRun:
        """Запускает сбор и дожидается результата (планировщик и тесты)."""
        run = await self.start_run(mode)
        if self._current is not None:
            await self._current
        finished = await self._runs.list_started_since(run.started_at)
        return next(r for r in finished if r.id == run.id)

    async def _execute(self, run: CollectionRun) -> None:
        loop = asyncio.get_running_loop()
        counters = {"new": 0, "updated": 0, "unchanged": 0, "errors": 0, "received": 0}
        seen: set[str] = set()
        lock = threading.Lock()

        def on_batch(batch: list[dict[str, Any]]) -> None:
            result = asyncio.run_coroutine_threadsafe(self._ingestor.ingest(batch, run.id), loop).result()
            with lock:
                counters["new"] += result.new
                counters["updated"] += result.updated
                counters["unchanged"] += result.unchanged
                counters["errors"] += result.errors
                counters["received"] += len(batch)
                seen.update(result.seen_ids)

        try:
            codes = [o.code for o in industries()]
            if self._settings.collector_industry_list:
                codes = [c for c in codes if c in self._settings.collector_industry_list]
            client = self._client_factory()
            crawler = Crawler(
                client,
                codes,
                [o.code for o in regions()],
                on_batch,
                workers=self._settings.collector_workers,
                stop=self._stop,
            )
            try:
                crawl = await asyncio.to_thread(crawler.run, run.snapshot_at, run.modified_from)
            finally:
                client.close()
            deactivated = 0
            notes = list(crawl.failed[:5])
            skipped = False
            if run.mode == RunMode.FULL:
                covered = len(seen) >= self._settings.collector_min_coverage * crawl.api_total
                if crawl.complete and covered:
                    deactivated = await self._vacancies.deactivate_missing(seen, self._clock.now())
                else:
                    skipped = True
                    notes.append("Деактивация пропущена: обход неполный или покрытие ниже порога")
            errors = counters["errors"] + len(crawl.failed)
            ok = crawl.complete and errors == 0 and not skipped
            final = replace(
                run,
                finished_at=self._clock.now(),
                status=RunStatus.SUCCESS if ok else RunStatus.PARTIAL,
                new_count=counters["new"],
                updated_count=counters["updated"],
                deactivated_count=deactivated,
                error_count=errors,
                complete=crawl.complete,
                error_message="; ".join(notes) or None,
                unchanged_count=counters["unchanged"],
                pages_fetched=crawl.pages,
                received=counters["received"],
            )
        except Exception as exc:
            log.exception("Сбор вакансий завершился ошибкой")
            final = replace(
                run,
                finished_at=self._clock.now(),
                status=RunStatus.FAILED,
                new_count=counters["new"],
                updated_count=counters["updated"],
                error_count=counters["errors"] + 1,
                complete=False,
                error_message=f"Сбор не выполнен: {type(exc).__name__}",
                unchanged_count=counters["unchanged"],
                received=counters["received"],
            )
        await self._runs.update(final)
