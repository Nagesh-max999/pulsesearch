# Performance Benchmarks

Numbers below come from running `scripts/benchmark.py` against a live instance — they
are measured, not estimated. Re-run the script to regenerate them for your own hardware:

```bash
python scripts/benchmark.py --base-url http://localhost:8000 --requests 200 --concurrency 10
```

The script:
1. Registers a fresh benchmark user.
2. Uploads sample documents and waits for each to reach `COMPLETED`, measuring
   end-to-end upload → searchable latency.
3. Fires N search requests (round-robining keyword/semantic/hybrid modes) at the given
   concurrency and reports p50/p95/p99 latency.

## Latest run

Measured 2026-09-21 against the API + worker running natively (not containerized this
time) against `docker compose`'s Postgres 16 + pgvector and Redis 7, on the same
non-dedicated Windows Docker Desktop host as the original run below — numbers are
directionally comparable to the 2026-08-29 baseline, not a controlled A/B. Rate
limiting was disabled for this run (`RATE_LIMIT_ENABLED=false`): the benchmark drives
200 concurrent requests through one registered user on purpose, to characterize raw
latency, and a per-user rate limit correctly rejects that pattern — confirmed by
running once with it left on, which produced 170/200 429s, exactly as designed. A
real deployment would leave rate limiting on; this benchmark exists to measure
latency, not to re-validate the limiter. Command:

```bash
python scripts/benchmark.py --base-url http://localhost:8000 --requests 200 --concurrency 10 --upload-count 5
```

```
Document upload -> COMPLETED (end-to-end)
  requests: 5   errors: 0
  mean:  670.26 ms
  p50:   563.20 ms
  p95:   1083.30 ms
  p99:   1083.30 ms
  min/max: 559.59 / 1083.30 ms

Search latency (200 requests, concurrency=10, round-robin keyword/semantic/hybrid)
  requests: 200   errors: 0
  mean:  257.83 ms
  p50:   116.22 ms
  p95:   1513.01 ms
  p99:   1989.61 ms
  min/max: 53.37 / 2590.56 ms
```

Interpretation:
- **Document processing (~560-1100ms end-to-end)**: essentially unchanged from the
  original baseline — text extraction + chunking + embedding generation + chunk
  insert for a short document, embedding model already warm.
- **Search p50 of ~116ms vs p99 of ~2s**: worse than the original baseline's p99 of
  ~1.75s, and the reason is reranking (added after that baseline was measured, see
  "What this benchmark caught" below) — a cross-encoder pass is a second CPU-bound
  inference call stacked on top of the embedding inference the original baseline
  already identified as the p99 bottleneck. `RERANK_CANDIDATE_POOL` (default 10,
  see below) trades reranking quality for exactly this cost; disabling reranking
  entirely (`RERANK_ENABLED=false`) removes it altogether for a latency-sensitive
  deployment that doesn't need the relevance-ordering improvement.

### What this benchmark caught: three real bugs, found by running it

Earlier runs of this exact script (before the fixes below) surfaced three genuine
bugs that unit tests didn't catch because they only manifest under real concurrent
load, a fresh process, or both:

1. **Model loading blocked the event loop.** `SentenceTransformerProvider` ran
   `asyncio.to_thread()` around the *encode* call only, but the (synchronous, and on a
   cold cache, 100+ second) *model load* happened directly on the event loop. The first
   semantic/hybrid request after startup stalled every other in-flight request in the
   same process — a p99 of **12.3s** on one run. Fixed by moving the load itself inside
   the threaded call.
2. **`functools.lru_cache` isn't single-flight under concurrency.** With loading moved
   to a thread, concurrent first requests could still both call `SentenceTransformer(...)`
   at once — `lru_cache`'s lock only protects its internal bookkeeping, not the wrapped
   call itself, so two threads raced to construct the same torch model and it corrupted
   ("Cannot copy out of meta tensor"), producing errors on **134 of 200** requests in one
   run. Fixed with an explicit `threading.Lock` around model construction
   (`sentence_transformer_provider.py`).
3. **The reranker had no startup warmup at all.** When reranking was added, only the
   embedding model got the `lifespan` warmup treatment above — the cross-encoder was
   still lazy-loaded on first use. Measured directly: the first search of *any* mode
   (not just semantic/hybrid — reranking runs on keyword results too) after a fresh
   start paid **2345ms** inline for that load; the very next request, same process,
   took 97ms. Fixed by warming the reranker in `app.main`'s `lifespan` the same way
   the embedding model already was (`app/main.py`) — confirmed the fix directly: the
   first search after a fresh start now takes ~300ms instead of ~2.3s.

All three are now additionally addressed at the root: both models are baked into the
Docker image at build time and eagerly warmed in the API's `lifespan` hook (and the
embedding model separately in the worker's `on_startup`, since only the worker uses it
there — the worker never reranks), so production traffic never hits a cold model load
in the first place. The lock fix remains as defense in depth if warmup itself is ever
skipped or fails.

## Notes on what affects these numbers

- **The embedding model is warmed at container startup**, not on first request — both
  `app.main`'s `lifespan` and the worker's `on_startup` call `embed_texts()` once before
  accepting traffic/jobs, and the model itself is baked into the Docker image at build
  time (no runtime download). This was a deliberate fix after benchmarking exposed how
  bad a cold first-request load was; see above.
- **The reranker model is warmed the same way**, in the API's `lifespan` only (the
  worker never reranks, so it has no reason to load this model) — see bug 3 above.
  `RERANK_ENABLED=false` skips loading it entirely if a deployment doesn't want the
  relevance-ordering improvement at any latency cost.
- **`RERANK_CANDIDATE_POOL` (default 10) directly trades reranking quality for
  latency** — each candidate is one more cross-encoder forward pass. Benchmarking
  showed 25 roughly doubling search p95/p99 under concurrent load versus 10, for no
  meaningfully better ordering at the result-set sizes this app actually returns
  (default page size 10).
- **Cache hits are near-instant** — repeated identical queries within the cache TTL
  (`SEARCH_CACHE_TTL_SECONDS`, default 60s) are served from Redis without touching
  Postgres, the embedding model, or the reranker.
- **Hybrid mode is the slowest of the three** — it runs both a keyword and a semantic
  query and blends the results, roughly the cost of both individual modes combined,
  plus reranking on top if enabled.
- **Embedding generation dominates document processing time**, not text extraction or
  chunking — CPU-bound inference on the local model.
- **Rate limiting will reject a benchmark-style traffic pattern by design** — a single
  user firing many rapid requests is exactly what `RATE_LIMIT_SEARCH_PER_MINUTE`/
  `RATE_LIMIT_UPLOAD_PER_MINUTE` exist to reject. Disable rate limiting (or spread
  load across multiple registered users) when benchmarking raw latency; leave it on
  for anything measuring real deployment behavior.
