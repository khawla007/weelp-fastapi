import os

import pytest

os.environ.setdefault("MAPBOX_TOKEN", "test-token")
os.environ.setdefault("NOMINATIM_USER_AGENT", "weelp-gateway-test/0.1 (test@example.com)")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")
os.environ.setdefault("RATE_LIMIT_PER_MIN", "60")
os.environ.setdefault("CIRCUIT_BREAKER_THRESHOLD", "3")
os.environ.setdefault("CIRCUIT_BREAKER_TTL_SECONDS", "1")


@pytest.fixture
def fake_redis():
    import fakeredis.aioredis

    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
async def app_with_fake_redis(monkeypatch, fake_redis):
    """Build the FastAPI app with Redis swapped for fakeredis. Resets state between tests."""
    import redis.asyncio

    from gateway.adapters import base as base_module

    base_module.reset_breaker_factory()

    monkeypatch.setattr(redis.asyncio, "from_url", lambda *a, **kw: fake_redis)

    from gateway.main import app

    yield app

    base_module.reset_breaker_factory()
    try:
        await fake_redis.aclose()
    except Exception:
        pass
