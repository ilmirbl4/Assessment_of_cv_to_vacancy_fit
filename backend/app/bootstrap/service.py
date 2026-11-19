"""Asynchronous startup with durable progress and a recoverable corpus transition."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from app.bootstrap.rebuild import apply_staged, rebuild
from app.container import build_container
from app.db.migrate import migrate, require_migrated
from app.ml.factory import model_specs

log = logging.getLogger(__name__)
BOOTSTRAP_LOCK = 7204117011


async def bootstrap(app: Any, database: Any, settings: Any, **overrides: Any) -> Any:
    """Expose liveness before migrations/models; keep errors visible on /status."""
    try:
        for attempt in range(settings.db_connect_attempts):
            try:
                await database.connect()
                break
            except Exception:
                if attempt + 1 == settings.db_connect_attempts:
                    raise
                await asyncio.sleep(settings.db_connect_retry_s)
        async with database.pool.acquire() as conn:
            if settings.db_auto_migrate:
                await migrate(conn)
            else:
                await require_migrated(conn)
        app.state.bootstrap.update(phase="models", database_ready=True)
        # Loading includes model hash checks and stays outside the event loop.
        container = await asyncio.to_thread(build_container, settings, database, **overrides)
        app.state.container = container
        await container.auth.ensure_admin()
        async with database.pool.acquire() as lock:
            if not await lock.fetchval("SELECT pg_try_advisory_lock($1)", BOOTSTRAP_LOCK):
                raise RuntimeError("Другая копия backend уже подготавливает эту БД")
            try:
                await container.collection.recover()
                old = await container.repos.models.stage(model_specs(container.ml, settings))
                await database.pool.execute("UPDATE pipeline_state SET phase='checking',error=NULL,updated_at=now()")
                app.state.bootstrap["phase"] = "checking"
                job = await rebuild(container, old, container.pipeline_id)
                container.monitoring.reference_id = __import__("json").loads(
                    (__import__("pathlib").Path(settings.monitoring_reference_path) / "manifest.json").read_text()
                )["reference_id"]
                initialized = await database.pool.fetchval("SELECT initial_complete FROM pipeline_state")
                existing = await database.pool.fetchval("SELECT count(*) FROM vacancy")
                # A proven successful legacy import may be adopted, a half-written import may not.
                legacy = await database.pool.fetchval("SELECT EXISTS(SELECT FROM ingestion_run WHERE status='success')")
                if not initialized and existing and legacy:
                    await database.pool.execute("UPDATE pipeline_state SET initial_complete=true")
                    initialized = True
                if not initialized:
                    await database.pool.execute("UPDATE pipeline_state SET phase='initial'")
                    await container.controller.start(initial=True, full=settings.collector_source == "api")
                    if not container.controller.current:
                        raise RuntimeError("Первоначальный импорт не запущен")
                    # Staging is valid only after the whole initial corpus is committed.
                    if not await container.controller.current:
                        raise RuntimeError("Первоначальный импорт завершился ошибкой; см. журнал сбора")
                    initialized = await database.pool.fetchval("SELECT initial_complete FROM pipeline_state")
                    if not initialized:
                        raise RuntimeError("Первоначальный импорт не подтвердил готовность корпуса")
                await container.monitoring.prepare_reference()
                await apply_staged(container, job, container.pipeline_id)
                await container.resumes.recover_stuck()
                app.state.bootstrap.update(phase="ready", matching_ready=True, error=None)
                if settings.collector_enabled:
                    app.state.scheduler = asyncio.create_task(container.controller.run_forever())
                await container.monitoring.refresh()
            finally:
                await lock.execute("SELECT pg_advisory_unlock($1)", BOOTSTRAP_LOCK)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.exception("Bootstrap failed")
        # Errors intentionally contain no connection string or secrets.
        message = f"{type(exc).__name__}: {exc}"
        for secret in (settings.postgres_password, settings.smtp_password, settings.admin_password):
            if secret:
                message = message.replace(secret, "[redacted]")
        app.state.bootstrap.update(phase="failed", error=message, matching_ready=False)
        with contextlib.suppress(Exception):
            await database.pool.execute(
                "UPDATE pipeline_state SET phase='failed',error=$1,updated_at=now()", message[:1000]
            )
