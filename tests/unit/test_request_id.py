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
