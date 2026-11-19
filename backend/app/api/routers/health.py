"""Проверка работоспособности."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

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


@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    """Public readiness and progress, without credentials or personal data."""
    state = dict(request.app.state.bootstrap)
    container = getattr(request.app.state, "container", None)
    if container:
        row = await container.database.pool.fetchrow("SELECT phase,progress,total,updated_at FROM pipeline_state")
        if row:
            state.update(dict(row))
    return state
