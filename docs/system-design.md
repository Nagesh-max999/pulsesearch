# System Design — PulseSearch

A walkthrough of PulseSearch as a system-design interview problem: requirements,
architecture, trade-offs, and what would change at larger scale.

## 1. Requirements

**Functional**
- Users register/login and manage their own documents (upload PDF/text, list, view, delete).
- Uploaded documents are processed asynchronously: text extraction → chunking →
  keyword indexing → embedding generation.
- Users can search their own documents by keyword, semantic meaning, or a hybrid of both.
- Users see live processing status without refreshing or polling manually.
- Users can see basic analytics on their search and document activity.

**Non-functional**
- Search should feel interactive (sub-second for typical corpora).
- The API must never block a request on slow work (embedding generation, file parsing).
- Processing must be safe to retry (idempotent) — a crashed worker or duplicate job
  shouldn't corrupt a document's index.
- A user must never see another user's documents or search results.
- The system should degrade gracefully if Redis or the embedding model is unavailable.

## 2. Scale assumptions

This is a portfolio-scale system, not a scale-out design exercise — the requirements
above are for a single-tenant-per-user application with realistically hundreds to low
thousands of documents per user. Section 12 below discusses what changes at 10-100x
that scale.

## 3. High-level architecture

See `docs/architecture.md` for the full component diagram. Summary: Next.js frontend,
FastAPI modular monolith, PostgreSQL (+pgvector) for all persistent state, Redis for
cache/queue/pub-sub, and a separate arq worker process for background processing.

## 4. Components

