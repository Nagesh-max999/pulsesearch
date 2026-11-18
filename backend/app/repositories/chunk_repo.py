import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk
from app.models.document import Document


class ChunkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def replace_chunks(
        self,
        document_id: uuid.UUID,
        chunks: list[dict],
    ) -> list[DocumentChunk]:
        """Idempotently replace all chunks for a document in one transaction."""
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        created = []
        for chunk in chunks:
            row = DocumentChunk(
                document_id=document_id,
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                token_count=chunk["token_count"],
                embedding=chunk.get("embedding"),
            )
            self.session.add(row)
            created.append(row)
        await self.session.flush()
        return created

    async def set_embeddings(self, chunk_embeddings: list[tuple[uuid.UUID, list[float]]]) -> None:
        for chunk_id, embedding in chunk_embeddings:
            chunk = await self.session.get(DocumentChunk, chunk_id)
            if chunk is not None:
                chunk.embedding = embedding
        await self.session.flush()

    async def get_previews(self, document_id: uuid.UUID, limit: int = 5) -> list[DocumentChunk]:
        result = await self.session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_for_document(self, document_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(DocumentChunk.document_id == document_id)
        )
        return result.scalar_one()

    async def keyword_search(
        self, user_id: uuid.UUID, query: str, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        """Rank chunks with Postgres full-text search (ts_rank_cd), scoped to the user."""
        tsquery = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank_cd(DocumentChunk.content_tsv, tsquery).label("rank")
        headline = func.ts_headline(
            "english",
            DocumentChunk.content,
            tsquery,
            "MaxFragments=1,MaxWords=35,MinWords=15",
        ).label("snippet")

        base = (
            select(
                DocumentChunk.document_id,
                Document.title,
                headline,
                rank,
                DocumentChunk.chunk_index,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.user_id == user_id, DocumentChunk.content_tsv.op("@@")(tsquery))
        )

        count_result = await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base.order_by(rank.desc()).offset(offset).limit(limit)
        )
        rows = [
            {
                "document_id": r.document_id,
                "title": r.title,
                "snippet": r.snippet,
                "score": float(r.rank),
                "chunk_index": r.chunk_index,
            }
            for r in result.all()
        ]
        return rows, total

    async def semantic_search(
        self, user_id: uuid.UUID, query_embedding: list[float], limit: int, offset: int
    ) -> tuple[list[dict], int]:
        """Rank chunks by cosine distance against the query embedding, scoped to the user."""
        distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")

        base = (
            select(
                DocumentChunk.document_id,
                Document.title,
                DocumentChunk.content,
                distance,
                DocumentChunk.chunk_index,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.user_id == user_id, DocumentChunk.embedding.is_not(None))
        )

        count_result = await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base.order_by(distance.asc()).offset(offset).limit(limit)
        )
        rows = [
            {
                "document_id": r.document_id,
                "title": r.title,
                "snippet": r.content[:280],
                "score": max(0.0, 1.0 - float(r.distance)),
                "chunk_index": r.chunk_index,
            }
            for r in result.all()
        ]
        return rows, total
