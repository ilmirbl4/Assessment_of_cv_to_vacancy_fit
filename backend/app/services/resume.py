"""Загрузка и фоновая обработка резюме (раздел 6.5 инструкции)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict
from datetime import timedelta
from typing import Any

import numpy as np

from app.config import MAX_RESUME_BYTES, Settings
from app.documents.extract import (
    check_signature,
    clean_file_name,
    extract_docx,
    extract_pdf,
    file_type_by_name,
    normalize_text,
)
from app.domain.clock import Clock
from app.domain.models import Embedding, Resume, ResumeFragment, ResumeStatus, User
from app.ml.factory import MlComponents
from app.repositories.factory import Repositories
from app.repositories.postgres._mapping import vector_to_text
from app.services import errors
from app.services.tasks import TaskRegistry

log = logging.getLogger("app.resume")

EXTRACT_TIMEOUT_S = 10
MSG_PROCESSING_FAILED = "Не удалось обработать резюме. Загрузите другой файл."
MSG_NO_PHRASES = "В резюме не найдено описания опыта и навыков."
MSG_TIMEOUT = "Обработка резюме заняла слишком много времени. Загрузите файл ещё раз."


def analyse_resume(ml: MlComponents, text: str) -> tuple[tuple[ResumeFragment, ...], Embedding]:
    """Режет резюме на фрагменты и считает вектор всего текста (общий для загрузки и подбора)."""
    return tuple(ml.segmenter.split(text)), ml.bi_encoder.encode([text])[0]


class ResumeService:
    """Приём файла резюме, извлечение текста, фоновая подготовка к сопоставлению."""

    def __init__(
        self, repos: Repositories, ml: MlComponents, tasks: TaskRegistry, clock: Clock, settings: Settings
    ) -> None:
        """Создаёт сервис."""
        self._repos = repos
        self._ml = ml
        self._tasks = tasks
        self._clock = clock
        self._settings = settings

    async def get(self, user: User) -> Resume:
        """Текущее резюме.

        Raises:
            ResumeNotFound: резюме не загружено.
        """
        resume = await self._repos.resumes.get(user.id)
        if resume is None:
            raise errors.ResumeNotFoundError
        return resume

    async def upload(self, user: User, file_name: str, data: bytes) -> Resume:
        """Проверяет файл, сохраняет резюме в статусе ``processing`` и запускает обработку.

        Raises:
            UnsupportedFormat, FileTooLarge, FileUnreadable, PdfNoTextLayer, ResumeEmpty: см. раздел 6.5.
        """
        file_type = file_type_by_name(file_name)
        if len(data) > MAX_RESUME_BYTES:
            raise errors.FileTooLargeError
        check_signature(file_type, data)
        extractor = extract_pdf if file_type == "pdf" else extract_docx
        try:
            raw_text = await asyncio.wait_for(asyncio.to_thread(extractor, data), EXTRACT_TIMEOUT_S)
        except TimeoutError as exc:
            raise errors.FileUnreadableError from exc
        text = normalize_text(raw_text)
        if len(text) < self._settings.resume_min_text_chars:
            raise errors.PdfNoTextLayerError if file_type == "pdf" else errors.ResumeEmptyError
        resume = Resume(
            id=str(uuid.uuid4()),
            user_id=user.id,
            file_name=clean_file_name(file_name),
            file_type=file_type,
            uploaded_at=self._clock.now(),
            status=ResumeStatus.PROCESSING,
            error_message=None,
            text=text,
        )
        await self._repos.resumes.replace(resume)
        await self._repos.match_runs.delete_for_user(user.id)
        self._tasks.spawn(self.process(resume), name="resume-processing")
        return resume

    async def delete(self, user: User) -> None:
        """Удаляет резюме и текущий подбор."""
        await self._repos.resumes.delete(user.id)
        await self._repos.match_runs.delete_for_user(user.id)

    async def process(self, resume: Resume) -> None:
        """Разбивает резюме на фразы и считает признаки; результат записывается, если резюме всё ещё текущее."""
        status, message = ResumeStatus.READY, None
        fragments: tuple[ResumeFragment, ...] = ()
        embedding = None
        try:
            analysis = await asyncio.wait_for(
                self.stage_analysis(resume.id, resume.text), self._settings.resume_processing_timeout_s
            )
            if analysis is None:
                return
            from app.repositories.postgres._mapping import vector_from_text

            embedding = vector_from_text(str(analysis["embedding"]))
            fragments = tuple(
                ResumeFragment(f["ord"], f["text"], f["span_start"], f["span_end"]) for f in analysis["fragments"]
            )
            if not fragments:
                status, message, embedding = ResumeStatus.FAILED, MSG_NO_PHRASES, None
        except TimeoutError:
            status, message = ResumeStatus.FAILED, MSG_TIMEOUT
        except Exception:
            log.exception("Ошибка обработки резюме")
            status, message = ResumeStatus.FAILED, MSG_PROCESSING_FAILED
        stored = await self._repos.resumes.complete_processing(
            resume.user_id,
            resume.id,
            status=status.value,
            error_message=message,
            fragments=fragments if status == ResumeStatus.READY else (),
            embedding=embedding,
            model_version=self._ml.resume_model_version,
            processed_at=self._clock.now(),
        )

        if stored and status == ResumeStatus.READY and embedding is not None:
            projection = np.asarray(embedding, dtype=float)[:32]
            await self._repos.resumes._db.pool.execute(
                "INSERT INTO resume_observation(pipeline_id,features) VALUES($1,$2)",
                self._ml.resume_model_version,
                {"projection": projection.tolist()},
            )

    async def stage_analysis(self, resume_id: Any, text: Any) -> Any:
        """Persist versioned fragments and the embedding, cascading with the resume."""
        db = self._repos.resumes._db
        existing = await db.pool.fetchrow(
            "SELECT * FROM resume_analysis WHERE resume_id=$1 AND pipeline_id=$2",
            resume_id,
            self._ml.resume_model_version,
        )
        if existing:
            return existing

        def analyse() -> Any:
            fragments = tuple(self._ml.segmenter.split(text))
            vectors = self._ml.bi_encoder.encode([text, *[f.text for f in fragments]])
            return fragments, vectors

        fragments, vectors = await self._ml.run(analyse)
        async with db.pool.acquire() as conn, conn.transaction():
            # A concurrent replacement/deletion must not resurrect personal data.
            if not await conn.fetchval("SELECT id FROM resume WHERE id=$1 FOR UPDATE", resume_id):
                return None
            row = await conn.fetchrow(
                """INSERT INTO resume_analysis(resume_id,pipeline_id,model_id,dim,embedding,
                fragments,skills,normalized_text) VALUES($1,$2,$3,$4,$5::text::halfvec,$6,$7,$8)
                ON CONFLICT(resume_id,pipeline_id) DO UPDATE SET skills=excluded.skills RETURNING *""",
                resume_id,
                self._ml.resume_model_version,
                self._repos.resumes._active.bi_id,
                self._ml.bi_encoder.dim,
                vector_to_text(vectors[0]),
                [{**asdict(f), "embedding": list(v)} for f, v in zip(fragments, vectors[1:], strict=False)],
                [],
                text,
            )
        return row

    async def recover_stuck(self) -> int:
        """При старте переводит зависшие в ``processing`` резюме в ``failed``."""
        border = self._clock.now() - timedelta(seconds=self._settings.resume_processing_timeout_s)
        stuck = await self._repos.resumes.list_processing_started_before(border)
        for resume in stuck:
            await self._repos.resumes.complete_processing(
                resume.user_id,
                resume.id,
                status=ResumeStatus.FAILED.value,
                error_message=MSG_TIMEOUT,
                fragments=(),
                embedding=None,
                model_version=None,
                processed_at=self._clock.now(),
            )
        return len(stuck)
