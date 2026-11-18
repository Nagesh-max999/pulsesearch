import io

import pytest


@pytest.mark.asyncio
async def test_get_job_for_uploaded_document(client, auth_headers):
    files = {"file": ("notes.txt", io.BytesIO(b"some content to process"), "text/plain")}
    upload = await client.post("/api/documents", files=files, headers=auth_headers)
    job_id = upload.json()["job_id"]

    resp = await client.get(f"/api/jobs/{job_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["attempt_count"] == 0


@pytest.mark.asyncio
async def test_get_job_not_found(client, auth_headers):
    resp = await client.get(
        "/api/jobs/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_job_requires_auth(client):
    resp = await client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401
