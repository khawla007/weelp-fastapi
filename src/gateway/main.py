from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.adapters.factory import factory
from gateway.adapters.mapbox.place_adapter import MapboxPlaceAdapter
from gateway.adapters.nominatim.place_adapter import NominatimPlaceAdapter
from gateway.api.v1 import health, places
from gateway.application.ports.place_provider import PlaceProvider
from gateway.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = httpx.AsyncClient(timeout=10.0)
    factory.register(
        PlaceProvider,
        "mapbox",
        MapboxPlaceAdapter(client, base_url=settings.mapbox_base_url, api_key=settings.mapbox_token),
    )
    factory.register(
        PlaceProvider,
        "nominatim",
        NominatimPlaceAdapter(
            client,
            base_url=settings.nominatim_base_url,
            api_key="",
            default_headers={"User-Agent": settings.nominatim_user_agent},
        ),
    )
    app.state.http = client
    try:
        yield
    finally:
        await client.aclose()


app = FastAPI(title="Weelp Integration Gateway", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(places.router)
