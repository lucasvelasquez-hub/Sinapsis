"""Per-request identifier: accepted from X-Request-ID or generated, echoed back,
attached to error envelopes and to every JSON log line."""

import re
import uuid
from contextvars import ContextVar

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[\w.-]{1,64}$")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def request_id_of(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


class RequestIdMiddleware:
    """Pure ASGI middleware (no BaseHTTPMiddleware: keeps streaming and contextvars)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Request(scope).headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        request_id_var.set(request_id)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_header)
