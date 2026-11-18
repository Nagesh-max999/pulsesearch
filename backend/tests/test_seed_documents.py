import pytest

from app.core.config import get_settings
from app.services.seed_service import SEED_DOCUMENTS

pytestmark = pytest.mark.asyncio


async def test_registration_seeds_demo_documents(client, fake_arq_pool, monkeypatch):
    monkeypatch.setenv("SEED_DEMO_DOCUMENTS", "true")
    get_settings.cache_clear()
    try:
        resp = await client.post(
            "/api/auth/register",
            json={"email": "seeded@example.com", "password": "supersecret123"},
        )
        assert resp.status_code == 201
        token = resp.json()["access_token"]

        docs = await client.get(
            "/api/documents", headers={"Authorization": f"Bearer {token}"}
        )
        assert docs.status_code == 200
        body = docs.json()
        assert body["total"] == len(SEED_DOCUMENTS)
        titles = {item["title"] for item in body["items"]}
        assert titles == {name for name, _ in SEED_DOCUMENTS}

        assert len(fake_arq_pool.enqueued) == len(SEED_DOCUMENTS)
        for function_name, _args in fake_arq_pool.enqueued:
            assert function_name == "process_document_task"
    finally:
        monkeypatch.delenv("SEED_DEMO_DOCUMENTS", raising=False)
        get_settings.cache_clear()


async def test_registration_does_not_seed_when_disabled(client, fake_arq_pool):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "unseeded@example.com", "password": "supersecret123"},
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]

    docs = await client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert docs.json()["total"] == 0
    assert fake_arq_pool.enqueued == []
