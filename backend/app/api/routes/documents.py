import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import (
    get_arq_pool,
    get_chunk_repo_read,
    get_current_user,
    get_current_user_sse,
    get_db,
    get_document_repo,
    get_document_repo_read,
    get_redis_client,
)
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.models.document import DocumentStatus
from app.models.user import User
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.schemas.document import (
    DocumentChunkPreview,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services.event_bus import DocumentEventBus
from app.services.storage.base import FileTooLargeError, UnsupportedFileTypeError
from app.services.storage.factory import get_storage_provider

router = APIRouter(prefix="/api/documents", tags=["documents"])
_upload_rate_limit = rate_limit("upload", "rate_limit_upload_per_minute")

PDF_MAGIC = b"%PDF-"


def _validate_content(ext: str, content: bytes) -> None:
    if ext == ".pdf" and not content.startswith(PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension is .pdf but content is not a valid PDF",
        )


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_upload_rate_limit)],
)
async def upload_document(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    document_repo: DocumentRepository = Depends(get_document_repo),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    settings = get_settings()
    storage = get_storage_provider()

    content = await file.read()
    try:
        ext = storage.validate(file.filename or "", len(content))
        _validate_content(ext, content)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {exc}. Allowed: {settings.allowed_extensions_list}",
        ) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large: {exc} bytes (max {settings.max_upload_size_bytes})",
        ) from exc

    storage_path = await storage.save(current_user.id, file.filename or "upload", content)

    document = await document_repo.create(
        user_id=current_user.id,
        title=file.filename or "Untitled",
        original_filename=file.filename or "upload",
        storage_path=storage_path,
        mime_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(content),
    )

    job_repo = JobRepository(session)
    job = await job_repo.create(document.id, max_attempts=settings.job_max_retries)
    await session.commit()

    await arq_pool.enqueue_job("process_document_task", str(document.id), str(job.id))

    return DocumentUploadResponse(document=DocumentResponse.model_validate(document), job_id=job.id)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    document_repo: DocumentRepository = Depends(get_document_repo_read),
):
    items, total = await document_repo.list_for_user(current_user.id, page, page_size)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    document_repo: DocumentRepository = Depends(get_document_repo_read),
    chunk_repo: ChunkRepository = Depends(get_chunk_repo_read),
):
    document = await document_repo.get_by_id_for_user(document_id, current_user.id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    previews = await chunk_repo.get_previews(document_id)
    chunk_count = await chunk_repo.count_for_document(document_id)

    return DocumentDetailResponse(
        **DocumentResponse.model_validate(document).model_dump(),
        chunk_count=chunk_count,
        chunk_previews=[DocumentChunkPreview.model_validate(c) for c in previews],
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    document_repo: DocumentRepository = Depends(get_document_repo),
):
    document = await document_repo.get_by_id_for_user(document_id, current_user.id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    storage = get_storage_provider()
    await storage.delete(document.storage_path)
    await document_repo.delete(document)


@router.get("/{document_id}/events")
async def document_events(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user_sse),
    document_repo: DocumentRepository = Depends(get_document_repo),
    redis=Depends(get_redis_client),
):
    document = await document_repo.get_by_id_for_user(document_id, current_user.id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    event_bus = DocumentEventBus(redis)
    terminal_statuses = {DocumentStatus.COMPLETED.value, DocumentStatus.FAILED.value}

    async def event_generator():
        yield {"event": "status", "data": document.status.value}
        if document.status.value in terminal_statuses:
            return
        async for event in event_bus.subscribe(document_id):
            yield {"event": "status", "data": event["status"]}
            if event["status"] in terminal_statuses:
                break

    return EventSourceResponse(event_generator())
