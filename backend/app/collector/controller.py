"""One database lock and durable schedule for manual and timer-driven collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from itertools import islice
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.collector.json_source import inspect, records
from app.collector.scheduler import next_full_run
from app.domain.models import CollectionRun, RunMode, RunStatus
from app.services.errors import CollectionAlreadyRunningError

log = logging.getLogger(__name__)
COLLECTION_LOCK = 7204117010


class Controller:
    """Serializes manual and scheduled collection through one database lock."""

    def __init__(self, container: Any) -> None:
        """Stores the shared container and an idle task slot."""
        self.c = container
        self.current: asyncio.Task[bool] | None = None
        self.stop = False

    async def start(self, initial: bool = False, full: bool = False) -> str:
        """Claim the interprocess lock before accepting an asynchronous request."""
        conn = await self.c.database.pool.acquire()
        try:
            if not await conn.fetchval("SELECT pg_try_advisory_lock($1)", COLLECTION_LOCK):
                raise CollectionAlreadyRunningError
            api_run = None
            if self.c.settings.collector_source == "api":
                mode = RunMode.FULL if initial or full else RunMode.INCREMENTAL
                api_run = await self.c.collection.start_run(mode)
            run_id = api_run.id if api_run else str(uuid4())
            self.current = asyncio.create_task(self._execute(conn, run_id, initial, api_run))
            return run_id
        except BaseException:
            await self.c.database.pool.release(conn)
            raise

    async def _execute(self, lock_conn: Any, run_id: str, initial: bool, api_run: CollectionRun | None) -> bool:
        c = self.c
        s = c.settings
        success = False
        try:
            if api_run is None:
                paths = (
                    [Path(s.initial_vacancies_path)]
                    if initial
                    else sorted(
                        p
                        for p in Path(s.incremental_vacancies_dir).glob("*")
                        if p.name.endswith((".json", ".jsonl", ".jsonl.gz"))
                    )
                )
                for path in paths:
                    if self.stop:
                        break
                    await self._file(path, run_id)
                    run_id = str(uuid4())
                success = not self.stop
            else:
                finished = await c.collection.wait_run(api_run)
                success = finished.status == RunStatus.SUCCESS
            if initial and success:
                await c.database.pool.execute("UPDATE pipeline_state SET initial_complete=true")
            if success:
                await c.monitoring.refresh()
        except Exception as exc:
            log.exception("Сбор не завершён")
            await c.database.pool.execute("UPDATE pipeline_state SET error=$1,updated_at=now()", str(exc)[:500])
        finally:
            now = c.clock.now()
            delay = (
                timedelta(minutes=s.collector_incremental_interval_min)
                if success
                else timedelta(seconds=s.collector_retry_s)
            )
            try:
                if api_run and api_run.mode == RunMode.FULL:
                    next_full = (
                        next_full_run(now, s.collector_full_run_time, s.app_timezone) if success else now + delay
                    )
                    await c.database.pool.execute(
                        "UPDATE pipeline_state SET next_collection_at=$1,next_full_at=$2", now + delay, next_full
                    )
                else:
                    await c.database.pool.execute("UPDATE pipeline_state SET next_collection_at=$1", now + delay)
            finally:
                await c.database.pool.release(lock_conn)
        return success

    async def _file(self, path: Any, run_id: Any) -> Any:
        c = self.c
        db = c.database
        s = c.settings
        sha, count = await asyncio.to_thread(inspect, path, s.json_max_bytes)
        old = await db.pool.fetchrow("SELECT * FROM source_batch WHERE checksum=$1", sha)
        if old and old["complete"]:
            return
        if old:
            run_id = str(old["run_id"])
        now = c.clock.now()
        async with db.pool.acquire() as conn, conn.transaction():
            await conn.execute(
                """INSERT INTO ingestion_run(id,mode,snapshot_at,started_at) VALUES($1,'incremental',$2,$2)
                ON CONFLICT(id) DO UPDATE SET status='running',finished_at=NULL,error_message=NULL""",
                run_id,
                now,
            )
            await conn.execute(
                "INSERT INTO source_batch(checksum,file_name,run_id) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
                sha,
                path.name,
                run_id,
            )
        iterator = records(path, s.json_max_bytes)
        cursor = old["cursor"] if old else 0
        for _ in islice(iterator, cursor):
            pass
        try:
            while batch := list(islice(iterator, s.collector_batch_size)):
                if self.stop:
                    raise RuntimeError("Сбор остановлен; следующий запуск продолжит checkpoint")
                position = cursor + len(batch)
                closed = [r["_closed_id"] for r in batch if "_closed_id" in r]
                live = [r for r in batch if "_closed_id" not in r]
                if live:
                    result = await c.ingestor.ingest(live, run_id, (sha, position))
                    if result.errors:
                        raise ValueError(f"Отклонено записей: {result.errors}; исправьте пакет и повторите")
                if closed:
                    # Closing is idempotent; the cursor is committed with its counters.
                    async with db.pool.acquire() as conn, conn.transaction():
                        rows = await conn.fetch(
                            """UPDATE vacancy SET is_active=false,closed_at=$2
                            WHERE source_id=ANY($1::text[]) AND is_active RETURNING id""",
                            closed,
                            now,
                        )
                        await conn.execute(
                            "UPDATE ingestion_run SET deactivated=deactivated+$2 WHERE id=$1", run_id, len(rows)
                        )
                        await conn.execute("UPDATE source_batch SET cursor=$2 WHERE checksum=$1", sha, position)
                cursor = position
                await db.pool.execute("UPDATE pipeline_state SET progress=$1,total=$2,updated_at=now()", cursor, count)
            async with db.pool.acquire() as conn, conn.transaction():
                await conn.execute("UPDATE source_batch SET complete=true WHERE checksum=$1", sha)
                await conn.execute(
                    "UPDATE ingestion_run SET status='success',finished_at=$2 WHERE id=$1", run_id, c.clock.now()
                )
        except Exception as exc:
            await db.pool.execute(
                "UPDATE ingestion_run SET status='failed',finished_at=$2,failed=failed+1,error_message=$3 WHERE id=$1",
                run_id,
                c.clock.now(),
                str(exc)[:500],
            )
            raise

    async def run_forever(self) -> Any:
        """A restart never pushes overdue work into the future."""
        s = self.c.settings
        while not self.stop:
            state = await self.c.database.pool.fetchrow("SELECT * FROM pipeline_state")
            now = self.c.clock.now()
            full = s.collector_source == "api" and state["next_full_at"] <= now
            if state["next_collection_at"] <= now or full:
                try:
                    await self.start(full=full)
                    if self.current is not None:
                        await asyncio.shield(self.current)
                except CollectionAlreadyRunningError:
                    pass
            await asyncio.sleep(s.collector_tick_s)
