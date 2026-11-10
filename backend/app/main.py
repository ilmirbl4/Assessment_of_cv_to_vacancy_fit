"""Точка входа: ``create_app`` собирает приложение FastAPI."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI

from app.api.errors import register_handlers
from app.api.middleware import RequestGuardMiddleware, configure_logging
from app.api.routers import auth, health, matching, resume
from app.collector.scheduler import Scheduler
from app.collector.service import ClientFactory
from app.config import Settings
from app.container import Container, build_container
from app.db.migrate import migrate
from app.domain.clock import Clock
from app.ml.factory import MlComponents, model_specs
from app.seed.seeder import seed_dataset, seed_demo, seed_synthetic
from app.services.email import EmailSender

log = logging.getLogger("app.main")

API_PREFIX = "/api/v1"


async def _startup(container: Container) -> asyncio.Task[None] | None:
    s = container.settings
    await container.auth.ensure_admin()
    await container.resumes.recover_stuck()
    await container.collection.recover()
    if s.seed_demo_data:
        await seed_demo(container)
    if s.seed_vacancies_dir:
        await seed_dataset(container, s.seed_vacancies_dir, s.seed_vacancies_limit)
    if s.seed_synthetic_vacancies:
        await seed_synthetic(container, s.seed_synthetic_vacancies)
    if not s.collector_enabled:
        return None
    has_complete = await container.repos.collection_runs.get_last_complete() is not None
    scheduler = Scheduler(
        container.collection,
        container.clock,
        s.collector_incremental_interval_min,
        s.collector_full_run_time,
        s.app_timezone,
        has_complete_run=has_complete,
    )
    return asyncio.create_task(scheduler.run_forever(), name="collector-scheduler")


def create_app(
    settings: Settings | None = None,
    *,
    clock: Clock | None = None,
    ml: MlComponents | None = None,
    sender: EmailSender | None = None,
    client_factory: ClientFactory | None = None,
) -> FastAPI:
    """Создаёт приложение; параметры позволяют тестам подменить часы, ML, почту и источник вакансий."""
    settings = settings or Settings()
    configure_logging(settings.log_level)
    container = build_container(settings, clock=clock, ml=ml, sender=sender, client_factory=client_factory)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        database = container.database
        scheduler_task: asyncio.Task[None] | None = None
        try:
            if database is not None:
                await database.connect()
                if settings.db_auto_migrate:
                    async with database.pool.acquire() as conn:
                        await migrate(conn)
            await container.repos.models.activate(model_specs(container.ml, settings))
            scheduler_task = await _startup(container)
            yield
        finally:
            container.collection.request_stop()
            if scheduler_task is not None:
                scheduler_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await scheduler_task
            await container.tasks.shutdown()
            if database is not None:
                await database.close()

    docs = settings.docs_enabled
    app = FastAPI(
        title="Система подбора вакансий",
        description="REST API подбора вакансий по резюме",
        version="0.1.0",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs" if docs else None,
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
        lifespan=lifespan,
    )
    app.state.container = container
    register_handlers(app)
    origin = urlsplit(settings.public_base_url)
    trusted = [*settings.trusted_origin_list, f"{origin.scheme}://{origin.netloc}"]
    app.add_middleware(RequestGuardMiddleware, trusted_origins=trusted)
    for module in (health, auth, resume, matching):
        app.include_router(module.router, prefix=API_PREFIX)
    return app


app = create_app()
