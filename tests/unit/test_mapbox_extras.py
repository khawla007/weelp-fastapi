"""Mapbox adapter — reverse, health, and `_to_canonical` edge cases.

The happy-path normalization lives in `test_mapbox_adapter.py`. This file fills
the M6 gaps: the reverse coordinate path, the HEAD-based health probe (both ok
and degraded), and the canonical mapping when the upstream payload is missing
fields the mapper would normally lean on.
"""

import httpx
import pytest
import respx

from gateway.adapters.mapbox.place_adapter import MapboxPlaceAdapter


@pytest.mark.asyncio
async def test_mapbox_reverse_returns_first_feature():
    sample = {
        "features": [
            {
                "id": "place.99",
                "text": "Lyon",
                "place_name": "Lyon, France",
                "center": [4.83, 45.75],
                "context": [{"id": "country.fr", "short_code": "fr", "text": "France"}],
            }
        ]
    }
    async with httpx.AsyncClient() as client:
        adapter = MapboxPlaceAdapter(client, base_url="https://api.mapbox.com", api_key="x")
        with respx.mock(base_url="https://api.mapbox.com") as mock:
            mock.get("/geocoding/v5/mapbox.places/4.83,45.75.json").mock(
                return_value=httpx.Response(200, json=sample)
            )
            out = await adapter.reverse(45.75, 4.83)
    assert out is not None
    assert out.id == "place.99"
    assert out.country_code == "FR"


@pytest.mark.asyncio
async def test_mapbox_reverse_returns_none_when_no_features():
    async with httpx.AsyncClient() as client:
        adapter = MapboxPlaceAdapter(client, base_url="https://api.mapbox.com", api_key="x")
        with respx.mock(base_url="https://api.mapbox.com") as mock:
            mock.get("/geocoding/v5/mapbox.places/0.0,0.0.json").mock(
                return_value=httpx.Response(200, json={"features": []})
            )
            out = await adapter.reverse(0.0, 0.0)
    assert out is None


@pytest.mark.asyncio
async def test_mapbox_health_ok_on_2xx():
    async with httpx.AsyncClient() as client:
        adapter = MapboxPlaceAdapter(client, base_url="https://api.mapbox.com", api_key="x")
        with respx.mock(base_url="https://api.mapbox.com") as mock:
            mock.head("").mock(return_value=httpx.Response(200))
            await adapter.health()


@pytest.mark.asyncio
async def test_mapbox_health_raises_on_5xx():
    async with httpx.AsyncClient() as client:
        adapter = MapboxPlaceAdapter(client, base_url="https://api.mapbox.com", api_key="x")
        with respx.mock(base_url="https://api.mapbox.com") as mock:
            mock.head("").mock(return_value=httpx.Response(503))
            with pytest.raises(RuntimeError, match="503"):
                await adapter.health()


def test_mapbox_canonical_falls_back_to_zz_when_country_missing():
    feature = {
        "id": "place.7",
        "text": "Nowhere",
        "place_name": "Nowhere",
        "center": [0.0, 0.0],
        "context": [{"id": "region.x", "text": "X"}],
    }
    place = MapboxPlaceAdapter._to_canonical(feature)
    assert place.country_code == "ZZ"
    assert place.name == "Nowhere"


def test_mapbox_canonical_uses_place_name_when_text_missing():
    feature = {
        "id": "place.8",
        "place_name": "Fallback Name",
        "center": [10.0, 20.0],
    }
    place = MapboxPlaceAdapter._to_canonical(feature)
    assert place.name == "Fallback Name"
    assert place.country_code == "ZZ"
