"""Зависимости FastAPI: контейнер, текущий пользователь, проверка ролей."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.container import Container
from app.domain.models import Role, User
from app.services import errors


def get_container(request: Request) -> Container:
    """Контейнер зависимостей приложения."""
    container: Container | None = getattr(request.app.state, "container", None)
    if container is None:
        raise HTTPException(503, "Система подготавливается. Состояние: /api/v1/status")
    path = request.url.path
    if (
        path.startswith(("/api/v1/matching", "/api/v1/vacancies"))
        or (path == "/api/v1/resume" and request.method == "PUT")
    ) and not request.app.state.bootstrap["matching_ready"]:
        raise HTTPException(503, "Подготовка моделей и вакансий ещё не завершена. Состояние: /api/v1/status")
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


async def current_user(request: Request, container: ContainerDep) -> User:
    """Пользователь по cookie сессии; иначе 401."""
    token = request.cookies.get(container.settings.session_cookie_name)
    return await container.auth.authenticate(token)


CurrentUser = Annotated[User, Depends(current_user)]


async def require_seeker(user: CurrentUser) -> User:
    """Только соискатель; администратор получает 403."""
    if user.role != Role.SEEKER:
        raise errors.ForbiddenError
    return user


async def require_admin(user: CurrentUser) -> User:
    """Только администратор (задел для панели администратора)."""
    if user.role != Role.ADMIN:
        raise errors.ForbiddenError
    return user


Seeker = Annotated[User, Depends(require_seeker)]
