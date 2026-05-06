"""Per-user vs per-IP rate-limit tier verification."""

from __future__ import annotations

import time

import httpx
import jwt
import pytest
import respx
from fastapi.testclient import TestClient


SECRET = "test-jwt-secret-do-not-use-in-prod"

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


def _token(sub: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": sub, "iat": now, "exp": now + 60}, SECRET, algorithm="HS256")


@pytest.mark.asyncio
async def test_per_user_buckets_isolated_from_ip(monkeypatch, app_with_fake_redis):
    monkeypatch.setattr("gateway.config.settings.rate_limit_per_min", 2)
    monkeypatch.setattr("gateway.config.settings.rate_limit_per_min_auth", 2)

    user_a = _token("user-a")
    user_b = _token("user-b")

    with TestClient(app_with_fake_redis) as client:
        with respx.mock(base_url="https://api.mapbox.com", assert_all_called=False) as mock:
            mock.get("/geocoding/v5/mapbox.places/berlin.json").mock(
                return_value=httpx.Response(200, json=SAMPLE)
            )

            anon = [
                client.get("/v1/places/geocode", params={"q": "berlin", "_n": i}).status_code
                for i in range(3)
            ]
            a_statuses = [
                client.get(
                    "/v1/places/geocode",
                    params={"q": "berlin", "_n": i + 100},
                    headers={"Authorization": f"Bearer {user_a}"},
                ).status_code
                for i in range(3)
            ]
            b_statuses = [
                client.get(
                    "/v1/places/geocode",
                    params={"q": "berlin", "_n": i + 200},
                    headers={"Authorization": f"Bearer {user_b}"},
                ).status_code
                for i in range(2)
            ]

    assert anon.count(200) == 2 and anon.count(429) == 1, anon
    assert a_statuses.count(200) == 2 and a_statuses.count(429) == 1, a_statuses
    assert b_statuses == [200, 200], b_statuses
