import uuid

from pydantic import BaseModel, Field

from app.models.search_event import SearchMode


class SearchResultItem(BaseModel):
    document_id: uuid.UUID
    title: str
    snippet: str
    score: float
    matched_terms: list[str] = Field(default_factory=list)
    keyword_score: float | None = None
    semantic_score: float | None = None
    rerank_score: float | None = None


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    results: list[SearchResultItem]
    total: int
    page: int
    page_size: int
    latency_ms: float


class AnalyticsSummary(BaseModel):
    total_searches: int
    keyword_searches: int
    semantic_searches: int
    hybrid_searches: int
    zero_result_searches: int
    avg_latency_ms: float
    top_queries: list[dict]
