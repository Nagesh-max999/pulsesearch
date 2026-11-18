# PulseSearch

A real-time, intelligent search engine: upload documents, watch them get processed
live, and search them by keyword, semantic meaning, or a hybrid of both.

Built as a portfolio project demonstrating production-quality engineering — clean
architecture, real async background processing, genuine keyword + vector search,
caching, retries/idempotency, tests, and Docker-based deployment. See
[`docs/system-design.md`](docs/system-design.md) for the full interview-style writeup.

## What it does

1. Register / log in (JWT auth).
2. Upload a PDF or text document — the API responds immediately; nothing blocks on processing.
3. Watch the document move through `UPLOADED → PROCESSING → TEXT_EXTRACTED → INDEXING → GENERATING_EMBEDDING → COMPLETED` in real time (Server-Sent Events, not polling).
4. Search across your documents by **keyword** (Postgres full-text search), **semantic** meaning (local embedding model + pgvector cosine similarity), or **hybrid** (both, blended).
5. View basic analytics: search volume, mode breakdown, zero-result queries, average latency.

## Architecture

```
Next.js  --HTTP + SSE-->  FastAPI  ---> PostgreSQL (+ pgvector)
                              |
                              +-------> Redis (cache, queue, pub/sub)
                              |
                              +-------> arq background worker
                                            |
                                            +--> local embedding model (sentence-transformers)
```

Full diagram, component reasoning, and request/processing flows:
[`docs/architecture.md`](docs/architecture.md).

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, TanStack Query |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy (async), Alembic |
| Database | PostgreSQL 16 + pgvector |
| Cache / queue | Redis 7, arq (async background jobs) |
| Search | Postgres full-text search (keyword) + pgvector cosine similarity (semantic) |
| Embeddings | Local `sentence-transformers` model, abstracted behind an `EmbeddingProvider` interface |
| Realtime | Server-Sent Events over Redis pub/sub |
| Auth | JWT + bcrypt password hashing |
| Infra | Docker, Docker Compose, GitHub Actions |

Rationale for each choice is in [`docs/architecture.md`](docs/architecture.md#why-these-choices).

## Repository structure

```
pulsesearch/
├── frontend/                 Next.js app
├── backend/
│   ├── app/
│   │   ├── api/               routers + auth/dependency wiring
│   │   ├── core/               config, db, redis, security, logging
│   │   ├── models/             SQLAlchemy models
│   │   ├── schemas/            Pydantic request/response models
│   │   ├── services/           business logic (search, processing, embeddings, cache, storage)
│   │   ├── repositories/       query layer
│   │   ├── workers/             arq background task + worker settings
│   │   └── main.py
│   ├── alembic/                 migrations
│   └── tests/
├── scripts/benchmark.py       performance benchmark (real measured numbers)
├── docs/                      architecture, database, performance, system design
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Running locally

### Option A: Docker Compose (recommended)

```bash
cp .env.example .env      # edit JWT_SECRET at minimum
docker compose up -d
```

This starts Postgres, Redis, runs migrations (`migrate` service), then starts the API,
worker, and frontend. API: http://localhost:8000 (docs at `/docs`). Frontend:
http://localhost:3000.

> The compose file maps Postgres to host port `5433` and Redis to `6380` (instead of
> the usual `5432`/`6379`) to avoid clashing with any native Postgres/Redis install on
> your machine. Containers still talk to each other over the internal Docker network
> using the standard ports regardless of the host mapping — only `DATABASE_URL`/
> `REDIS_URL` values used by tools running *outside* Docker (e.g. `psql`, `pytest`)
> need the remapped host ports.

### Option B: Run backend/frontend natively

**Backend** (requires Postgres with `pgvector` and Redis running — `docker compose up -d postgres redis` works for just those two):

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # or .venv/bin/activate on macOS/Linux
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-dev.txt
cp ../.env.example .env   # then set:
# DATABASE_URL=postgresql+asyncpg://pulsesearch:pulsesearch@localhost:5433/pulsesearch
# REDIS_URL=redis://localhost:6380/0
# (5433/6380 are the compose file's remapped host ports, not the container-internal ones)
alembic upgrade head
uvicorn app.main:app --reload          # API
arq app.workers.worker.WorkerSettings  # worker, in a second terminal
```

**Frontend**:

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

## Environment variables

See [`.env.example`](.env.example) for the full list (database, Redis, JWT, upload
limits, embedding model, CORS). Never commit a real `.env` — it's gitignored.

## Testing

```bash
cd backend
pytest                 # unit tests (chunking, text extraction, storage validation)
                        # + integration tests against a real Postgres/Redis (see tests/conftest.py)
ruff check .            # lint
```

```bash
cd frontend
npm run lint
npx tsc --noEmit
```

Integration tests exercise the real ingestion pipeline (real text extraction, real
chunking, real local embeddings) and real Postgres full-text/vector search — no mocked
core functionality. See [`docs/system-design.md#13-security`](docs/system-design.md) and
the test files under `backend/tests/` for what's covered: auth, upload validation,
authorization (cross-user isolation), processing idempotency, keyword/semantic/hybrid
search correctness, caching, and analytics.

## Performance

`scripts/benchmark.py` measures real p50/p95/p99 search latency and document
processing time against a running instance. See [`docs/performance.md`](docs/performance.md).

## Deployment

Any host that can run Docker Compose (or the two containers + a managed Postgres/Redis)
works. Practical steps:

1. Provision Postgres (with the `vector` extension available — the `pgvector/pgvector`
   image already includes it) and Redis, or use managed equivalents.
2. Set `.env` with production values (`JWT_SECRET` especially — generate a long random
   value, e.g. `openssl rand -hex 32`).
3. `docker compose up -d --build` (or push images to a registry and deploy them behind
   a load balancer / reverse proxy with TLS termination).
4. Point the frontend's `NEXT_PUBLIC_API_URL` at the backend's public URL and rebuild.

CI (`.github/workflows/ci.yml`) lints, tests, and builds both images on every push/PR —
treat a green pipeline as the deploy gate.

## Trade-offs

See [`docs/system-design.md#15-trade-offs`](docs/system-design.md#15-trade-offs) for the
full table (local embeddings vs. hosted API, pgvector vs. dedicated vector DB, word-based
chunking, local disk storage, single Postgres instance) and the reasoning behind each.

## Documentation index

- [`docs/architecture.md`](docs/architecture.md) — component diagram, request/processing flows, failure handling, scalability
- [`docs/database.md`](docs/database.md) — schema, ER diagram, indexing decisions
- [`docs/system-design.md`](docs/system-design.md) — full system-design writeup (interview prep)
- [`docs/performance.md`](docs/performance.md) — how to run and read the benchmark
