import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_requires_auth(client: AsyncClient):
    files = {"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")}
    resp = await client.post("/api/documents", files=files)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_txt_document_returns_202_and_enqueues_job(
    client: AsyncClient, auth_headers: dict, fake_arq_pool
):
    files = {"file": ("notes.txt", io.BytesIO(b"database optimization and caching"), "text/plain")}
    resp = await client.post("/api/documents", files=files, headers=auth_headers)

    assert resp.status_code == 202
    body = resp.json()
    assert body["document"]["status"] == "UPLOADED"
    assert body["message"] == "Upload successful"
    assert body["job_id"]

    assert len(fake_arq_pool.enqueued) == 1
    function_name, args = fake_arq_pool.enqueued[0]
    assert function_name == "process_document_task"
    assert args[0] == body["document"]["id"]


@pytest.mark.asyncio
async def test_upload_rejects_disallowed_extension(client: AsyncClient, auth_headers: dict):
    files = {"file": ("malware.exe", io.BytesIO(b"MZ..."), "application/octet-stream")}
    resp = await client.post("/api/documents", files=files, headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_spoofed_pdf(client: AsyncClient, auth_headers: dict):
    files = {"file": ("fake.pdf", io.BytesIO(b"not really a pdf"), "application/pdf")}
    resp = await client.post("/api/documents", files=files, headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_documents_pagination(client: AsyncClient, auth_headers: dict):
    for i in range(3):
        files = {"file": (f"doc{i}.txt", io.BytesIO(b"some content here"), "text/plain")}
        await client.post("/api/documents", files=files, headers=auth_headers)

    resp = await client.get("/api/documents?page=1&page_size=2", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_get_document_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get(
        "/api/documents/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_document_owned_by_other_user_is_hidden(client: AsyncClient):
    email_a = "owner-a@example.com"
    email_b = "owner-b@example.com"
    await client.post("/api/auth/register", json={"email": email_a, "password": "supersecret123"})
    login_a = await client.post(
        "/api/auth/login", json={"email": email_a, "password": "supersecret123"}
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    files = {"file": ("private.txt", io.BytesIO(b"secret content"), "text/plain")}
    upload = await client.post("/api/documents", files=files, headers=headers_a)
    document_id = upload.json()["document"]["id"]

    await client.post("/api/auth/register", json={"email": email_b, "password": "supersecret123"})
    login_b = await client.post(
        "/api/auth/login", json={"email": email_b, "password": "supersecret123"}
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    resp = await client.get(f"/api/documents/{document_id}", headers=headers_b)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_document(client: AsyncClient, auth_headers: dict):
    files = {"file": ("todelete.txt", io.BytesIO(b"content to delete"), "text/plain")}
    upload = await client.post("/api/documents", files=files, headers=auth_headers)
    document_id = upload.json()["document"]["id"]

    resp = await client.delete(f"/api/documents/{document_id}", headers=auth_headers)
    assert resp.status_code == 204

    follow_up = await client.get(f"/api/documents/{document_id}", headers=auth_headers)
    assert follow_up.status_code == 404
