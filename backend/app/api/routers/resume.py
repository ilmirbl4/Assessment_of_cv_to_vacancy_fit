"""Резюме соискателя."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile

from app.api.deps import ContainerDep, Seeker
from app.api.routers.common import errors
from app.config import MAX_RESUME_BYTES
from app.schemas.models import Resume, resume_out
from app.services import errors as svc_errors

router = APIRouter()


@router.get(
    "/resume",
    response_model=Resume,
    summary="Текущее резюме",
    description="Возвращает имя файла, время загрузки и статус обработки резюме.",
    responses=errors(401, 403, 404),
)
async def get_resume(user: Seeker, container: ContainerDep) -> Resume:
    """Текущее резюме."""
    return resume_out(await container.resumes.get(user), container.settings.app_timezone)


@router.put(
    "/resume",
    status_code=202,
    response_model=Resume,
    summary="Загрузка резюме",
    description="Принимает файл DOCX или PDF (до 5 МБ), заменяет прежнее резюме и запускает обработку.",
    responses=errors(401, 403, 413, 415, 422),
)
async def upload_resume(
    user: Seeker, container: ContainerDep, file: Annotated[UploadFile | None, File()] = None
) -> Resume:
    """Загрузка резюме."""
    if file is None or not file.filename:
        raise svc_errors.ValidationFailedError(fields={"file": "Файл не передан"})
    data = await file.read(MAX_RESUME_BYTES + 1)
    resume = await container.resumes.upload(user, file.filename, data)
    return resume_out(resume, container.settings.app_timezone)


@router.delete(
    "/resume",
    status_code=204,
    response_class=Response,
    summary="Удаление резюме",
    description="Удаляет резюме и текущий подбор.",
    responses=errors(401, 403),
)
async def delete_resume(user: Seeker, container: ContainerDep) -> Response:
    """Удаление резюме."""
    await container.resumes.delete(user)
    return Response(status_code=204)
