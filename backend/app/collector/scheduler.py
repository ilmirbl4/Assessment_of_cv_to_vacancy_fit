"""Планировщик сбора вакансий (раздел 8.6 инструкции)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.collector.service import CollectionService
from app.domain.clock import Clock
from app.domain.models import RunMode
from app.services.errors import CollectionAlreadyRunningError

log = logging.getLogger("app.collector.scheduler")

TICK_SECONDS = 30.0


def next_full_run(after: datetime, run_time: str, timezone: str) -> datetime:
    """Ближайший ежедневный момент полной сверки строго после ``after`` (UTC)."""
    tz = ZoneInfo(timezone)
    hour, minute = (int(part) for part in run_time.split(":"))
    local = after.astimezone(tz)
    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC)


class Scheduler:
    """Решает, пора ли запускать сбор, и запускает его."""

    def __init__(
        self,
        service: CollectionService,
        clock: Clock,
        interval_min: int,
        full_run_time: str,
        timezone: str,
        has_complete_run: bool = False,
    ) -> None:
        """Создаёт планировщик; ``has_complete_run=False`` означает, что первый запуск полный и немедленный."""
        self._service = service
        self._clock = clock
        self._interval = timedelta(minutes=interval_min)
        self._full_time = full_run_time
        self._timezone = timezone
        now = clock.now()
        self._next_incremental: datetime | None = None if not has_complete_run else now + self._interval
        self._next_full: datetime | None = None if not has_complete_run else next_full_run(now, full_run_time, timezone)
        self._first_pending = not has_complete_run

    def due(self, now: datetime) -> RunMode | None:
        """Какой запуск пора начинать сейчас (чистая функция от состояния и времени)."""
        if self._first_pending:
            return RunMode.FULL
        if self._next_full is not None and now >= self._next_full:
            return RunMode.FULL
        if self._next_incremental is not None and now >= self._next_incremental:
            return RunMode.INCREMENTAL
        return None

    def mark_started(self, mode: RunMode, now: datetime) -> None:
        """Сдвигает расписание после начала запуска."""
        self._first_pending = False
        self._next_incremental = now + self._interval
        if mode == RunMode.FULL or self._next_full is None:
            self._next_full = next_full_run(now, self._full_time, self._timezone)

    async def run_forever(self) -> None:
        """Цикл планировщика; останавливается отменой задачи."""
        while True:
            now = self._clock.now()
            mode = self.due(now)
            if mode is not None:
                self.mark_started(mode, now)
                try:
                    await self._service.run_blocking(mode)
                except CollectionAlreadyRunningError:
                    log.info("Сбор уже идёт, запуск по расписанию пропущен")
                except Exception:
                    log.exception("Ошибка запуска сбора по расписанию")
            await asyncio.sleep(TICK_SECONDS)
