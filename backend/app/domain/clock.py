"""Источник времени: все сервисы получают текущий момент только отсюда."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """Интерфейс часов."""

    def now(self) -> datetime:
        """Возвращает текущий момент в UTC (aware datetime)."""
        ...


class SystemClock:
    """Реальные системные часы."""

    def now(self) -> datetime:
        """Возвращает текущее время UTC."""
        return datetime.now(UTC)


class ManualClock:
    """Управляемые часы для тестов."""

    def __init__(self, start: datetime | None = None) -> None:
        """Создаёт часы с заданным начальным моментом."""
        self._now = start or datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)

    def now(self) -> datetime:
        """Возвращает текущий момент часов."""
        return self._now

    def advance(self, **kwargs: float) -> None:
        """Сдвигает часы вперёд (аргументы как у ``timedelta``)."""
        self._now += timedelta(**kwargs)
