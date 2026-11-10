"""Сквозные ограничения: идентификатор запроса, лимит тела, проверка Origin (CSRF)."""

from __future__ import annotations

import contextvars
import json
import logging
import uuid
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import error_body
from app.config import MAX_JSON_BODY_BYTES, MAX_RESUME_BYTES

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

UNSAFE_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})
UPLOAD_LIMIT = MAX_RESUME_BYTES + 1024 * 1024


class RequestIdFilter(logging.Filter):
    """Добавляет идентификатор запроса в каждую запись журнала."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Проставляет ``record.request_id``."""
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str) -> None:
    """Настраивает формат журнала с идентификатором запроса (идемпотентно)."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    if not any(isinstance(f, RequestIdFilter) for h in root.handlers for f in h.filters):
        handler = logging.StreamHandler()
        handler.addFilter(RequestIdFilter())
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
        root.addHandler(handler)


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope["headers"]:
        if key == name:
            return str(value.decode("latin-1"))
    return None


class RequestGuardMiddleware:
    """Чистый ASGI-middleware: X-Request-ID, лимит размера тела, проверка Origin."""

    def __init__(self, app: ASGIApp, trusted_origins: list[str]) -> None:
        """Создаёт middleware; ``trusted_origins`` — разрешённые origin (схема + хост)."""
        self.app = app
        self._trusted = {o.rstrip("/") for o in trusted_origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Обрабатывает HTTP-запрос."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rid = _header(scope, b"x-request-id") or str(uuid.uuid4())
        token = request_id_var.set(rid)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [h for h in message.get("headers", []) if h[0].lower() != b"x-request-id"]
                headers.append((b"x-request-id", rid.encode("latin-1", "replace")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            rejection = self._origin_rejection(scope)
            if rejection is None:
                receive, rejection = await self._limit_body(scope, receive)
            if rejection is not None:
                await self._respond(send_with_id, *rejection)
                return
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)

    def _origin_rejection(self, scope: Scope) -> tuple[int, str, str] | None:
        if scope["method"] not in UNSAFE_METHODS:
            return None
        origin = _header(scope, b"origin")
        if not origin:
            return None
        host = urlsplit(origin).netloc
        allowed = {_header(scope, b"host"), _header(scope, b"x-forwarded-host")}
        if host in allowed or origin.rstrip("/") in self._trusted:
            return None
        return 403, "FORBIDDEN", "Недостаточно прав"

    async def _limit_body(self, scope: Scope, receive: Receive) -> tuple[Receive, tuple[int, str, str] | None]:
        upload = scope["method"] == "PUT" and scope["path"].rstrip("/").endswith("/resume")
        limit = UPLOAD_LIMIT if upload else MAX_JSON_BODY_BYTES
        length = _header(scope, b"content-length")
        too_large = (413, "REQUEST_TOO_LARGE", "Слишком большой запрос")
        if length is not None and length.isdigit() and int(length) > limit:
            return receive, too_large
        if upload or scope["method"] not in UNSAFE_METHODS:
            return receive, None
        chunks: list[Message] = []
        size = 0
        while True:
            message = await receive()
            chunks.append(message)
            if message["type"] != "http.request":
                break
            size += len(message.get("body", b""))
            if size > limit:
                return receive, too_large
            if not message.get("more_body", False):
                break
        replay = iter(chunks)

        async def replayed() -> Message:
            try:
                return next(replay)
            except StopIteration:
                return await receive()

        return replayed, None

    @staticmethod
    async def _respond(send: Send, status: int, code: str, message: str) -> None:
        body = json.dumps(error_body(code, message), ensure_ascii=False).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})
