import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import JobStatus, ProcessingJob


class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, document_id: uuid.UUID, max_attempts: int) -> ProcessingJob:
        job = ProcessingJob(
            document_id=document_id, status=JobStatus.PENDING, max_attempts=max_attempts
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> ProcessingJob | None:
        result = await self.session.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def mark_running(self, job: ProcessingJob) -> ProcessingJob:
        job.status = JobStatus.RUNNING
        job.attempt_count += 1
        await self.session.flush()
        return job

    async def mark_completed(self, job: ProcessingJob) -> ProcessingJob:
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(UTC)
        job.last_error = None
        await self.session.flush()
        return job

    async def mark_failed(self, job: ProcessingJob, error: str, retrying: bool) -> ProcessingJob:
        job.status = JobStatus.RETRYING if retrying else JobStatus.FAILED
        job.last_error = error[:2000]
        await self.session.flush()
        return job
