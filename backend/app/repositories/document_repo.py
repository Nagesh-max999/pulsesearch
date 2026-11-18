import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentStatus


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: uuid.UUID,
        title: str,
        original_filename: str,
        storage_path: str,
        mime_type: str,
        file_size_bytes: int,
    ) -> Document:
        document = Document(
            user_id=user_id,
            title=title,
            original_filename=original_filename,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            status=DocumentStatus.UPLOADED,
        )
        self.session.add(document)
        await self.session.flush()
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        result = await self.session.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

    async def get_by_id_for_user(
        self, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> Document | None:
        result = await self.session.execute(
            select(Document).where(Document.id == document_id, Document.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_with_chunks(self, document_id: uuid.UUID) -> Document | None:
        result = await self.session.execute(
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.chunks))
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: uuid.UUID, page: int, page_size: int
    ) -> tuple[list[Document], int]:
        base = select(Document).where(Document.user_id == user_id)
        total = (
            await self.session.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar_one()
        result = await self.session.execute(
            base.order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def count_by_status_for_user(self, user_id: uuid.UUID) -> dict[str, int]:
        result = await self.session.execute(
            select(Document.status, func.count())
            .where(Document.user_id == user_id)
            .group_by(Document.status)
        )
        return {status.value: count for status, count in result.all()}

    async def update_status(
        self,
        document: Document,
        status: DocumentStatus,
        error_message: str | None = None,
    ) -> Document:
        document.status = status
        document.error_message = error_message
        await self.session.flush()
        return document

    async def set_raw_text(self, document: Document, raw_text: str) -> Document:
        document.raw_text = raw_text
        await self.session.flush()
        return document

    async def delete(self, document: Document) -> None:
        await self.session.delete(document)
        await self.session.flush()
