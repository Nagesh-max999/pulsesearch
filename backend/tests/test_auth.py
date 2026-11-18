import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_returns_token(client: AsyncClient):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": "supersecret123"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client: AsyncClient):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "supersecret123"}
    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_register_rejects_short_password(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register", json={"email": "short@example.com", "password": "123"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    password = "supersecret123"
    await client.post("/api/auth/register", json={"email": email, "password": password})

    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client: AsyncClient):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/api/auth/register", json={"email": email, "password": "supersecret123"})

    resp = await client.post("/api/auth/login", json={"email": email, "password": "wrongpass"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client: AsyncClient, auth_headers: dict, registered_user):
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == registered_user["email"]


@pytest.mark.asyncio
async def test_invalid_token_rejected(client: AsyncClient):
    resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
