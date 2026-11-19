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
from app.api.routers import admin, auth, health, matching, resume
from app.bootstrap.service import bootstrap
from app.collector.service import ClientFactory
from app.config import Settings
from app.db.database import Database
from app.domain.clock import Clock
from app.ml.factory import MlComponents
from app.services.email import EmailSender

log = logging.getLogger("app.main")

API_PREFIX = "/api/v1"


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
    if not settings.database_url:
        raise ValueError("Задайте DATABASE_URL в backend/.env")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(settings.database_url, settings.db_pool_min, settings.db_pool_max)
        app.state.bootstrap = dict(phase="database", database_ready=False, matching_ready=False, error=None)
        app.state.scheduler = None
        task = asyncio.create_task(
            bootstrap(app, database, settings, clock=clock, ml=ml, sender=sender, client_factory=client_factory)
        )
        try:
            yield
        finally:
            container = getattr(app.state, "container", None)
            if container:
                container.controller.stop = True
                container.collection.request_stop()
            if app.state.scheduler:
                app.state.scheduler.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await app.state.scheduler
            if container and container.controller.current and not container.controller.current.done():
                await container.controller.current
            if not task.done():
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            if container:
                await container.tasks.shutdown()
                container.ml._executor.shutdown(wait=True)
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
    register_handlers(app)
    origin = urlsplit(settings.public_base_url)
    trusted = [*settings.trusted_origin_list, f"{origin.scheme}://{origin.netloc}"]
    app.add_middleware(RequestGuardMiddleware, trusted_origins=trusted)
    for module in (health, auth, resume, matching, admin):
        app.include_router(module.router, prefix=API_PREFIX)
    return app


app = create_app()
