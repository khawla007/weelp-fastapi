from fastapi import HTTPException, Query, status

from gateway.adapters.factory import factory
from gateway.application.ports.place_provider import PlaceProvider


def get_place_provider(provider: str = Query("mapbox")) -> PlaceProvider:
    try:
        return factory.get(PlaceProvider, provider)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
