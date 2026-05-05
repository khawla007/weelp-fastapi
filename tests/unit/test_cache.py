import httpx
import pytest
import respx
from fastapi.testclient import TestClient


SAMPLE_MAPBOX_RESPONSE = {
    "features": [
        {
            "id": "place.42",
            "text": "Paris",
            "place_name": "Paris, France",
            "center": [2.35, 48.86],
            "context": [{"id": "country.fr", "short_code": "fr", "text": "France"}],
        }
    ]
}


@pytest.mark.asyncio
async def test_cache_hit_skips_upstream(app_with_fake_redis):
    with TestClient(app_with_fake_redis) as client:
        with respx.mock(base_url="https://api.mapbox.com", assert_all_called=False) as mock:
            route = mock.get("/geocoding/v5/mapbox.places/paris.json").mock(
                return_value=httpx.Response(200, json=SAMPLE_MAPBOX_RESPONSE)
            )

            r1 = client.get("/v1/places/geocode", params={"q": "paris", "provider": "mapbox"})
            assert r1.status_code == 200
            assert route.call_count == 1

            r2 = client.get("/v1/places/geocode", params={"q": "paris", "provider": "mapbox"})
            assert r2.status_code == 200
            assert route.call_count == 1


@pytest.mark.asyncio
async def test_cache_fail_soft_when_redis_down(monkeypatch):
    """If Redis raises on get/set, request must still 200 from upstream."""
    import redis.asyncio
    import redis.exceptions

    from gateway.adapters import base as base_module

    base_module.reset_breaker_factory()

    class BrokenRedis:
        async def ping(self):
            raise redis.exceptions.ConnectionError("down")

        async def get(self, *_):
            raise redis.exceptions.ConnectionError("down")

        async def set(self, *_, **__):
            raise redis.exceptions.ConnectionError("down")

        async def aclose(self):
            return None

    monkeypatch.setattr(redis.asyncio, "from_url", lambda *a, **kw: BrokenRedis())

    from gateway.main import app

    with TestClient(app) as client:
        with respx.mock(base_url="https://api.mapbox.com") as mock:
            mock.get("/geocoding/v5/mapbox.places/lyon.json").mock(
                return_value=httpx.Response(200, json=SAMPLE_MAPBOX_RESPONSE)
            )
            r = client.get("/v1/places/geocode", params={"q": "lyon", "provider": "mapbox"})
    assert r.status_code == 200
    base_module.reset_breaker_factory()
