"""Cover the tenacity retry-exhaustion path on `BaseHttpAdapter._do_get`.

`_do_get` retries `httpx.TransportError` and `httpx.HTTPStatusError` up to three
attempts. Once tenacity's `stop_after_attempt` is hit, the original exception
propagates (`reraise=True`). The unit confirms that contract end-to-end without
any network mocks installed at the route layer.
"""

import httpx
import pytest
import respx

from gateway.adapters.base import reset_breaker_factory
from gateway.adapters.mapbox.place_adapter import MapboxPlaceAdapter


@pytest.mark.asyncio
async def test_do_get_retries_then_reraises_on_persistent_transport_error():
    reset_breaker_factory()
    async with httpx.AsyncClient() as client:
        adapter = MapboxPlaceAdapter(client, base_url="https://api.mapbox.com", api_key="x")
        with respx.mock(base_url="https://api.mapbox.com") as mock:
            route = mock.get("/geocoding/v5/mapbox.places/boom.json").mock(
                side_effect=httpx.ConnectTimeout("boom")
            )
            with pytest.raises(httpx.TransportError):
                await adapter.geocode("boom")
            assert route.call_count == 3
    reset_breaker_factory()


@pytest.mark.asyncio
async def test_do_get_retries_on_5xx_then_reraises_http_status_error():
    reset_breaker_factory()
    async with httpx.AsyncClient() as client:
        adapter = MapboxPlaceAdapter(client, base_url="https://api.mapbox.com", api_key="x")
        with respx.mock(base_url="https://api.mapbox.com") as mock:
            route = mock.get("/geocoding/v5/mapbox.places/down.json").mock(
                return_value=httpx.Response(502)
            )
            with pytest.raises(httpx.HTTPStatusError):
                await adapter.geocode("down")
            assert route.call_count == 3
    reset_breaker_factory()
