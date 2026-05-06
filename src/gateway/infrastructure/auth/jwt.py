from __future__ import annotations

import jwt
from fastapi import HTTPException, Request, status

from gateway.config import settings
from gateway.observability.logging import logger


class _AuthError(Exception):
    def __init__(self, event: str, detail: str) -> None:
        self.event = event
        self.detail = detail
        super().__init__(detail)


def _extract_bearer(request: Request) -> str:
    header = request.headers.get("authorization")
    if not header:
        raise _AuthError("auth.missing", "missing authorization header")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise _AuthError("auth.malformed", "malformed authorization header")
    return parts[1]


def _decode(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as e:
        raise _AuthError("auth.expired", "token expired") from e
    except jwt.InvalidSignatureError as e:
        raise _AuthError("auth.signature_mismatch", "signature mismatch") from e
    except jwt.DecodeError as e:
        raise _AuthError("auth.decode_error", "decode error") from e
    except jwt.InvalidTokenError as e:
        raise _AuthError("auth.invalid", "invalid token") from e


def require_jwt(request: Request) -> dict:
    """Reject the request unless a valid bearer token is present.

    Sets ``request.state.user`` to the decoded payload on success.
    """
    try:
        token = _extract_bearer(request)
        payload = _decode(token)
    except _AuthError as e:
        logger.warning(e.event, detail=e.detail, path=request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.detail,
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    request.state.user = payload
    return payload


def optional_jwt(request: Request) -> dict | None:
    """Return the decoded payload when a valid bearer is present, ``None`` otherwise.

    Never raises. Sets ``request.state.user`` only on success so anonymous traffic
    leaves the attribute unset.
    """
    try:
        token = _extract_bearer(request)
        payload = _decode(token)
    except _AuthError as e:
        logger.debug(e.event, detail=e.detail, path=request.url.path)
        return None
    request.state.user = payload
    return payload
