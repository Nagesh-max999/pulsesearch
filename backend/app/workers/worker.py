import logging

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.embeddings.factory import get_embedding_provider
from app.workers.tasks import process_document_task

logger = logging.getLogger(__name__)


async def on_startup(ctx: dict) -> None:
    configure_logging()

    # The worker records its own metrics (documents_processed_total,
    # embedding_generation_seconds — see core/metrics.py) into this process's
    # memory. Unlike the API, the worker has no HTTP server of its own to serve
    # them from, so without this they'd be recorded but genuinely unreachable
    # by anything. A tiny standalone metrics server is the standard pattern for
    # a non-web background process (arq doesn't run a WSGI/ASGI app to bolt a
    # route onto); the API's own /metrics stays separate; a scrape config
    # would list both endpoints rather than expecting one to proxy the other.
    try:
        from prometheus_client import start_http_server

        start_http_server(get_settings().worker_metrics_port)
        logger.info("Worker metrics server listening on :%s", get_settings().worker_metrics_port)
    except OSError:
        logger.warning(
            "Could not bind worker metrics port %s (already in use? "
            "normal if another worker process on this host already bound it)",
            get_settings().worker_metrics_port,
        )

    # Warm the embedding model before accepting jobs, so the first document processed
    # doesn't pay the (possibly multi-minute, on a cold model cache) load cost inline
    # and risk tripping the job timeout.
    try:
        await get_embedding_provider().embed_texts(["startup warmup"])
        logger.info("Embedding model warmed up")
    except Exception:
        logger.exception("Embedding model warmup failed; will retry lazily on first job")


class WorkerSettings:
    functions = [process_document_task]
    on_startup = on_startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = get_settings().job_max_retries + 2
    job_timeout = 300
    keep_result = 3600
