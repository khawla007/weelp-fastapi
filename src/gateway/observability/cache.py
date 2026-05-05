import functools
import hashlib
import json
import time
from typing import Any, Awaitable, Callable

import redis.asyncio as aioredis
import redis.exceptions
import structlog
from fastapi import FastAPI, Request

from gateway.config import settings
from gateway.observability.logging import logger

CACHE_PREFIX = "weelp-gw:cache"


async def init_cache(app: FastAPI) -> None:
    client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        await client.ping()
        logger.info("cache.connected", redis_url=settings.redis_url)
    except redis.exceptions.RedisError as exc:
        logger.warning(
            "cache.unavailable_at_startup",
            redis_url=settings.redis_url,
            error=type(exc).__name__,
        )
    app.state.redis = client


async def shutdown_cache(app: FastAPI) -> None:
    client: aioredis.Redis | None = getattr(app.state, "redis", None)
    if client is not None:
        try:
            await client.aclose()
        except Exception:
            pass


def _build_key(namespace: str, request: Request) -> str:
    provider = request.query_params.get("provider", "mapbox")
    params = sorted(
        (k, v) for k, v in request.query_params.multi_items() if k != "provider"
    )
    payload = json.dumps(
        {"path": request.url.path, "params": params},
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()[:24]
    return f"{CACHE_PREFIX}:{namespace}:{provider}:{digest}"


def cached(namespace: str, ttl: int | None = None) -> Callable:
    """Route-level cache decorator. Fail-soft when Redis is unavailable."""

    expire = ttl if ttl is not None else settings.cache_ttl_seconds

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request | None = kwargs.get("request")
            if request is None:
                return await func(*args, **kwargs)

            redis_client: aioredis.Redis | None = getattr(
                request.app.state, "redis", None
            )
            if redis_client is None:
                return await func(*args, **kwargs)

            key = _build_key(namespace, request)
            t0 = time.perf_counter()

            try:
                cached_value = await redis_client.get(key)
            except redis.exceptions.RedisError as exc:
                logger.warning(
                    "cache.unavailable",
                    op="get",
                    error=type(exc).__name__,
                )
                return await func(*args, **kwargs)

            if cached_value is not None:
                latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                logger.info(
                    "cache.hit",
                    namespace=namespace,
                    provider=request.query_params.get("provider", "mapbox"),
                    path=request.url.path,
                    latency_ms=latency_ms,
                    cache_hit=True,
                )
                structlog.contextvars.bind_contextvars(cache_hit=True)
                return json.loads(cached_value)

            structlog.contextvars.bind_contextvars(cache_hit=False)
            result = await func(*args, **kwargs)

            try:
                serialized = json.dumps(result, default=_json_default)
                await redis_client.set(key, serialized, ex=expire)
            except (redis.exceptions.RedisError, TypeError) as exc:
                logger.warning(
                    "cache.set_failed",
                    op="set",
                    error=type(exc).__name__,
                )

            return result

        return wrapper

    return decorator


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"Type {type(obj).__name__} is not JSON serializable")
