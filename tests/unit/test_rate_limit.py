import httpx
import pytest
import respx
from fastapi.testclient import TestClient


SAMPLE = {
    "features": [
        {
            "id": "place.1",
            "text": "Berlin",
            "place_name": "Berlin, Germany",
            "center": [13.4, 52.5],
            "context": [{"id": "country.de", "short_code": "de", "text": "Germany"}],
        }
    ]
}


@pytest.mark.asyncio
async def test_rate_limit_returns_429_after_threshold(monkeypatch, app_with_fake_redis):
    monkeypatch.setattr("gateway.config.settings.rate_limit_per_min", 2)

    with TestClient(app_with_fake_redis) as client:
        with respx.mock(base_url="https://api.mapbox.com", assert_all_called=False) as mock:
            mock.get("/geocoding/v5/mapbox.places/berlin.json").mock(
                return_value=httpx.Response(200, json=SAMPLE)
            )

            statuses = []
            for i in range(4):
                r = client.get(
                    "/v1/places/geocode",
                    params={"q": "berlin", "provider": "mapbox", "_n": i},
                )
                statuses.append(r.status_code)

    assert 429 in statuses, f"Expected at least one 429, got {statuses}"
    assert statuses.count(200) >= 1
