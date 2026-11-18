import uuid

from arq import ArqRedis

from app.core.config import Settings
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.services.storage.base import StorageProvider

# Real onboarding content, not placeholder text — these documents explain the
# product itself, so they're useful to read even outside of the fact that they
# also give a fresh account something real to search over. Seeded through the
# exact same save -> create -> enqueue path as a normal upload (see
# app/api/routes/documents.py's upload_document), so a new user watches these
# move through the real processing pipeline live rather than appearing
# instantly as if they were never processed.
_WELCOME = """Welcome to PulseSearch

PulseSearch is a real-time document search engine. Upload a PDF or text file
and it is processed asynchronously: text extraction, sentence-aware chunking,
full-text indexing, and embedding generation, with live status updates
streamed to the browser over Server-Sent Events the whole way through.

Once processing completes, a document becomes searchable three ways. Keyword
search uses PostgreSQL full-text search and is best for exact terms you know
are in the text. Semantic search compares meaning using vector embeddings, so
it can find a relevant passage even if it does not share any exact words with
your query. Hybrid search blends both signals, then optionally reranks the
top candidates with a cross-encoder for a second, more accurate pass at
relevance ordering.

These three documents were created automatically when your account was
created, and processed through the same pipeline any file you upload goes
through. Delete them any time from the Documents page.
"""

_HYBRID_SEARCH = """How Hybrid Search Works

A pure keyword search engine matches the words you typed. It is fast and
precise, but it misses a passage that says "improve API response times"
when you searched for "make requests faster" — no shared words, even though
the meaning is the same.

A pure semantic search engine embeds your query and every indexed chunk into
the same vector space, then ranks by cosine similarity. It catches meaning-
based matches like the example above, but it can also surface passages that
are topically related without actually answering the query, since it has no
concept of an exact term match.

Hybrid search runs both retrieval paths in parallel, normalizes each score
into a comparable range, and combines them with a weighted sum. The default
weighting favors keyword precision slightly over semantic recall, which
tends to suit short, technical queries — but the right balance depends on
the kind of documents and queries a given deployment actually sees, which is
why both weights and the reranking step are configurable rather than fixed.
"""

_PROCESSING_PIPELINE = """The Document Processing Pipeline

Uploading a file only ever does two things synchronously: validate it, and
save it. The API responds immediately with status 202 Accepted and a job id,
rather than making you wait for the whole pipeline to finish.

A background worker then picks up the job and moves the document through a
sequence of statuses: UPLOADED, PROCESSING, TEXT_EXTRACTED, INDEXING,
GENERATING_EMBEDDING, and finally COMPLETED (or FAILED, with a specific
error message, if something in the pipeline could not recover). Each
transition is published over Redis and streamed to any open browser tab for
that document, which is what drives the live progress indicator on the
document detail page.

Retries are tracked in the database, not just in the queue, so a worker
restart mid-job does not lose track of how many attempts a document has had.
Re-running the pipeline for the same document is safe: chunks are replaced
atomically rather than appended to, so a retried job converges to the same
end state instead of duplicating search results.
"""

SEED_DOCUMENTS: list[tuple[str, bytes]] = [
    ("welcome-to-pulsesearch.txt", _WELCOME.encode("utf-8")),
    ("how-hybrid-search-works.txt", _HYBRID_SEARCH.encode("utf-8")),
    ("the-processing-pipeline.txt", _PROCESSING_PIPELINE.encode("utf-8")),
]


async def seed_demo_documents(
    user_id: uuid.UUID,
    document_repo: DocumentRepository,
    job_repo: JobRepository,
    storage: StorageProvider,
    arq_pool: ArqRedis,
    settings: Settings,
) -> None:
    for filename, content in SEED_DOCUMENTS:
        storage_path = await storage.save(user_id, filename, content)
        document = await document_repo.create(
            user_id=user_id,
            title=filename,
            original_filename=filename,
            storage_path=storage_path,
            mime_type="text/plain",
            file_size_bytes=len(content),
        )
        job = await job_repo.create(document.id, max_attempts=settings.job_max_retries)
        await arq_pool.enqueue_job("process_document_task", str(document.id), str(job.id))
