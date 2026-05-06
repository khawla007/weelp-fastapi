"""Tests for the JWT auth bridge: require_jwt, optional_jwt, and the /v1/me stub."""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi.testclient import TestClient


SECRET = "test-jwt-secret-do-not-use-in-prod"


def _sign(payload: dict, secret: str = SECRET) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def _valid_token(sub: str = "user-1", ttl: int = 60) -> str:
    now = int(time.time())
    return _sign({"sub": sub, "iat": now, "exp": now + ttl})


# ---------- /v1/me — covers require_jwt's 401 paths and the success round-trip ----------


@pytest.mark.asyncio
async def test_me_missing_header_returns_401(app_with_fake_redis):
    with TestClient(app_with_fake_redis) as client:
        r = client.get("/v1/me")
    assert r.status_code == 401
    assert "missing" in r.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "header",
    ["Bearer", "Token abc.def.ghi", "Bearer ", "Basic zzz"],
)
async def test_me_malformed_header_returns_401(app_with_fake_redis, header):
    with TestClient(app_with_fake_redis) as client:
        r = client.get("/v1/me", headers={"Authorization": header})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_signature_mismatch_returns_401(app_with_fake_redis):
    bad = _sign({"sub": "user-1", "exp": int(time.time()) + 60}, secret="wrong-secret")
    with TestClient(app_with_fake_redis) as client:
        r = client.get("/v1/me", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401
    assert "signature mismatch" in r.json()["detail"]


@pytest.mark.asyncio
async def test_me_expired_token_returns_401(app_with_fake_redis):
    expired = _sign({"sub": "user-1", "exp": int(time.time()) - 10})
    with TestClient(app_with_fake_redis) as client:
        r = client.get("/v1/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401
    assert "expired" in r.json()["detail"]


@pytest.mark.asyncio
async def test_me_valid_token_round_trip(app_with_fake_redis):
    token = _valid_token(sub="user-42")
    with TestClient(app_with_fake_redis) as client:
        r = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["sub"] == "user-42"
    assert "exp" in body and "iat" in body


# ---------- optional_jwt — must never raise; returns None on every failure mode ----------


def test_optional_jwt_returns_none_on_missing():
    from unittest.mock import MagicMock

    from gateway.infrastructure.auth.jwt import optional_jwt

    request = MagicMock()
    request.headers = {}
    request.url.path = "/v1/places/geocode"
    request.state = MagicMock(spec=[])
    assert optional_jwt(request) is None


def test_optional_jwt_returns_none_on_malformed():
    from unittest.mock import MagicMock

    from gateway.infrastructure.auth.jwt import optional_jwt

    request = MagicMock()
    request.headers = {"authorization": "garbage"}
    request.url.path = "/v1/places/geocode"
    request.state = MagicMock(spec=[])
    assert optional_jwt(request) is None


def test_optional_jwt_returns_none_on_expired():
    from unittest.mock import MagicMock

    from gateway.infrastructure.auth.jwt import optional_jwt

    expired = _sign({"sub": "user-1", "exp": int(time.time()) - 10})
    request = MagicMock()
    request.headers = {"authorization": f"Bearer {expired}"}
    request.url.path = "/v1/places/geocode"
    request.state = MagicMock(spec=[])
    assert optional_jwt(request) is None


def test_optional_jwt_returns_payload_on_valid():
    from unittest.mock import MagicMock

    from gateway.infrastructure.auth.jwt import optional_jwt

    token = _valid_token(sub="user-7")
    request = MagicMock()
    request.headers = {"authorization": f"Bearer {token}"}
    request.url.path = "/v1/places/geocode"
    request.state = MagicMock()
    payload = optional_jwt(request)
    assert payload is not None
    assert payload["sub"] == "user-7"
