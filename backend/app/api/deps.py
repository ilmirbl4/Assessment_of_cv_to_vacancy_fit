"""Зависимости FastAPI: контейнер, текущий пользователь, проверка ролей."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.container import Container
from app.domain.models import Role, User
from app.services import errors


def get_container(request: Request) -> Container:
    """Контейнер зависимостей приложения."""
    container: Container = request.app.state.container
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
