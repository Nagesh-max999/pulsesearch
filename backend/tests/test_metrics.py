import pytest

pytestmark = pytest.mark.asyncio


async def test_metrics_endpoint_exposes_prometheus_format(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "# HELP" in resp.text


async def test_metrics_endpoint_is_not_itself_counted(client):
    await client.get("/metrics")
    resp = await client.get("/metrics")
    assert '/metrics' not in _extract_http_requests_paths(resp.text)


async def test_search_request_increments_search_metric(client, auth_headers):
    await client.get("/api/search", params={"q": "test", "mode": "KEYWORD"}, headers=auth_headers)

    resp = await client.get("/metrics")
    assert 'search_requests_total{mode="KEYWORD"}' in resp.text


def _extract_http_requests_paths(body: str) -> set[str]:
    paths = set()
    for line in body.splitlines():
        if line.startswith("http_requests_total{") and 'path="/metrics"' in line:
            paths.add("/metrics")
    return paths
