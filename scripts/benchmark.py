"""Performance benchmark for PulseSearch.

Runs real HTTP requests against a running instance (default http://localhost:8000)
and reports measured latency percentiles. Nothing here is hardcoded or simulated —
every number comes from an actual request/response round trip.

Usage:
    python scripts/benchmark.py --requests 200 --concurrency 10
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import uuid
from dataclasses import dataclass, field

import httpx

SAMPLE_DOCS = [
    (
        "perf-notes-1.txt",
        "Improving API performance often starts with database optimization, such as "
        "adding indexes and using connection pooling. Caching frequently accessed data "
        "in Redis reduces load on the primary database.",
    ),
    (
        "perf-notes-2.txt",
        "Asynchronous processing and background job queues let the API return "
        "immediately instead of blocking on slow work like embedding generation or "
        "file parsing.",
    ),
    (
        "perf-notes-3.txt",
        "Query optimization, batching writes, and avoiding N+1 database queries are "
        "some of the highest-leverage changes for reducing p95 latency under load.",
    ),
]

SEARCH_QUERIES = [
    "database optimization",
    "connection pooling",
    "how do I make my API faster",
    "background job queue",
    "caching strategy",
]


@dataclass
class Result:
    latencies_ms: list[float] = field(default_factory=list)
    errors: int = 0

    def summary(self, label: str) -> str:
        if not self.latencies_ms:
            return f"{label}: no successful requests (errors={self.errors})"
        sorted_lat = sorted(self.latencies_ms)
        n = len(sorted_lat)

        def pct(p: float) -> float:
            idx = min(n - 1, int(round(p / 100 * n)) - 1)
            return sorted_lat[max(0, idx)]

        return (
            f"{label}\n"
            f"  requests: {n + self.errors}   errors: {self.errors}\n"
            f"  mean:  {statistics.mean(sorted_lat):.2f} ms\n"
            f"  p50:   {pct(50):.2f} ms\n"
            f"  p95:   {pct(95):.2f} ms\n"
            f"  p99:   {pct(99):.2f} ms\n"
            f"  min/max: {sorted_lat[0]:.2f} / {sorted_lat[-1]:.2f} ms"
        )


async def register_and_login(client: httpx.AsyncClient) -> str:
    email = f"benchmark-{uuid.uuid4().hex[:10]}@example.com"
    password = "benchmark123456"
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": password}
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def seed_documents(client: httpx.AsyncClient, headers: dict) -> None:
    for filename, content in SAMPLE_DOCS:
        files = {"file": (filename, content.encode(), "text/plain")}
        resp = await client.post("/api/documents", files=files, headers=headers)
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
        await _wait_for_job(client, headers, job_id)


async def _wait_for_job(client: httpx.AsyncClient, headers: dict, job_id: str, timeout_s: float = 60) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = await client.get(f"/api/jobs/{job_id}", headers=headers)
        resp.raise_for_status()
        status = resp.json()["status"]
        if status in ("COMPLETED", "FAILED"):
            return
        await asyncio.sleep(0.5)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout_s}s")


async def run_search_benchmark(
    client: httpx.AsyncClient, headers: dict, total_requests: int, concurrency: int
) -> Result:
    result = Result()
    semaphore = asyncio.Semaphore(concurrency)

    async def one_request(i: int) -> None:
        query = SEARCH_QUERIES[i % len(SEARCH_QUERIES)]
        mode = ["KEYWORD", "SEMANTIC", "HYBRID"][i % 3]
        start = time.perf_counter()
        try:
            resp = await client.get(
                "/api/search", params={"q": query, "mode": mode}, headers=headers
            )
            resp.raise_for_status()
            elapsed_ms = (time.perf_counter() - start) * 1000
            result.latencies_ms.append(elapsed_ms)
        except (httpx.HTTPError, httpx.HTTPStatusError):
            result.errors += 1

    async def bound(i: int) -> None:
        async with semaphore:
            await one_request(i)

    await asyncio.gather(*(bound(i) for i in range(total_requests)))
    return result


async def run_upload_benchmark(client: httpx.AsyncClient, headers: dict, count: int) -> Result:
    result = Result()
    for i in range(count):
        content = f"Benchmark document {i} discussing indexing throughput and search latency."
        files = {"file": (f"bench-{i}.txt", content.encode(), "text/plain")}
        start = time.perf_counter()
        try:
            resp = await client.post("/api/documents", files=files, headers=headers)
            resp.raise_for_status()
            job_id = resp.json()["job_id"]
            await _wait_for_job(client, headers, job_id)
            elapsed_ms = (time.perf_counter() - start) * 1000
            result.latencies_ms.append(elapsed_ms)
        except (httpx.HTTPError, TimeoutError):
            result.errors += 1
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="PulseSearch performance benchmark")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=200, help="search requests to run")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--upload-count", type=int, default=5, help="documents to upload/process")
    args = parser.parse_args()

    async with httpx.AsyncClient(base_url=args.base_url, timeout=30.0) as client:
        print(f"Target: {args.base_url}")
        token = await register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}

        print("\nSeeding documents for search benchmark...")
        await seed_documents(client, headers)

        print(f"\nRunning document upload+processing benchmark ({args.upload_count} docs)...")
        upload_result = await run_upload_benchmark(client, headers, args.upload_count)
        print(upload_result.summary("Document upload -> COMPLETED (end-to-end)"))

        print(f"\nRunning search benchmark ({args.requests} requests, concurrency={args.concurrency})...")
        search_result = await run_search_benchmark(
            client, headers, args.requests, args.concurrency
        )
        print(search_result.summary("Search latency"))


if __name__ == "__main__":
    asyncio.run(main())
