import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.document import DocumentStatus
from app.models.job import JobStatus


class JobResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: JobStatus
    attempt_count: int
    max_attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class DocumentStatusEvent(BaseModel):
    document_id: uuid.UUID
    status: DocumentStatus
    message: str | None = None
    timestamp: datetime
