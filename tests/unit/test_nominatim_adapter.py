import httpx
import pytest
import respx

from gateway.adapters.nominatim.place_adapter import NominatimPlaceAdapter


@pytest.mark.asyncio
async def test_nominatim_geocode_normalizes_to_canonical():
    sample = [
        {
            "place_id": 12345,
            "osm_id": 7444,
            "name": "Paris",
            "display_name": "Paris, Île-de-France, France",
            "lat": "48.8566969",
            "lon": "2.3514616",
            "address": {
                "country": "France",
                "country_code": "fr",
            },
        }
    ]
    async with httpx.AsyncClient() as client:
        adapter = NominatimPlaceAdapter(
            client,
            base_url="https://nominatim.openstreetmap.org",
            api_key="",
            default_headers={"User-Agent": "weelp-gateway-test/0.1"},
        )
        with respx.mock(base_url="https://nominatim.openstreetmap.org") as mock:
            mock.get("/search").mock(return_value=httpx.Response(200, json=sample))
            out = await adapter.geocode("paris", limit=1)

    assert len(out) == 1
    p = out[0]
    assert p.id == "12345"
    assert p.name == "Paris"
    assert p.country_code == "FR"
    assert p.lat == pytest.approx(48.8566969)
    assert p.lng == pytest.approx(2.3514616)
    assert p.provider == "nominatim"


@pytest.mark.asyncio
async def test_nominatim_reverse_returns_none_on_error():
    async with httpx.AsyncClient() as client:
        adapter = NominatimPlaceAdapter(
            client,
            base_url="https://nominatim.openstreetmap.org",
            api_key="",
            default_headers={"User-Agent": "weelp-gateway-test/0.1"},
        )
        with respx.mock(base_url="https://nominatim.openstreetmap.org") as mock:
            mock.get("/reverse").mock(
                return_value=httpx.Response(200, json={"error": "Unable to geocode"})
            )
            out = await adapter.reverse(0.0, 0.0)
    assert out is None
