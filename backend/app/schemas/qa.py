import uuid

from pydantic import BaseModel


class AskCitation(BaseModel):
    document_id: uuid.UUID
    title: str
    snippet: str


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[AskCitation]
    latency_ms: float
