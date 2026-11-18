import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search_event import SearchEvent, SearchMode


class SearchEventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(
        self,
        user_id: uuid.UUID | None,
        query: str,
        mode: SearchMode,
        result_count: int,
        latency_ms: float,
    ) -> SearchEvent:
        event = SearchEvent(
            user_id=user_id,
            query=query,
            mode=mode,
            result_count=result_count,
            latency_ms=latency_ms,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def summary_for_user(self, user_id: uuid.UUID, days: int = 30) -> dict:
        since = datetime.now(UTC) - timedelta(days=days)
        base = select(SearchEvent).where(
            SearchEvent.user_id == user_id, SearchEvent.created_at >= since
        )

        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()

        by_mode = await self.session.execute(
            select(SearchEvent.mode, func.count())
            .where(SearchEvent.user_id == user_id, SearchEvent.created_at >= since)
            .group_by(SearchEvent.mode)
        )
        mode_counts = {mode.value: count for mode, count in by_mode.all()}

        zero_result = (
            await self.session.execute(
                select(func.count()).where(
                    SearchEvent.user_id == user_id,
                    SearchEvent.created_at >= since,
                    SearchEvent.result_count == 0,
                )
            )
        ).scalar_one()

        avg_latency = (
            await self.session.execute(
                select(func.coalesce(func.avg(SearchEvent.latency_ms), 0.0)).where(
                    SearchEvent.user_id == user_id, SearchEvent.created_at >= since
                )
            )
        ).scalar_one()

        top_queries_result = await self.session.execute(
            select(SearchEvent.query, func.count().label("count"))
            .where(SearchEvent.user_id == user_id, SearchEvent.created_at >= since)
            .group_by(SearchEvent.query)
            .order_by(func.count().desc())
            .limit(10)
        )
        top_queries = [{"query": q, "count": c} for q, c in top_queries_result.all()]

        return {
            "total_searches": total,
            "keyword_searches": mode_counts.get(SearchMode.KEYWORD.value, 0),
            "semantic_searches": mode_counts.get(SearchMode.SEMANTIC.value, 0),
            "hybrid_searches": mode_counts.get(SearchMode.HYBRID.value, 0),
            "zero_result_searches": zero_result,
            "avg_latency_ms": float(avg_latency),
            "top_queries": top_queries,
        }
