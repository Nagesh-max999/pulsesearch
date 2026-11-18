from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_document_repo
from app.models.user import User
from app.repositories.document_repo import DocumentRepository
from app.repositories.search_event_repo import SearchEventRepository
from app.schemas.search import AnalyticsSummary

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/search", response_model=AnalyticsSummary)
async def search_analytics(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = SearchEventRepository(session)
    summary = await repo.summary_for_user(current_user.id)
    return AnalyticsSummary(**summary)


@router.get("/documents")
async def document_analytics(
    current_user: User = Depends(get_current_user),
    document_repo: DocumentRepository = Depends(get_document_repo),
):
    counts = await document_repo.count_by_status_for_user(current_user.id)
    return {
        "total": sum(counts.values()),
        "by_status": counts,
    }
