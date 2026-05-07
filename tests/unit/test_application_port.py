"""Cover the default no-op `health()` on the PlaceProvider port.

Adapters opt into upstream probing by overriding `health()`. The base port keeps
a no-op so a provider that doesn't ship a probe still answers `/v1/ready`
quickly. The default body is one line — exercising it closes the M6 gap on the
application/ package.
"""

import pytest

from gateway.application.ports.place_provider import PlaceProvider
from gateway.domain.places import CanonicalPlace


class _MinimalProvider(PlaceProvider):
    name = "minimal"

    async def geocode(self, query: str, *, limit: int = 5) -> list[CanonicalPlace]:
        return []

    async def reverse(self, lat: float, lng: float) -> CanonicalPlace | None:
        return None


@pytest.mark.asyncio
async def test_default_health_is_no_op_returning_none():
    provider = _MinimalProvider()
    assert await provider.health() is None
