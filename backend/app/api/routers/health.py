"""Проверка работоспособности."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.models import HealthStatus

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Проверка работоспособности",
    description="Возвращает ``ok``, если сервис запущен.",
)
async def health() -> HealthStatus:
    """Состояние сервиса."""
    return HealthStatus(status="ok")
