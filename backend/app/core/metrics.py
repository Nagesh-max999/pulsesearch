import re
import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
SEARCH_REQUESTS = Counter(
    "search_requests_total",
    "Total search requests by mode",
    ["mode"],
)
DOCUMENTS_PROCESSED = Counter(
    "documents_processed_total",
    "Total documents that finished processing, by outcome",
    ["status"],
)
EMBEDDING_DURATION = Histogram(
    "embedding_generation_seconds",
    "Time spent generating embeddings for a batch of chunks",
)

# Matches a UUID path segment so /api/documents/<uuid>/events collapses to
# /api/documents/{id}/events instead of creating one label per document ever
# requested — unbounded label cardinality is a real way to make Prometheus
# fall over.
_UUID_SEGMENT = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _normalize_path(path: str) -> str:
    return _UUID_SEGMENT.sub("{id}", path)


class MetricsMiddleware:
    """Records request count and latency per (method, normalized path, status).

    Implemented as raw ASGI, not Starlette's `BaseHTTPMiddleware` — same reason
    as RequestIDMiddleware: BaseHTTPMiddleware runs the downstream app in a
    separate task, which breaks request-scoped async SQLAlchemy sessions.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start
            path = _normalize_path(scope["path"])
            method = scope["method"]
            if path != "/metrics":
                HTTP_REQUESTS.labels(method=method, path=path, status=status_code).inc()
                HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)


def metrics_response() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
