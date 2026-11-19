"""Аутентификация, сессии, подтверждение адреса, сброс пароля, удаление учётной записи."""

from __future__ import annotations

import asyncio
import logging
import re
import smtplib
import uuid
from dataclasses import dataclass
from datetime import timedelta

from app.config import Settings
from app.domain.clock import Clock
from app.domain.models import AuthToken, Role, Session, TokenPurpose, User
from app.reference import consent
from app.repositories.errors import AlreadyExistsError
from app.repositories.factory import Repositories
from app.services import errors
from app.services.email import EmailSender, confirmation_message, reset_message
from app.services.rate_limit import RateLimiter
from app.services.security import (
    MAX_EMAIL,
    PasswordService,
    hash_token,
    is_valid_email,
    is_valid_password,
    new_token,
    normalize_email,
)
from app.services.tasks import TaskRegistry

log = logging.getLogger("app.auth")

MSG_EMAIL = "Введите корректный адрес электронной почты"
MSG_WEAK = "Пароль должен содержать не менее 8 символов, буквы и цифры"
MSG_CONSENT = "Для регистрации необходимо дать согласие на обработку персональных данных"
RESEND_PAUSE = timedelta(seconds=60)
MAX_TOKEN = 256


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Результат входа: пользователь и значение cookie."""

    user: User
    session_token: str
    max_age_seconds: int


class AuthService:
    """Регистрация, вход, выход, подтверждение адреса, восстановление пароля."""

    def __init__(
        self,
        repos: Repositories,
        passwords: PasswordService,
        limiter: RateLimiter,
        sender: EmailSender,
        tasks: TaskRegistry,
        clock: Clock,
        settings: Settings,
    ) -> None:
        """Создаёт сервис."""
        self._repos = repos
        self._passwords = passwords
        self._limiter = limiter
        self._sender = sender
        self._tasks = tasks
        self._clock = clock
        self._settings = settings

    # ---------- сессии ----------

    async def authenticate(self, token: str | None) -> User:
        """Возвращает пользователя по токену сессии.

        Raises:
            Unauthorized: сессия не найдена, истекла или пользователь удалён.
        """
        if not token:
            raise errors.UnauthorizedError
        digest = hash_token(token)
        session = await self._repos.sessions.get(digest)
        if session is None:
            raise errors.UnauthorizedError
        if session.expires_at <= self._clock.now():
            await self._repos.sessions.delete(digest)
            raise errors.UnauthorizedError
        user = await self._repos.users.get_by_id(session.user_id)
        if user is None:
            raise errors.UnauthorizedError
        return user

    async def _open_session(self, user: User) -> LoginResult:
        token = new_token()
        now = self._clock.now()
        ttl = timedelta(hours=self._settings.session_ttl_hours)
        await self._repos.sessions.create(Session(hash_token(token), user.id, now, now + ttl))
        return LoginResult(user, token, int(ttl.total_seconds()))

    # ---------- регистрация ----------

    async def register(self, email: str, password: str, consent_accepted: bool, consent_version: str) -> None:
        """Регистрирует соискателя и отправляет письмо подтверждения.

        Raises:
            ValidationFailed: ошибки полей (все сразу).
            EmailTaken: адрес уже зарегистрирован.
        """
        fields: dict[str, str] = {}
        if not is_valid_email(email):
            fields["email"] = MSG_EMAIL
        if not is_valid_password(password):
            fields["password"] = MSG_WEAK
        if consent_accepted is not True or consent_version != consent()["version"]:
            fields["consent_accepted"] = MSG_CONSENT
        if fields:
            raise errors.ValidationFailedError(fields=fields)
        now = self._clock.now()
        user = User(
            id=str(uuid.uuid4()),
            email=normalize_email(email),
            password_hash=await asyncio.to_thread(self._passwords.hash, password),
            role=Role.SEEKER,
            email_confirmed_at=None,
            consent_version=consent_version,
            consent_accepted_at=now,
            created_at=now,
        )
        try:
            await self._repos.users.create(user)
        except AlreadyExistsError as exc:
            raise errors.EmailTakenError from exc
        await self._send_confirmation(user)

    async def _send_confirmation(self, user: User) -> None:
        await self._repos.tokens.invalidate_for_user(user.id, TokenPurpose.CONFIRM_EMAIL)
        ttl = timedelta(hours=self._settings.confirm_token_ttl_hours)
        token = await self._issue_token(user.id, TokenPurpose.CONFIRM_EMAIL, ttl)
        link = f"{self._settings.public_base_url.rstrip('/')}/confirm-email?token={token}"
        subject, text = confirmation_message(link, self._settings.confirm_token_ttl_hours)
        self._dispatch(user.email, subject, text)

    async def _issue_token(self, user_id: str, purpose: TokenPurpose, ttl: timedelta) -> str:
        token = new_token()
        now = self._clock.now()
        await self._repos.tokens.create(AuthToken(hash_token(token), user_id, purpose, now, now + ttl))
        return token

    def _dispatch(self, to: str, subject: str, text: str) -> None:
        async def job() -> None:
            try:
                await asyncio.to_thread(self._sender.send, to, subject, text)
            except smtplib.SMTPRecipientsRefused as exc:
                code, reply = next(iter(exc.recipients.values()), (0, b""))
                self._log_smtp_rejection(exc, code, reply)
            except smtplib.SMTPResponseException as exc:
                self._log_smtp_rejection(exc, exc.smtp_code, exc.smtp_error)
            except OSError as exc:
                log.error("Не удалось отправить письмо (%s, errno=%s)", type(exc).__name__, exc.errno)
            except Exception as exc:
                log.error("Не удалось отправить письмо (%s)", type(exc).__name__)
            else:
                log.info("Письмо принято SMTP-сервером")

        self._tasks.spawn(job(), name="send-email")

    @staticmethod
    def _log_smtp_rejection(exc: smtplib.SMTPException, code: int, reply: bytes | str) -> None:
        if isinstance(reply, bytes):
            reply = reply.decode("ascii", errors="replace")
        enhanced_code = re.search(r"\b[245]\.\d{1,3}\.\d{1,3}\b", reply)
        log.error(
            "SMTP отклонил письмо (%s, код %s, расширенный код %s)",
            type(exc).__name__,
            code,
            enhanced_code[0] if enhanced_code else "отсутствует",
        )

    # ---------- вход и выход ----------

    async def login(self, email: str, password: str, ip: str) -> LoginResult:
        """Выполняет вход.

        Raises:
            TooManyRequests: превышен лимит неудачных попыток.
            InvalidCredentials: неверный адрес или пароль.
            EmailNotConfirmed: адрес не подтверждён.
        """
        normalized = normalize_email(email)
        key = f"{ip}|{normalized}"
        now = self._clock.now()
        if self._limiter.blocked(key, now):
            raise errors.TooManyRequestsError
        user = await self._repos.users.get_by_email(normalized) if len(normalized) <= MAX_EMAIL else None
        if user is None or len(password) > 128:
            await asyncio.to_thread(self._passwords.verify_dummy, password[:128])
            self._limiter.register_failure(key, now)
            raise errors.InvalidCredentialsError
        if not await asyncio.to_thread(self._passwords.verify, user.password_hash, password):
            self._limiter.register_failure(key, now)
            raise errors.InvalidCredentialsError
        if user.email_confirmed_at is None:
            raise errors.EmailNotConfirmedError
        self._limiter.reset(key)
        if self._passwords.needs_rehash(user.password_hash):
            await self._repos.users.update_password_hash(
                user.id, await asyncio.to_thread(self._passwords.hash, password)
            )
        return await self._open_session(user)

    async def logout(self, token: str | None) -> None:
        """Удаляет сессию и текущий подбор пользователя; без сессии ничего не делает."""
        if not token:
            return
        digest = hash_token(token)
        session = await self._repos.sessions.get(digest)
        if session is not None:
            await self._repos.match_runs.delete_for_user(session.user_id)
            await self._repos.sessions.delete(digest)

    # ---------- подтверждение и сброс ----------

    async def confirm_email(self, token: str) -> None:
        """Подтверждает адрес по токену.

        Raises:
            TokenInvalid: токен недействителен.
        """
        stored = await self._valid_token(token, TokenPurpose.CONFIRM_EMAIL)
        now = self._clock.now()
        await self._repos.users.mark_email_confirmed(stored.user_id, now)
        await self._repos.tokens.mark_used(stored.token_hash, now)

    async def _valid_token(self, token: str, purpose: TokenPurpose) -> AuthToken:
        if not token or len(token) > MAX_TOKEN:
            raise errors.TokenInvalidError
        stored = await self._repos.tokens.get_valid(hash_token(token), purpose, self._clock.now())
        if stored is None:
            raise errors.TokenInvalidError
        return stored

    async def resend_confirmation(self, email: str) -> None:
        """Повторно отправляет письмо, если адрес не подтверждён и пауза прошла."""
        user = await self._repos.users.get_by_email(normalize_email(email))
        if user is None or user.email_confirmed_at is not None:
            return
        last = await self._repos.tokens.last_created_at(user.id, TokenPurpose.CONFIRM_EMAIL)
        if last is not None and self._clock.now() - last <= RESEND_PAUSE:
            return
        await self._send_confirmation(user)

    async def request_password_reset(self, email: str) -> None:
        """Отправляет письмо со ссылкой сброса пароля (ответ API не зависит от существования адреса)."""
        user = await self._repos.users.get_by_email(normalize_email(email))
        if user is None:
            return
        last = await self._repos.tokens.last_created_at(user.id, TokenPurpose.RESET)
        if last is not None and self._clock.now() - last <= RESEND_PAUSE:
            return
        await self._repos.tokens.invalidate_for_user(user.id, TokenPurpose.RESET)
        ttl = timedelta(minutes=self._settings.reset_token_ttl_minutes)
        token = await self._issue_token(user.id, TokenPurpose.RESET, ttl)
        link = f"{self._settings.public_base_url.rstrip('/')}/reset-password?token={token}"
        subject, text = reset_message(link, self._settings.reset_token_ttl_minutes)
        self._dispatch(user.email, subject, text)

    async def confirm_password_reset(self, token: str, new_password: str) -> None:
        """Задаёт новый пароль по токену и закрывает все сессии.

        Raises:
            TokenInvalid: токен недействителен.
            ValidationFailed: пароль не проходит правила.
        """
        stored = await self._valid_token(token, TokenPurpose.RESET)
        if not is_valid_password(new_password):
            raise errors.ValidationFailedError(fields={"new_password": MSG_WEAK})
        await self._repos.users.update_password_hash(
            stored.user_id, await asyncio.to_thread(self._passwords.hash, new_password)
        )
        await self._repos.tokens.mark_used(stored.token_hash, self._clock.now())
        await self._repos.sessions.delete_all_for_user(stored.user_id)

    # ---------- учётная запись ----------

    async def delete_account(self, user: User) -> None:
        """Безвозвратно удаляет данные пользователя.

        Пользователь удаляется первым: в PostgreSQL каскад убирает всё остальное одной операцией, а следующие
        вызовы становятся пустыми; хранилищу в памяти они по-прежнему нужны.
        """
        await self._repos.users.delete(user.id)
        await self._repos.favorites.delete_all_for_user(user.id)
        await self._repos.match_runs.delete_for_user(user.id)
        await self._repos.resumes.delete(user.id)
        await self._repos.tokens.delete_all_for_user(user.id)
        await self._repos.sessions.delete_all_for_user(user.id)

    async def ensure_admin(self) -> None:
        """Создаёт администратора из настроек, если его ещё нет."""
        email, password = self._settings.admin_email, self._settings.admin_password
        if not email or not password:
            return
        if await self._repos.users.get_by_email(normalize_email(email)) is not None:
            return
        now = self._clock.now()
        await self._repos.users.create(
            User(
                id=str(uuid.uuid4()),
                email=normalize_email(email),
                password_hash=self._passwords.hash(password),
                role=Role.ADMIN,
                email_confirmed_at=now,
                consent_version=None,
                consent_accepted_at=None,
                created_at=now,
            )
        )
