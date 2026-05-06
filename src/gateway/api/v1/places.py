from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from gateway.adapters.base import CircuitOpenError
from gateway.application.ports.place_provider import PlaceProvider
from gateway.domain.places import CanonicalPlace
from gateway.infrastructure.auth.jwt import optional_jwt
from gateway.infrastructure.deps import get_place_provider
from gateway.observability.cache import cached
from gateway.observability.limiter import limiter, rate_limit_for

router = APIRouter(prefix="/v1/places", tags=["places"])


@router.get("/geocode", response_model=list[CanonicalPlace])
@limiter.limit(rate_limit_for)
@cached(namespace="geocode")
async def geocode(
    request: Request,
    q: str = Query(..., min_length=2, description="Free-text place query"),
    limit: int = Query(5, ge=1, le=20),
    svc: PlaceProvider = Depends(get_place_provider),
    _user: dict | None = Depends(optional_jwt),
) -> list[CanonicalPlace]:
    try:
        return await svc.geocode(q, limit=limit)
    except HTTPException:
        raise
    except CircuitOpenError as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Provider unavailable: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Provider error: {e}") from e


@router.get("/reverse", response_model=CanonicalPlace | None)
@limiter.limit(rate_limit_for)
@cached(namespace="reverse")
async def reverse(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    svc: PlaceProvider = Depends(get_place_provider),
    _user: dict | None = Depends(optional_jwt),
) -> CanonicalPlace | None:
    try:
        return await svc.reverse(lat, lng)
    except HTTPException:
        raise
    except CircuitOpenError as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Provider unavailable: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Provider error: {e}") from e
