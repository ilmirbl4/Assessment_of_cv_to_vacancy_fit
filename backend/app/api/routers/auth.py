"""Аутентификация, сессии, согласие и удаление учётной записи."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api.deps import ContainerDep, CurrentUser, Seeker
from app.api.routers.common import errors
from app.reference import consent as consent_data
from app.schemas.models import (
    Consent,
    EmailRequest,
    Empty,
    LoginRequest,
    PasswordResetConfirmRequest,
    RegisterRequest,
    TokenRequest,
    User,
    user_out,
)

router = APIRouter()


def _drop_cookie(response: Response, container: ContainerDep) -> None:
    response.delete_cookie(
        container.settings.session_cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=container.settings.cookie_secure,
    )


@router.get(
    "/auth/me",
    response_model=User,
    summary="Текущий пользователь",
    responses=errors(401),
    description="Возвращает пользователя, вошедшего в систему.",
)
async def me(user: CurrentUser) -> User:
    """Текущий пользователь."""
    return user_out(user)


@router.post(
    "/auth/register",
    status_code=201,
    response_model=Empty,
    summary="Регистрация соискателя",
    description="Создаёт учётную запись и отправляет письмо со ссылкой подтверждения адреса.",
    responses=errors(409, 422),
)
async def register(body: RegisterRequest, container: ContainerDep) -> Empty:
    """Регистрация соискателя."""
    await container.auth.register(body.email, body.password, body.consent_accepted, body.consent_version)
    return Empty()


@router.post(
    "/auth/login",
    response_model=User,
    summary="Вход",
    description="Проверяет адрес и пароль, создаёт сессию и устанавливает cookie.",
    responses=errors(401, 403, 429),
)
async def login(body: LoginRequest, request: Request, response: Response, container: ContainerDep) -> User:
    """Вход в систему."""
    ip = request.client.host if request.client else "-"
    result = await container.auth.login(body.email, body.password, ip)
    response.set_cookie(
        container.settings.session_cookie_name,
        result.session_token,
        max_age=result.max_age_seconds,
        path="/",
        httponly=True,
        samesite="lax",
        secure=container.settings.cookie_secure,
    )
    return user_out(result.user)


@router.post(
    "/auth/logout",
    status_code=204,
    response_class=Response,
    summary="Выход",
    description="Закрывает сессию, удаляет текущий подбор и сбрасывает cookie.",
)
async def logout(request: Request, container: ContainerDep) -> Response:
    """Выход из системы."""
    await container.auth.logout(request.cookies.get(container.settings.session_cookie_name))
    response = Response(status_code=204)
    _drop_cookie(response, container)
    return response


@router.post(
    "/auth/confirm-email",
    response_model=Empty,
    summary="Подтверждение адреса",
    description="Подтверждает адрес электронной почты по токену из письма.",
    responses=errors(400),
)
async def confirm_email(body: TokenRequest, container: ContainerDep) -> Empty:
    """Подтверждение адреса."""
    await container.auth.confirm_email(body.token)
    return Empty()


@router.post(
    "/auth/resend-confirmation",
    status_code=202,
    response_model=Empty,
    summary="Повторное письмо",
    description="Повторно отправляет письмо подтверждения. Ответ всегда одинаковый.",
)
async def resend_confirmation(body: EmailRequest, container: ContainerDep) -> Empty:
    """Повторная отправка письма подтверждения."""
    await container.auth.resend_confirmation(body.email)
    return Empty()


@router.post(
    "/auth/password-reset/request",
    status_code=202,
    response_model=Empty,
    summary="Запрос сброса пароля",
    description="Отправляет письмо со ссылкой сброса пароля. Ответ всегда одинаковый.",
)
async def password_reset_request(body: EmailRequest, container: ContainerDep) -> Empty:
    """Запрос сброса пароля."""
    await container.auth.request_password_reset(body.email)
    return Empty()


@router.post(
    "/auth/password-reset/confirm",
    response_model=Empty,
    summary="Задание нового пароля",
    description="Задаёт новый пароль по токену из письма и закрывает все сессии.",
    responses=errors(400, 422),
)
async def password_reset_confirm(body: PasswordResetConfirmRequest, container: ContainerDep) -> Empty:
    """Подтверждение сброса пароля."""
    await container.auth.confirm_password_reset(body.token, body.new_password)
    return Empty()


@router.get(
    "/consent/current",
    response_model=Consent,
    summary="Текущее согласие на обработку ПДн",
    description="Возвращает версию, дату публикации и текст согласия.",
)
async def current_consent() -> Consent:
    """Текущее согласие."""
    data = consent_data()
    return Consent(version=data["version"], text=data["text"], published_at=data["published_at"])


@router.delete(
    "/account",
    status_code=204,
    response_class=Response,
    summary="Удаление учётной записи",
    description="Безвозвратно удаляет учётную запись и все данные соискателя.",
    responses=errors(401, 403),
)
async def delete_account(user: Seeker, container: ContainerDep) -> Response:
    """Удаление учётной записи."""
    await container.auth.delete_account(user)
    response = Response(status_code=204)
    _drop_cookie(response, container)
    return response
