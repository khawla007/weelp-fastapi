from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from gateway.config import settings


def _build_limiter() -> Limiter:
    storage_uri = settings.rate_limit_storage_uri or settings.redis_url
    try:
        return Limiter(
            key_func=get_remote_address,
            storage_uri=storage_uri,
            default_limits=[],
            swallow_errors=True,
        )
    except Exception:
        return Limiter(
            key_func=get_remote_address,
            default_limits=[],
            swallow_errors=True,
        )


limiter = _build_limiter()


def register_limiter(app: FastAPI, limiter_instance: Limiter) -> None:
    app.state.limiter = limiter_instance
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
