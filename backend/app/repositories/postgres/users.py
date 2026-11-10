"""Пользователи, сессии и токены писем на PostgreSQL."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg

from app.db.database import Database
from app.domain.models import AuthToken, Role, Session, TokenPurpose, User
from app.repositories.errors import AlreadyExistsError
from app.repositories.postgres._mapping import sql_template

_USER_COLUMNS = "id, email, password_hash, role, email_confirmed_at, consent_version, consent_accepted_at, created_at"


def _user(row: asyncpg.Record) -> User:
    return User(
        id=str(row["id"]),
        email=row["email"],
        password_hash=row["password_hash"],
        role=Role(row["role"]),
        email_confirmed_at=row["email_confirmed_at"],
        consent_version=row["consent_version"],
        consent_accepted_at=row["consent_accepted_at"],
        created_at=row["created_at"],
    )


class PgUserRepository:
    """Пользователи в таблице ``app_user``."""

    def __init__(self, db: Database) -> None:
        """Создаёт репозиторий."""
        self._db = db

    async def get_by_id(self, user_id: str) -> User | None:
        """Возвращает пользователя по идентификатору."""
        row = await self._db.pool.fetchrow(
            sql_template("SELECT {cols} FROM app_user WHERE id = $1", cols=_USER_COLUMNS), user_id
        )
        return _user(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        """Возвращает пользователя по адресу без учёта регистра."""
        row = await self._db.pool.fetchrow(
            sql_template("SELECT {cols} FROM app_user WHERE lower(email) = lower($1)", cols=_USER_COLUMNS), email
        )
        return _user(row) if row else None

    async def create(self, user: User) -> None:
        """Создаёт пользователя; занятый адрес даёт ``AlreadyExistsError``."""
        try:
            await self._db.pool.execute(
                sql_template(
                    "INSERT INTO app_user ({cols}) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)", cols=_USER_COLUMNS
                ),
                user.id,
                user.email,
                user.password_hash,
                user.role.value,
                user.email_confirmed_at,
                user.consent_version,
                user.consent_accepted_at,
                user.created_at,
            )
        except asyncpg.UniqueViolationError as exc:
            raise AlreadyExistsError(user.email.lower()) from exc

    async def update_password_hash(self, user_id: str, password_hash: str) -> None:
        """Обновляет хеш пароля."""
        await self._db.pool.execute("UPDATE app_user SET password_hash = $2 WHERE id = $1", user_id, password_hash)

    async def mark_email_confirmed(self, user_id: str, at: datetime) -> None:
        """Отмечает адрес подтверждённым."""
        await self._db.pool.execute("UPDATE app_user SET email_confirmed_at = $2 WHERE id = $1", user_id, at)

    async def delete(self, user_id: str) -> None:
        """Удаляет пользователя; каскад убирает сессии, токены, резюме, выдачу и избранное."""
        await self._db.pool.execute("DELETE FROM app_user WHERE id = $1", user_id)


class PgSessionRepository:
    """Сессии в таблице ``user_session``."""

    def __init__(self, db: Database) -> None:
        """Создаёт репозиторий."""
        self._db = db

    async def create(self, session: Session) -> None:
        """Сохраняет сессию."""
        await self._db.pool.execute(
            "INSERT INTO user_session (token_hash, user_id, created_at, expires_at) VALUES ($1, $2, $3, $4)",
            session.token_hash,
            session.user_id,
            session.created_at,
            session.expires_at,
        )

    async def get(self, token_hash: str) -> Session | None:
        """Возвращает сессию по хешу токена."""
        row = await self._db.pool.fetchrow(
            "SELECT token_hash, user_id, created_at, expires_at FROM user_session WHERE token_hash = $1", token_hash
        )
        if row is None:
            return None
        return Session(row["token_hash"], str(row["user_id"]), row["created_at"], row["expires_at"])

    async def delete(self, token_hash: str) -> None:
        """Удаляет сессию."""
        await self._db.pool.execute("DELETE FROM user_session WHERE token_hash = $1", token_hash)

    async def delete_all_for_user(self, user_id: str) -> None:
        """Удаляет все сессии пользователя."""
        await self._db.pool.execute("DELETE FROM user_session WHERE user_id = $1", user_id)

    async def delete_expired(self, now: datetime) -> int:
        """Удаляет истёкшие сессии и возвращает их число."""
        rows = await self._db.pool.fetch("DELETE FROM user_session WHERE expires_at <= $1 RETURNING 1", now)
        return len(rows)


class PgAuthTokenRepository:
    """Токены писем в таблице ``auth_token``."""

    def __init__(self, db: Database) -> None:
        """Создаёт репозиторий."""
        self._db = db

    async def create(self, token: AuthToken) -> None:
        """Сохраняет токен."""
        await self._db.pool.execute(
            "INSERT INTO auth_token (token_hash, user_id, purpose, created_at, expires_at, used_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            token.token_hash,
            token.user_id,
            token.purpose.value,
            token.created_at,
            token.expires_at,
            token.used_at,
        )

    async def get_valid(self, token_hash: str, purpose: TokenPurpose, now: datetime) -> AuthToken | None:
        """Возвращает токен, если он не использован и не истёк."""
        row: Any = await self._db.pool.fetchrow(
            "SELECT token_hash, user_id, purpose, created_at, expires_at, used_at FROM auth_token "
            "WHERE token_hash = $1 AND purpose = $2 AND used_at IS NULL AND expires_at > $3",
            token_hash,
            purpose.value,
            now,
        )
        if row is None:
            return None
        return AuthToken(
            row["token_hash"],
            str(row["user_id"]),
            TokenPurpose(row["purpose"]),
            row["created_at"],
            row["expires_at"],
            row["used_at"],
        )

    async def mark_used(self, token_hash: str, at: datetime) -> None:
        """Помечает токен использованным."""
        await self._db.pool.execute("UPDATE auth_token SET used_at = $2 WHERE token_hash = $1", token_hash, at)

    async def invalidate_for_user(self, user_id: str, purpose: TokenPurpose) -> None:
        """Удаляет все токены пользователя с данным назначением."""
        await self._db.pool.execute(
            "DELETE FROM auth_token WHERE user_id = $1 AND purpose = $2", user_id, purpose.value
        )

    async def last_created_at(self, user_id: str, purpose: TokenPurpose) -> datetime | None:
        """Момент создания последнего токена."""
        value: datetime | None = await self._db.pool.fetchval(
            "SELECT max(created_at) FROM auth_token WHERE user_id = $1 AND purpose = $2", user_id, purpose.value
        )
        return value

    async def delete_all_for_user(self, user_id: str) -> None:
        """Удаляет все токены пользователя."""
        await self._db.pool.execute("DELETE FROM auth_token WHERE user_id = $1", user_id)
