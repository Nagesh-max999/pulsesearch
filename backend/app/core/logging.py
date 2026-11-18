import logging
import sys
import time
import uuid
from contextvars import ContextVar

from app.core.config import get_settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(settings.log_level)
    root.handlers = [handler]


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


class Timer:
    """Context manager that measures elapsed wall time in milliseconds."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self.elapsed_ms: float = 0.0
        return self

    def __exit__(self, *exc) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
