"""Administrative collection, performance and drift endpoints with role enforcement."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import ContainerDep, require_admin
from app.schemas.admin import CollectionDashboard, DriftDashboard, SpeedDashboard

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


@router.get("/collection", response_model=CollectionDashboard)
async def collection(container: ContainerDep, days: Annotated[int, Query(ge=1, le=365)] = 30) -> Any:
    """Журнал сбора и состояние подготовки за период."""
    runs = await container.repos.collection_runs.list_started_since(container.clock.now() - timedelta(days=days))
    state = dict(await container.database.pool.fetchrow("SELECT * FROM pipeline_state"))
    current = container.controller.current if container.controller is not None else None
    return dict(
        active_vacancies_total=await container.repos.vacancies.count_active(),
        is_running=bool(current and not current.done()) or any(r.status.value == "running" for r in runs),
        runs=[asdict(r) for r in runs],
        bootstrap=state,
    )


@router.post("/collection/runs", status_code=202)
async def start_collection(container: ContainerDep, request: Request) -> dict[str, str]:
    """Ручной запуск сбора через общую блокировку."""
    if not request.app.state.bootstrap["matching_ready"]:
        raise HTTPException(409, "Подготовка системы ещё выполняется")
    return {"run_id": await container.controller.start()}


@router.get("/matching-speed", response_model=SpeedDashboard)
async def speed(container: ContainerDep, days: Annotated[int, Query(ge=1, le=365)] = 30) -> Any:
    """Агрегаты скорости подбора по суткам."""
    rows = await container.database.pool.fetch(
        """SELECT (at AT TIME ZONE $2)::date date,
        avg(duration_ms) avg_ms,percentile_cont(0.95) WITHIN GROUP(ORDER BY duration_ms) p95_ms,count(*) count
        FROM matching_event WHERE at>=$1 GROUP BY 1 ORDER BY 1""",
        container.clock.now() - timedelta(days=days),
        container.settings.app_timezone,
    )
    return {"days": [dict(r) for r in rows]}


@router.get("/drift", response_model=DriftDashboard)
async def drift(
    container: ContainerDep,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    batch: UUID | None = None,
) -> Any:
    """Дрейф данных за период или выбранный пакет."""
    try:
        return await container.monitoring.dashboard(from_date, to, batch)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/status")
async def status(container: ContainerDep) -> dict[str, Any]:
    """Административное состояние подготовки корпуса."""
    return dict(await container.database.pool.fetchrow("SELECT * FROM pipeline_state"))
