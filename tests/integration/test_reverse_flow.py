"""End-to-end reverse flow — happy, validation, breaker, and generic-error paths."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway.adapters.base import CircuitOpenError
from tests.integration.conftest import make_place


@pytest.mark.asyncio
async def test_reverse_happy_path_returns_canonical_body(
    app_with_fake_provider, fake_provider
):
    fake_provider.reverse_result = make_place(id="fake-r", name="Marseille")
    with TestClient(app_with_fake_provider) as client:
        r = client.get(
            "/v1/places/reverse",
            params={"lat": 43.29, "lng": 5.37, "provider": "fake"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "fake-r"
    assert body["name"] == "Marseille"
    assert fake_provider.reverse_calls == [(43.29, 5.37)]


@pytest.mark.asyncio
async def test_reverse_returns_null_when_provider_returns_none(
    app_with_fake_provider, fake_provider
):
    fake_provider.reverse_result = None
    with TestClient(app_with_fake_provider) as client:
        r = client.get(
            "/v1/places/reverse",
            params={"lat": 0.0, "lng": 0.0, "provider": "fake"},
        )
    assert r.status_code == 200
    assert r.json() is None


@pytest.mark.asyncio
async def test_reverse_out_of_range_lat_returns_422(app_with_fake_provider):
    with TestClient(app_with_fake_provider) as client:
        r = client.get(
            "/v1/places/reverse",
            params={"lat": 999.0, "lng": 0.0, "provider": "fake"},
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_reverse_circuit_open_returns_503(app_with_fake_provider, fake_provider):
    fake_provider.reverse_result = CircuitOpenError("breaker open")
    with TestClient(app_with_fake_provider) as client:
        r = client.get(
            "/v1/places/reverse",
            params={"lat": 1.0, "lng": 2.0, "provider": "fake"},
        )
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_reverse_generic_error_returns_502(app_with_fake_provider, fake_provider):
    fake_provider.reverse_result = RuntimeError("boom")
    with TestClient(app_with_fake_provider) as client:
        r = client.get(
            "/v1/places/reverse",
            params={"lat": 1.0, "lng": 2.0, "provider": "fake"},
        )
    assert r.status_code == 502
