import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_request_id_header_is_echoed_when_provided(app_with_fake_redis):
    with TestClient(app_with_fake_redis) as client:
        response = client.get("/v1/health", headers={"X-Request-Id": "test-id-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "test-id-123"


@pytest.mark.asyncio
async def test_request_id_generated_when_missing(app_with_fake_redis):
    with TestClient(app_with_fake_redis) as client:
        response = client.get("/v1/health")
    assert response.status_code == 200
    request_id = response.headers.get("X-Request-Id")
    assert request_id is not None
    assert len(request_id) >= 16


@pytest.mark.asyncio
async def test_request_id_rejects_spoofed_value(app_with_fake_redis):
    # Too short, contains slash, or contains spaces — minted instead of trusted.
    bad_values = ["short", "has spaces", "x" * 65, "ok/with/slash", "<script>"]
    with TestClient(app_with_fake_redis) as client:
        for bad in bad_values:
            response = client.get("/v1/health", headers={"X-Request-Id": bad})
            assert response.status_code == 200
            echoed = response.headers["X-Request-Id"]
            assert echoed != bad
            assert len(echoed) >= 16
