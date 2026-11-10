"""Регистр фоновых задач: хранит ссылки, ждёт завершения в тестах, отменяет при остановке."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

log = logging.getLogger("app.tasks")


class TaskRegistry:
    """Обёртка над ``asyncio.create_task`` с учётом задач и журналом исключений."""

    def __init__(self) -> None:
        """Создаёт пустой регистр."""
        self._tasks: set[asyncio.Task[Any]] = set()

    def spawn(self, coro: Coroutine[Any, Any, Any], name: str = "task") -> asyncio.Task[Any]:
        """Запускает корутину фоновой задачей; исключение пишется в лог и не роняет процесс."""

        async def guarded() -> Any:
            try:
                return await coro
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Фоновая задача %s завершилась с ошибкой", name)
                return None

        task = asyncio.create_task(guarded(), name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def join(self) -> None:
        """Ждёт завершения всех текущих задач (в том числе порождённых ими)."""
        while self._tasks:
            pending = [task for task in self._tasks if not task.done()]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            else:
                # gather() по завершённым задачам не отдаёт управление циклу, а ``discard`` ещё не выполнился
                await asyncio.sleep(0)

    async def shutdown(self) -> None:
        """Отменяет все задачи и ждёт их завершения."""
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
