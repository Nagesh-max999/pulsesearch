import logging
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import DOCUMENTS_PROCESSED, EMBEDDING_DURATION
from app.models.document import DocumentStatus
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.document_repo import DocumentRepository
from app.services.chunking import chunk_text, estimate_token_count
from app.services.embeddings.base import EmbeddingProvider
from app.services.event_bus import DocumentEventBus
from app.services.storage.base import StorageProvider
from app.services.storage.factory import get_storage_provider
from app.services.text_extraction import TextExtractionError, extract_text, normalize_text

logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    pass


class ProcessingService:
    """Runs the full ingestion pipeline for one document.

    Idempotency: replace_chunks() deletes-then-inserts chunks for the document inside
    the same flush, and update_status()/set_raw_text() are plain overwrites — so
    re-running this pipeline for the same document_id (e.g. after a retried job)
    converges to the same end state instead of duplicating chunks or corrupting the
    index.
    """

    def __init__(
        self,
        session: AsyncSession,
        document_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        embedding_provider: EmbeddingProvider,
        event_bus: DocumentEventBus,
        storage_provider: StorageProvider | None = None,
    ):
        self.session = session
        self.document_repo = document_repo
        self.chunk_repo = chunk_repo
        self.embedding_provider = embedding_provider
        self.event_bus = event_bus
        self.storage_provider = storage_provider or get_storage_provider()

    async def process(self, document_id: uuid.UUID) -> None:
        document = await self.document_repo.get_by_id(document_id)
        if document is None:
            raise ProcessingError(f"Document {document_id} not found")

        try:
            await self._set_status(document_id, DocumentStatus.PROCESSING, "Extracting text")
            content = await self.storage_provider.read(document.storage_path)
            raw_text = extract_text(content, document.mime_type, document.original_filename)
            normalized = normalize_text(raw_text)
            await self.document_repo.set_raw_text(document, normalized)
            await self._set_status(document_id, DocumentStatus.TEXT_EXTRACTED, "Text extracted")

            await self._set_status(document_id, DocumentStatus.INDEXING, "Chunking and indexing")
            pieces = chunk_text(normalized)
            if not pieces:
                raise ProcessingError("Document produced no chunks after normalization")

            await self._set_status(
                document_id, DocumentStatus.GENERATING_EMBEDDING, "Generating embeddings"
            )
            embed_start = time.perf_counter()
            embeddings = await self.embedding_provider.embed_texts(pieces)
            EMBEDDING_DURATION.observe(time.perf_counter() - embed_start)

            chunk_rows = [
                {
                    "chunk_index": idx,
                    "content": piece,
                    "token_count": estimate_token_count(piece),
                    "embedding": embedding,
                }
                for idx, (piece, embedding) in enumerate(zip(pieces, embeddings, strict=True))
            ]
            await self.chunk_repo.replace_chunks(document_id, chunk_rows)

            await self.document_repo.update_status(document, DocumentStatus.COMPLETED)
            await self.session.commit()
            DOCUMENTS_PROCESSED.labels(status="completed").inc()
            await self.event_bus.publish(
                document_id,
                DocumentStatus.COMPLETED.value,
                "Document is now searchable",
                user_id=document.user_id,
            )
        except TextExtractionError as exc:
            await self._fail(document, str(exc))
            raise ProcessingError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected error processing document %s", document_id)
            await self._fail(document, f"Unexpected error: {exc}")
            raise ProcessingError(str(exc)) from exc

    async def _set_status(
        self, document_id: uuid.UUID, status: DocumentStatus, message: str
    ) -> None:
        document = await self.document_repo.get_by_id(document_id)
        await self.document_repo.update_status(document, status)
        await self.session.commit()
        await self.event_bus.publish(document_id, status.value, message, user_id=document.user_id)

    async def _fail(self, document, error_message: str) -> None:
        await self.session.rollback()
        document = await self.document_repo.get_by_id(document.id)
        await self.document_repo.update_status(document, DocumentStatus.FAILED, error_message)
        await self.session.commit()
        DOCUMENTS_PROCESSED.labels(status="failed").inc()
        await self.event_bus.publish(
            document.id, DocumentStatus.FAILED.value, error_message, user_id=document.user_id
        )
