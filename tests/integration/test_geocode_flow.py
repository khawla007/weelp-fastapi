"""End-to-end geocode flow with `app.dependency_overrides`.

The unit tests prove each adapter normalizes its provider's payload. These
integration tests prove the route stack — limiter key resolution, the cache
decorator, optional JWT decode, and provider injection — wires together in the
right order. Upstream HTTP is replaced via `dependency_overrides`; respx is
intentionally absent because the layer being tested doesn't touch the network.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway.adapters.base import CircuitOpenError
from tests._helpers.auth import valid_token
from tests.integration.conftest import make_place


@pytest.mark.asyncio
async def test_geocode_happy_path_returns_canonical_body(
    app_with_fake_provider, fake_provider
):
    fake_provider.geocode_result = [make_place(id="fake-1", name="Paris", country_code="FR")]
    with TestClient(app_with_fake_provider) as client:
        r = client.get("/v1/places/geocode", params={"q": "paris", "provider": "fake"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == "fake-1"
    assert body[0]["country_code"] == "FR"
    assert fake_provider.geocode_calls == [("paris", 5)]


@pytest.mark.asyncio
async def test_geocode_short_query_returns_422(app_with_fake_provider):
    with TestClient(app_with_fake_provider) as client:
        r = client.get("/v1/places/geocode", params={"q": "a", "provider": "fake"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_geocode_circuit_open_returns_503(app_with_fake_provider, fake_provider):
    fake_provider.geocode_result = CircuitOpenError("breaker open for fake")
    with TestClient(app_with_fake_provider) as client:
        r = client.get("/v1/places/geocode", params={"q": "paris", "provider": "fake"})
    assert r.status_code == 503
    assert "Provider unavailable" in r.json()["detail"]


@pytest.mark.asyncio
async def test_geocode_generic_upstream_error_returns_502(
    app_with_fake_provider, fake_provider
):
    fake_provider.geocode_result = RuntimeError("upstream exploded")
    with TestClient(app_with_fake_provider) as client:
        r = client.get("/v1/places/geocode", params={"q": "paris", "provider": "fake"})
    assert r.status_code == 502
    assert "Provider error" in r.json()["detail"]


@pytest.mark.asyncio
async def test_geocode_bearer_token_lands_in_user_rate_tier(
    monkeypatch, app_with_fake_provider, fake_provider
):
    """Auth tier 2/min, anon tier 1/min — bearer caller hits 200,200,429
    (proving the limiter resolved `user:<sub>`, not `ip:<addr>`)."""
    monkeypatch.setattr("gateway.config.settings.rate_limit_per_min", 1)
    monkeypatch.setattr("gateway.config.settings.rate_limit_per_min_auth", 2)

    fake_provider.geocode_result = [make_place()]
    token = valid_token(sub="bearer-tier-user")

    with TestClient(app_with_fake_provider) as client:
        statuses = [
            client.get(
                "/v1/places/geocode",
                params={"q": "paris", "provider": "fake", "_n": i},
                headers={"Authorization": f"Bearer {token}"},
            ).status_code
            for i in range(3)
        ]

    assert statuses == [200, 200, 429], statuses
