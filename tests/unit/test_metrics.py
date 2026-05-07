"""/metrics route + custom counter wiring."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient


SAMPLE_MAPBOX_RESPONSE = {
    "features": [
        {
            "id": "place.99",
            "text": "Lyon",
            "place_name": "Lyon, France",
            "center": [4.83, 45.76],
            "context": [{"id": "country.fr", "short_code": "fr"}],
        }
    ]
}


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus_format(app_with_fake_redis):
    with TestClient(app_with_fake_redis) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    body = r.text
    # Default histograms surface as soon as one request is recorded; the custom
    # series surface their HELP/TYPE preamble even before any sample.
    assert "gateway_cache_events_total" in body
    assert "gateway_circuit_breaker_state" in body


@pytest.mark.asyncio
async def test_cache_counter_increments_on_miss_then_hit(app_with_fake_redis):
    with TestClient(app_with_fake_redis) as client:
        with respx.mock(base_url="https://api.mapbox.com", assert_all_called=False) as mock:
            mock.get("/geocoding/v5/mapbox.places/lyon.json").mock(
                return_value=httpx.Response(200, json=SAMPLE_MAPBOX_RESPONSE)
            )
            client.get("/v1/places/geocode", params={"q": "lyon", "provider": "mapbox"})
            client.get("/v1/places/geocode", params={"q": "lyon", "provider": "mapbox"})

        r = client.get("/metrics")
    body = r.text
    # First request → miss; second → hit. Both labels must appear with samples ≥ 1.
    assert (
        'gateway_cache_events_total{event="miss",namespace="geocode",provider="mapbox"} 1.0'
        in body
    )
    assert (
        'gateway_cache_events_total{event="hit",namespace="geocode",provider="mapbox"} 1.0'
        in body
    )
