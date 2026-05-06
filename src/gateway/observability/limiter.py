from fastapi import FastAPI
from starlette.requests import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from gateway.config import settings
from gateway.infrastructure.auth.jwt import _decode, _extract_bearer, _AuthError


def key_for(request: Request) -> str:
    """Hybrid limiter key: ``user:<sub>`` for valid bearer tokens, ``ip:<addr>`` otherwise.

    Reads the ``Authorization`` header directly so the key is stable regardless
    of FastAPI dependency vs middleware ordering. Failures fall back to IP and
    never raise.
    """
    try:
        token = _extract_bearer(request)
        payload = _decode(token)
        sub = payload.get("sub")
        if sub:
            return f"user:{sub}"
    except _AuthError:
        pass
    except Exception:
        pass
    return f"ip:{get_remote_address(request)}"


def rate_limit_for(key: str) -> str:
    """Pick the per-minute ceiling from the limiter key prefix.

    ``key_for`` emits ``user:<sub>`` for authenticated callers and ``ip:<addr>``
    otherwise — slowapi passes that key into the limit provider so we can tier
    without re-reading the request.
    """
    ceiling = (
        settings.rate_limit_per_min_auth
        if key.startswith("user:")
        else settings.rate_limit_per_min
    )
    return f"{ceiling}/minute"


def _build_limiter() -> Limiter:
    storage_uri = settings.rate_limit_storage_uri or settings.redis_url
    try:
        return Limiter(
            key_func=key_for,
            storage_uri=storage_uri,
            default_limits=[],
            swallow_errors=True,
        )
    except Exception:
        return Limiter(
            key_func=key_for,
            default_limits=[],
            swallow_errors=True,
        )


limiter = _build_limiter()


def register_limiter(app: FastAPI, limiter_instance: Limiter) -> None:
    app.state.limiter = limiter_instance
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