- **api/** — HTTP boundary: request parsing, auth, response shaping. No business logic.
- **services/** — business logic (auth, search ranking, ingestion pipeline, caching,
  storage, embeddings). This is where decisions get made.
- **repositories/** — the only layer that writes SQL/ORM queries. Keeps query logic out
  of business logic and out of route handlers.
- **workers/** — the arq task(s) that run the ingestion pipeline outside the request cycle.
- **models/** — SQLAlchemy ORM models = source of truth for schema shape.

## 5. Data flow

**Write path (upload)**: client → API validates & stores file → DB row created
(`UPLOADED`) → job enqueued on Redis → API responds `202` immediately.

**Processing path**: worker dequeues → runs pipeline → writes chunks/embeddings →
updates status → publishes each transition to Redis pub/sub.

**Read path (search)**: client → API checks Redis cache → on miss, queries Postgres
(FTS and/or pgvector) scoped to the authenticated user → response cached → search event
recorded for analytics.

## 6. Database design

See `docs/database.md` for the full schema and ER diagram. Key decision: keyword search
(`tsvector` + GIN) and vector search (`pgvector` + IVFFlat) live in the same table
(`document_chunks`) in the same database, avoiding the operational cost of a second
search system for this scale.

## 7. Search architecture

Three modes, one code path (`SearchService`):

- **Keyword**: `websearch_to_tsquery` against the generated `tsvector` column, ranked
  with `ts_rank_cd`, snippet built with `ts_headline`.
- **Semantic**: query text → embedding (local `sentence-transformers` model) → cosine
  distance search (`pgvector`'s `<=>` operator via the IVFFlat index) → similarity =
  `1 - distance`.
- **Hybrid**: runs both, min-max normalizes keyword scores (unbounded) against the
  already-bounded [0,1] semantic scores, then blends:
  `score = 0.6 * keyword + 0.4 * semantic` (both weights are config values, not
  hardcoded — see `HYBRID_KEYWORD_WEIGHT`/`HYBRID_SEMANTIC_WEIGHT`). The 0.6/0.4 split
  favors precise term matches, which suits short technical queries typical of document
  search; a corpus with more paraphrased/conceptual queries might prefer the reverse.
  This is a reasonable starting point tuned by intuition, not a proven-optimal formula —
  `search_events` captures query/mode/result-count/latency specifically so it could be
  tuned against real usage later.

All three modes are scoped with a `WHERE documents.user_id = :current_user` predicate —
authorization is enforced at the query level, not just the API level.

## 8. Background processing

arq (async, Redis-backed) rather than Celery: the whole stack is already async
(FastAPI + SQLAlchemy async + asyncpg), so an async-native task queue avoids mixing
sync and async execution models. Celery's broker/backend/beat subsystems would be
unused weight here.

**Idempotency**: `ChunkRepository.replace_chunks()` deletes then inserts inside one
flush, so re-running the pipeline for the same `document_id` converges rather than
duplicating rows. **Retries**: attempt count is tracked in Postgres
(`processing_jobs.attempt_count`/`max_attempts`), independent of arq's in-memory retry
counter, so retry state survives a worker restart; transient failures back off
exponentially (`arq.Retry(defer=2**attempt)`) up to `JOB_MAX_RETRIES`.

## 9. Caching

Redis caches search responses, keyed `search:{user_id}:{mode}:{page}:{page_size}:{query_hash}`
with a short TTL (default 60s — short because a newly-indexed document should become
searchable quickly). Cache reads/writes are wrapped in try/except: a Redis outage is
treated as a cache miss, not a request failure — caching is a performance optimization
here, not a correctness dependency.

## 10. Real-time updates

Server-Sent Events, not WebSockets — status updates are one-directional
(server → client), so SSE's simplicity (plain HTTP, auto-reconnect, no extra protocol)
wins over WebSockets' bidirectionality that this feature doesn't need. The worker
publishes each real status transition to a Redis pub/sub channel scoped to the document
(`doc-events:{id}`); the API's SSE endpoint subscribes and streams those events through.
No polling, no client-side timers simulating progress.

## 11. Failure handling

- Extraction/embedding errors are caught in `ProcessingService`, the document is marked
  `FAILED` with a specific `error_message`, and that status is pushed over SSE — the
  user sees *why* it failed, not just a spinner that never resolves.
- `/api/health` checks Postgres and Redis independently and reports `degraded` if either
  is down, rather than a single boolean.
- A global exception handler in `main.py` catches anything unhandled, logs it
  server-side with a correlation `error_id`, and returns a generic 500 to the client —
  never a stack trace.

## 12. Scalability

See the "Scalability discussion" section in `docs/architecture.md` for the bottleneck
list and the scale-out diagram (load balancer → multiple API instances → Redis →
multiple workers → Postgres replicas → dedicated vector infra). The short version: this
architecture is deliberately single-node-first, and each scale-out step is motivated by
a specific measurable bottleneck rather than adopted preemptively.

## 13. Security

- Passwords hashed with bcrypt (via passlib), never stored or returned in plaintext.
- JWT bearer auth with expiry; every document/search/job endpoint is scoped to
  `current_user` at the query layer (not just checked at the API layer).
- Uploads validated by extension, size, and content (PDF magic-byte check) — never
  trusted by filename/MIME type alone. Filenames are sanitized and stored under a
  per-user directory with a resolved-path containment check to block traversal.
- Generic 500s hide internal errors from clients; detailed errors are logged
  server-side only.
- Search snippets are HTML-escaped on the frontend before rendering (only the
  `<b>`/`</b>` highlight tags from `ts_headline` are allowed through), since snippet
  text originates from user-uploaded document content.

## 14. Observability

Structured logs carry a per-request correlation ID (`X-Request-ID` header, also in every
log line via a `ContextVar`). `/api/health` reports component-level status. Search
latency, mode, and result counts are persisted per-query in `search_events`, which
doubles as both an analytics source and a performance-tuning dataset.

## 15. Trade-offs

| Choice | What we gave up |
|---|---|
| Local embedding model by default | Lower semantic quality than a large hosted model. `EMBEDDING_PROVIDER=hosted` (`app/services/embeddings/hosted_provider.py`) trades this away for an OpenAI-compatible API — the local model stays the zero-cost/offline default. |
| pgvector (IVFFlat) instead of a dedicated vector DB | Approximate search recall/tuning is coarser than purpose-built vector databases at very large scale — still true; see section 12. |
| Sentence-aware chunking with a word-window fallback | `app/services/chunking.py` packs whole sentences up to `max_words` (falling back to a fixed word window for punctuation-free text or an oversized single sentence) — better chunk boundaries than pure word windows, short of full token-exact/semantic chunking. |
| Cross-encoder reranking as an optional second pass | More accurate relevance ordering than the bi-encoder/FTS scores alone, at the cost of a second model load and per-query latency — `RERANK_ENABLED` toggles it off entirely when that cost isn't worth it. |
| Local disk storage by default | `STORAGE_BACKEND=s3` (`app/services/storage/s3_provider.py`) is available for S3 or any S3-compatible endpoint (MinIO included via `S3_ENDPOINT_URL`) once storage needs to scale independently of the API process; local disk stays the zero-config default. |
| Single Postgres instance by default | `DATABASE_URL_REPLICA` (`app/core/db.py`) lets read-only endpoints (search, document list/detail) route to a replica; unset, `get_db_read` transparently reuses the primary's own engine, so there's no second connection pool paid for until a replica actually exists. |
| Fixed-window Redis rate limiting | Allows a small burst across a window boundary compared to a sliding window or token bucket — not worth the extra Redis round trips at this scale. Fails open (allows the request) on Redis errors, matching the cache's philosophy: Redis outages shouldn't take the API down. |

## 16. Future improvements

- Sliding-window or token-bucket rate limiting if the fixed-window's boundary-burst
  behavior ever actually matters.
- IVFFlat re-tuning (or a move to HNSW/a dedicated vector DB) once corpus size outgrows
  the current index's `lists` parameter — see section 12.
- Read replicas are wired (`DATABASE_URL_REPLICA`) but only meaningfully tested against
  a real second Postgres instance, not just a second URL pointed at the same database.
