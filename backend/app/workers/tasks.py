import logging
import uuid

from arq import Retry

from app.core.db import AsyncSessionLocal
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.services.embeddings.factory import get_embedding_provider
from app.services.event_bus import DocumentEventBus
from app.services.processing_service import ProcessingError, ProcessingService

logger = logging.getLogger(__name__)


async def process_document_task(ctx: dict, document_id: str, job_id: str) -> None:
    """arq task: run the ingestion pipeline for one document.

    Retries transient failures with exponential backoff up to the job's
    max_attempts (tracked in Postgres, not just in arq) so retry state survives
    a worker restart.
    """
    async with AsyncSessionLocal() as session:
        document_repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)
        job_repo = JobRepository(session)
        event_bus = DocumentEventBus(ctx["redis"])

        job = await job_repo.get_by_id(uuid.UUID(job_id))
        if job is None:
            logger.error("Job %s not found; skipping", job_id)
            return

        await job_repo.mark_running(job)
        await session.commit()

        service = ProcessingService(
            session=session,
            document_repo=document_repo,
            chunk_repo=chunk_repo,
            embedding_provider=get_embedding_provider(),
            event_bus=event_bus,
        )

        try:
            await service.process(uuid.UUID(document_id))
        except ProcessingError as exc:
            attempt = ctx.get("job_try", job.attempt_count)
            retrying = attempt < job.max_attempts
            job = await job_repo.get_by_id(uuid.UUID(job_id))
            await job_repo.mark_failed(job, str(exc), retrying=retrying)
            await session.commit()
            if retrying:
                backoff_seconds = min(60, 2**attempt)
                raise Retry(defer=backoff_seconds) from exc
            logger.error("Document %s failed permanently after %s attempts", document_id, attempt)
            return

        job = await job_repo.get_by_id(uuid.UUID(job_id))
        await job_repo.mark_completed(job)
        await session.commit()
