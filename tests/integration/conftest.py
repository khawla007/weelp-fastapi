"""Integration-test fixtures.

Builds on the unit-level `app_with_fake_redis` fixture from tests/conftest.py:
the Redis swap, limiter reset, and breaker reset all stay reused. The piece
this file adds is a `FakePlaceProvider` that satisfies the `PlaceProvider`
port and lets each test program canned canonical results without touching the
upstream HTTP layer.

A hand-rolled subclass is preferred over `AsyncMock(spec=PlaceProvider)`
because it survives a port-method addition without silently passing — the
abstract base will fail to instantiate if a method is added and the fake
hasn't followed.
"""

from __future__ import annotations

import pytest

from gateway.adapters.base import CircuitOpenError
from gateway.application.ports.place_provider import PlaceProvider
from gateway.domain.places import CanonicalPlace
from gateway.infrastructure.deps import get_place_provider


class FakePlaceProvider(PlaceProvider):
    name = "fake"

    def __init__(self) -> None:
        self.geocode_result: list[CanonicalPlace] | Exception = []
        self.reverse_result: CanonicalPlace | None | Exception = None
        self.geocode_calls: list[tuple[str, int]] = []
        self.reverse_calls: list[tuple[float, float]] = []

    async def geocode(self, query: str, *, limit: int = 5) -> list[CanonicalPlace]:
        self.geocode_calls.append((query, limit))
        if isinstance(self.geocode_result, Exception):
            raise self.geocode_result
        return self.geocode_result

    async def reverse(self, lat: float, lng: float) -> CanonicalPlace | None:
        self.reverse_calls.append((lat, lng))
        if isinstance(self.reverse_result, Exception):
            raise self.reverse_result
        return self.reverse_result


@pytest.fixture
def fake_provider() -> FakePlaceProvider:
    return FakePlaceProvider()


@pytest.fixture
async def app_with_fake_provider(app_with_fake_redis, fake_provider):
    """Wires `get_place_provider` to the FakePlaceProvider for the test's lifetime."""
    app_with_fake_redis.dependency_overrides[get_place_provider] = lambda: fake_provider
    yield app_with_fake_redis
    app_with_fake_redis.dependency_overrides.pop(get_place_provider, None)


@pytest.fixture
def circuit_open_error() -> CircuitOpenError:
    return CircuitOpenError("breaker open for fake")


def make_place(
    *,
    id: str = "fake-1",
    name: str = "Fakeville",
    country_code: str = "FR",
    lat: float = 1.0,
    lng: float = 2.0,
) -> CanonicalPlace:
    return CanonicalPlace(
        id=id,
        name=name,
        country_code=country_code,
        lat=lat,
        lng=lng,
        provider="fake",
    )
