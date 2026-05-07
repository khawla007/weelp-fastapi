"""Shared JWT minting helpers — single source of truth for the test secret/algo."""

from __future__ import annotations

import time

import jwt

SECRET = "test-jwt-secret-do-not-use-in-prod"
ALGORITHM = "HS256"


def sign(payload: dict, secret: str = SECRET, algorithm: str = ALGORITHM) -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)


def valid_token(sub: str = "user-1", ttl: int = 60) -> str:
    now = int(time.time())
    return sign({"sub": sub, "iat": now, "exp": now + ttl})
