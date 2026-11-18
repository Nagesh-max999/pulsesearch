import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    job_id: uuid.UUID
    message: str = "Upload successful"


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentChunkPreview(BaseModel):
    chunk_index: int
    content: str

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentResponse):
    chunk_count: int
    chunk_previews: list[DocumentChunkPreview]
