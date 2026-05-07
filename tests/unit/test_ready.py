"""Readiness probe tests — /v1/ready must reflect Redis + provider health."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_ready_ok(app_with_fake_redis, monkeypatch):
    """All dependencies green → 200 with status=ready."""
    from gateway.adapters.mapbox.place_adapter import MapboxPlaceAdapter
    from gateway.adapters.nominatim.place_adapter import NominatimPlaceAdapter

    async def ok(self):
        return None

    monkeypatch.setattr(MapboxPlaceAdapter, "health", ok)
    monkeypatch.setattr(NominatimPlaceAdapter, "health", ok)

    with TestClient(app_with_fake_redis) as client:
        r = client.get("/v1/ready")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["redis"] == "ok"
    assert body["checks"]["mapbox"] == "ok"
    assert body["checks"]["nominatim"] == "ok"


@pytest.mark.asyncio
async def test_ready_redis_down(monkeypatch):
    """Redis ping raising → 503 with checks.redis=error:..."""
    import redis.asyncio

    from gateway.adapters import base as base_module
    from gateway.adapters.mapbox.place_adapter import MapboxPlaceAdapter
    from gateway.adapters.nominatim.place_adapter import NominatimPlaceAdapter

    base_module.reset_breaker_factory()

    class BrokenRedis:
        async def ping(self):
            raise redis.exceptions.ConnectionError("down")

        async def aclose(self):
            return None

    monkeypatch.setattr(redis.asyncio, "from_url", lambda *a, **kw: BrokenRedis())

    async def ok(self):
        return None

    monkeypatch.setattr(MapboxPlaceAdapter, "health", ok)
    monkeypatch.setattr(NominatimPlaceAdapter, "health", ok)

    from gateway.main import app

    with TestClient(app) as client:
        r = client.get("/v1/ready")

    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"].startswith("error:")
    assert body["checks"]["mapbox"] == "ok"
    base_module.reset_breaker_factory()


@pytest.mark.asyncio
async def test_ready_provider_down(app_with_fake_redis, monkeypatch):
    """Provider health raising → 503 with that provider in error state."""
    from gateway.adapters.mapbox.place_adapter import MapboxPlaceAdapter
    from gateway.adapters.nominatim.place_adapter import NominatimPlaceAdapter

    async def ok(self):
        return None

    async def boom(self):
        raise RuntimeError("upstream returned 503")

    monkeypatch.setattr(MapboxPlaceAdapter, "health", boom)
    monkeypatch.setattr(NominatimPlaceAdapter, "health", ok)

    with TestClient(app_with_fake_redis) as client:
        r = client.get("/v1/ready")

    assert r.status_code == 503
    body = r.json()
    assert body["checks"]["redis"] == "ok"
    assert body["checks"]["mapbox"].startswith("error:")
    assert body["checks"]["nominatim"] == "ok"


def test_health_unaffected(app_with_fake_redis):
    """/v1/health stays a binary liveness signal."""
    with TestClient(app_with_fake_redis) as client:
        r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
