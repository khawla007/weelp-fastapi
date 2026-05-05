import httpx
import pytest
import respx

from gateway.adapters.mapbox.place_adapter import MapboxPlaceAdapter


@pytest.mark.asyncio
async def test_mapbox_geocode_normalizes_to_canonical():
    sample = {
        "features": [
            {
                "id": "place.1",
                "text": "Marseille",
                "place_name": "Marseille, France",
                "center": [5.37, 43.29],
                "context": [
                    {"id": "country.123", "short_code": "fr", "text": "France"},
                ],
            }
        ]
    }
    async with httpx.AsyncClient() as client:
        adapter = MapboxPlaceAdapter(client, base_url="https://api.mapbox.com", api_key="x")
        with respx.mock(base_url="https://api.mapbox.com") as mock:
            mock.get("/geocoding/v5/mapbox.places/marseille.json").mock(
                return_value=httpx.Response(200, json=sample)
            )
            out = await adapter.geocode("marseille", limit=1)

    assert len(out) == 1
    p = out[0]
    assert p.id == "place.1"
    assert p.name == "Marseille"
    assert p.country_code == "FR"
    assert p.lat == 43.29
    assert p.lng == 5.37
    assert p.provider == "mapbox"


@pytest.mark.asyncio
async def test_mapbox_geocode_empty_features_returns_empty_list():
    async with httpx.AsyncClient() as client:
        adapter = MapboxPlaceAdapter(client, base_url="https://api.mapbox.com", api_key="x")
        with respx.mock(base_url="https://api.mapbox.com") as mock:
            mock.get("/geocoding/v5/mapbox.places/zzzzz.json").mock(
                return_value=httpx.Response(200, json={"features": []})
            )
            out = await adapter.geocode("zzzzz")
    assert out == []
