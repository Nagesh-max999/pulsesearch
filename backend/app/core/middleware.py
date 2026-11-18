from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import new_request_id, request_id_ctx


class RequestIDMiddleware:
    """Stamps each request with a correlation ID (X-Request-ID header + log context).

    Implemented as raw ASGI rather than Starlette's `BaseHTTPMiddleware` /
    `@app.middleware("http")` — that helper runs the downstream app in a separate task,
    which corrupts request-scoped async SQLAlchemy sessions (asyncpg raises "another
    operation is in progress" under concurrent use of one connection).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = new_request_id()
        token = request_id_ctx.set(request_id)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_ctx.reset(token)
