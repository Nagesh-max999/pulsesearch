import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import analytics, ask, auth, documents, events, health, jobs, metrics, search
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import MetricsMiddleware
from app.core.middleware import RequestIDMiddleware
from app.core.queue import create_arq_pool
from app.services.embeddings.factory import get_embedding_provider
from app.services.reranking.factory import get_reranker_provider

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    app.state.arq_pool = await create_arq_pool()

    # Loads (and on a cold cache, downloads) the embedding model before accepting
    # traffic. Without this, the first semantic/hybrid search after a fresh start
    # pays that cost inline — anywhere from a couple of seconds to over a minute —
    # instead of it being a predictable, one-time part of startup.
    try:
        await get_embedding_provider().embed_texts(["startup warmup"])
        logger.info("Embedding model warmed up")
    except Exception:
        logger.exception("Embedding model warmup failed; will retry lazily on first use")

    # Same reasoning as the embedding warmup above, and just as costly if
    # skipped: the cross-encoder reranker is a second, separate model that
    # search() lazy-loads on first use when RERANK_ENABLED is on. Measured
    # impact of skipping this: the first search of *any* mode after a fresh
    # start paid ~2.3s inline for this load alone (see docs/performance.md).
    settings = get_settings()
    if settings.rerank_enabled:
        try:
            await get_reranker_provider().rerank("startup warmup", ["warmup candidate"])
            logger.info("Reranker model warmed up")
        except Exception:
            logger.exception("Reranker warmup failed; will retry lazily on first use")

    logger.info("PulseSearch API starting up")
    yield
    await app.state.arq_pool.close()
    logger.info("PulseSearch API shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="PulseSearch API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(MetricsMiddleware)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        error_id = uuid.uuid4().hex[:12]
        logger.exception("Unhandled error [%s] on %s %s", error_id, request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "error_id": error_id},
        )

    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(events.router)
    app.include_router(search.router)
    app.include_router(ask.router)
    app.include_router(jobs.router)
    app.include_router(analytics.router)

    return app


app = create_app()
