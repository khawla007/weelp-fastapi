"""Nominatim adapter — reverse happy path, health probe, mapper fallbacks."""

import httpx
import pytest
import respx

from gateway.adapters.nominatim.place_adapter import NominatimPlaceAdapter


@pytest.mark.asyncio
async def test_nominatim_reverse_returns_canonical():
    sample = {
        "place_id": 9001,
        "name": "Eiffel Tower",
        "display_name": "Eiffel Tower, Paris, France",
        "lat": "48.8584",
        "lon": "2.2945",
        "address": {"country_code": "fr"},
    }
    async with httpx.AsyncClient() as client:
        adapter = NominatimPlaceAdapter(
            client,
            base_url="https://nominatim.openstreetmap.org",
            api_key="",
            default_headers={"User-Agent": "weelp-gateway-test/0.1"},
        )
        with respx.mock(base_url="https://nominatim.openstreetmap.org") as mock:
            mock.get("/reverse").mock(return_value=httpx.Response(200, json=sample))
            out = await adapter.reverse(48.8584, 2.2945)
    assert out is not None
    assert out.id == "9001"
    assert out.country_code == "FR"


@pytest.mark.asyncio
async def test_nominatim_reverse_returns_none_on_empty_array():
    async with httpx.AsyncClient() as client:
        adapter = NominatimPlaceAdapter(
            client,
            base_url="https://nominatim.openstreetmap.org",
            api_key="",
            default_headers={"User-Agent": "weelp-gateway-test/0.1"},
        )
        with respx.mock(base_url="https://nominatim.openstreetmap.org") as mock:
            mock.get("/reverse").mock(return_value=httpx.Response(200, json=[]))
            out = await adapter.reverse(0.0, 0.0)
    assert out is None


@pytest.mark.asyncio
async def test_nominatim_health_ok_on_2xx():
    async with httpx.AsyncClient() as client:
        adapter = NominatimPlaceAdapter(
            client,
            base_url="https://nominatim.openstreetmap.org",
            api_key="",
            default_headers={"User-Agent": "weelp-gateway-test/0.1"},
        )
        with respx.mock(base_url="https://nominatim.openstreetmap.org") as mock:
            mock.head("").mock(return_value=httpx.Response(200))
            await adapter.health()


@pytest.mark.asyncio
async def test_nominatim_health_raises_on_5xx():
    async with httpx.AsyncClient() as client:
        adapter = NominatimPlaceAdapter(
            client,
            base_url="https://nominatim.openstreetmap.org",
            api_key="",
            default_headers={"User-Agent": "weelp-gateway-test/0.1"},
        )
        with respx.mock(base_url="https://nominatim.openstreetmap.org") as mock:
            mock.head("").mock(return_value=httpx.Response(502))
            with pytest.raises(RuntimeError, match="502"):
                await adapter.health()


def test_nominatim_canonical_falls_back_to_display_name_when_name_missing():
    row = {
        "display_name": "Some Place, Earth",
        "lat": "0.0",
        "lon": "0.0",
        "osm_id": 12,
    }
    place = NominatimPlaceAdapter._to_canonical(row)
    assert place.id == "12"
    assert place.name == "Some Place, Earth"
    assert place.country_code == "ZZ"


def test_nominatim_canonical_uses_display_name_as_id_when_no_ids():
    row = {
        "display_name": "Anonymous Spot",
        "lat": "1.0",
        "lon": "2.0",
    }
    place = NominatimPlaceAdapter._to_canonical(row)
    assert place.id == "Anonymous Spot"
    assert place.lat == 1.0
    assert place.lng == 2.0
