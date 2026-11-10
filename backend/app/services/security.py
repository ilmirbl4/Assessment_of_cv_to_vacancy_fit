"""Пароли, токены, проверка email и маскирование (раздел 6.1 инструкции)."""

from __future__ import annotations

import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
MAX_EMAIL = 254
MIN_PASSWORD = 8
MAX_PASSWORD = 128


def normalize_email(value: str) -> str:
    """Обрезает пробелы и приводит адрес к нижнему регистру."""
    return value.strip().lower()


def is_valid_email(value: str) -> bool:
    """Проверяет адрес тем же регулярным выражением, что и клиент."""
    stripped = value.strip()
    return len(stripped) <= MAX_EMAIL and EMAIL_RE.match(stripped) is not None


def is_valid_password(value: str) -> bool:
    """Длина 8..128, есть буква (любая буква Юникода) и цифра ``0-9``."""
    return (
        MIN_PASSWORD <= len(value) <= MAX_PASSWORD
        and any(ch.isalpha() for ch in value)
        and any(ch in "0123456789" for ch in value)
    )


def mask_email(value: str) -> str:
    """Маскирует адрес для логов: ``s***@example.com``."""
    local, _, domain = value.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def new_token() -> str:
    """Случайный токен для сессии или письма."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 токена; в хранилище лежит только он."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PasswordService:
    """Хеширование паролей argon2id."""

    def __init__(self, fast: bool = False) -> None:
        """Создаёт сервис; ``fast=True`` задаёт облегчённые параметры (только тесты)."""
        self._hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1) if fast else PasswordHasher()
        self._dummy = self._hasher.hash(secrets.token_urlsafe(16))

    def hash(self, password: str) -> str:
        """Возвращает argon2id-хеш пароля."""
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        """Проверяет пароль по хешу."""
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def verify_dummy(self, password: str) -> None:
        """Проверка против фиктивного хеша: выравнивает время ответа для неизвестного адреса."""
        self.verify(self._dummy, password)

    def needs_rehash(self, password_hash: str) -> bool:
        """Нужно ли пересчитать хеш."""
        return self._hasher.check_needs_rehash(password_hash)
