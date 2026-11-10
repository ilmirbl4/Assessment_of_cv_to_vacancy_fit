"""Ограничитель попыток входа."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Protocol


class RateLimiter(Protocol):
    """Интерфейс ограничителя неудачных попыток."""

    def blocked(self, key: str, now: datetime) -> bool:
        """Исчерпан ли лимит по ключу."""
        ...

    def register_failure(self, key: str, now: datetime) -> None:
        """Записывает неудачную попытку."""
        ...

    def reset(self, key: str) -> None:
        """Сбрасывает счётчик ключа."""
        ...


class MemoryRateLimiter:
    """Лимитер в памяти процесса: поэтому приложение запускается с одним воркером (``--workers 1``)."""

    def __init__(self, max_failures: int, window: timedelta = timedelta(minutes=15)) -> None:
        """Создаёт ограничитель: не более ``max_failures`` неудач за ``window``."""
        self._max = max_failures
        self._window = window
        self._failures: dict[str, list[datetime]] = defaultdict(list)

    def _fresh(self, key: str, now: datetime) -> list[datetime]:
        fresh = [t for t in self._failures[key] if now - t < self._window]
        self._failures[key] = fresh
        return fresh

    def blocked(self, key: str, now: datetime) -> bool:
        """Исчерпан ли лимит по ключу."""
        return len(self._fresh(key, now)) >= self._max

    def register_failure(self, key: str, now: datetime) -> None:
        """Записывает неудачную попытку."""
        self._fresh(key, now).append(now)

    def reset(self, key: str) -> None:
        """Сбрасывает счётчик ключа."""
        self._failures.pop(key, None)
