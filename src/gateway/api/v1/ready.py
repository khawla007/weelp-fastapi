"""Readiness probe — distinct from `/v1/health`.

`/v1/health` answers "process is up". `/v1/ready` answers "process can serve":
Redis is reachable and every registered place provider answers a cheap probe.
A 503 here drains the gateway from upstream rotation cleanly.
"""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gateway.adapters.factory import factory
from gateway.application.ports.place_provider import PlaceProvider

router = APIRouter(prefix="/v1", tags=["health"])

_REDIS_PING_TIMEOUT_S = 0.5
_PROVIDER_HEALTH_TIMEOUT_S = 2.0


async def _check_redis(request: Request) -> str:
    client = getattr(request.app.state, "redis", None)
    if client is None:
        return "error: not_initialized"
    try:
        await asyncio.wait_for(client.ping(), timeout=_REDIS_PING_TIMEOUT_S)
    except asyncio.TimeoutError:
        return "error: timeout"
    except Exception as exc:
        return f"error: {type(exc).__name__}"
    return "ok"


async def _check_provider(instance: PlaceProvider) -> str:
    try:
        await asyncio.wait_for(instance.health(), timeout=_PROVIDER_HEALTH_TIMEOUT_S)
    except asyncio.TimeoutError:
        return "error: timeout"
    except Exception as exc:
        return f"error: {type(exc).__name__}"
    return "ok"


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    checks: dict[str, str] = {"redis": await _check_redis(request)}
    for name, instance in factory.all_for(PlaceProvider):
        checks[name] = await _check_provider(instance)

    failing = [k for k, v in checks.items() if v != "ok"]
    return JSONResponse(
        status_code=503 if failing else 200,
        content={
            "status": "degraded" if failing else "ready",
            "checks": checks,
        },
    )
