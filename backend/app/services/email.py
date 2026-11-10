"""Отправка писем: консольная и SMTP-реализации, тексты писем."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.services.security import mask_email

log = logging.getLogger("app.email")

SIGNATURE = "Система подбора вакансий"


class EmailSender(Protocol):
    """Интерфейс отправителя писем."""

    def send(self, to: str, subject: str, text: str) -> None:
        """Отправляет письмо (блокирующий вызов)."""
        ...


class ConsoleEmailSender:
    """Пишет в лог тему и ссылку, адрес маскирует (тесты и запуск без Docker)."""

    def send(self, to: str, subject: str, text: str) -> None:
        """Выводит письмо в лог."""
        log.info("Письмо для %s: %s\n%s", mask_email(to), subject, text)


class SmtpEmailSender:
    """Отправка через ``smtplib``."""

    def __init__(
        self,
        host: str,
        port: int,
        security: str,
        user: str,
        password: str,
        sender: str,
        sender_name: str,
        timeout: float,
    ) -> None:
        """Сохраняет параметры соединения (``security``: ssl / starttls / none)."""
        self._host, self._port, self._security = host, port, security
        self._user, self._password = user, password
        self._sender, self._sender_name, self._timeout = sender, sender_name, timeout

    def send(self, to: str, subject: str, text: str) -> None:
        """Собирает письмо в UTF-8 и отправляет его."""
        message = EmailMessage()
        message["From"] = f'"{self._sender_name}" <{self._sender}>'
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text, charset="utf-8")
        if self._security == "ssl":
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(self._host, self._port, timeout=self._timeout)
        else:
            smtp = smtplib.SMTP(self._host, self._port, timeout=self._timeout)
        with smtp:
            if self._security == "starttls":
                smtp.starttls()
            if self._user:
                smtp.login(self._user, self._password)
            smtp.send_message(message)


def confirmation_message(link: str, ttl_hours: int) -> tuple[str, str]:
    """Тема и текст письма подтверждения адреса."""
    return (
        "Подтвердите адрес электронной почты",
        "Здравствуйте! Вы зарегистрировались в системе подбора вакансий. "
        f"Чтобы подтвердить адрес, перейдите по ссылке: {link}. "
        f"Ссылка действует {_hours(ttl_hours)}. "
        "Если вы не регистрировались, просто проигнорируйте это письмо.\n\n" + SIGNATURE,
    )


def reset_message(link: str, ttl_minutes: int) -> tuple[str, str]:
    """Тема и текст письма восстановления пароля."""
    return (
        "Восстановление пароля",
        "Здравствуйте! Мы получили запрос на смену пароля. "
        f"Чтобы задать новый пароль, перейдите по ссылке: {link}. "
        f"Ссылка действует {_minutes(ttl_minutes)}. "
        "Если вы не запрашивали смену пароля, просто проигнорируйте это письмо: пароль останется прежним.\n\n"
        + SIGNATURE,
    )


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} {one}"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} {few}"
    return f"{n} {many}"


def _hours(n: int) -> str:
    return _plural(n, "час", "часа", "часов")


def _minutes(n: int) -> str:
    if n % 60 == 0:
        return _hours(n // 60)
    return _plural(n, "минуту", "минуты", "минут")
