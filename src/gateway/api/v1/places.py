from fastapi import APIRouter, Depends, HTTPException, Query, status

from gateway.application.ports.place_provider import PlaceProvider
from gateway.domain.places import CanonicalPlace
from gateway.infrastructure.deps import get_place_provider

router = APIRouter(prefix="/v1/places", tags=["places"])


@router.get("/geocode", response_model=list[CanonicalPlace])
async def geocode(
    q: str = Query(..., min_length=2, description="Free-text place query"),
    limit: int = Query(5, ge=1, le=20),
    svc: PlaceProvider = Depends(get_place_provider),
) -> list[CanonicalPlace]:
    try:
        return await svc.geocode(q, limit=limit)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Provider error: {e}") from e


@router.get("/reverse", response_model=CanonicalPlace | None)
async def reverse(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    svc: PlaceProvider = Depends(get_place_provider),
) -> CanonicalPlace | None:
    try:
        return await svc.reverse(lat, lng)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Provider error: {e}") from e
