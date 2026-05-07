from gateway.adapters.base import BaseHttpAdapter
from gateway.application.ports.place_provider import PlaceProvider
from gateway.domain.places import CanonicalPlace


class MapboxPlaceAdapter(BaseHttpAdapter, PlaceProvider):
    name = "mapbox"

    async def geocode(self, query: str, *, limit: int = 5) -> list[CanonicalPlace]:
        data = await self._get(
            f"/geocoding/v5/mapbox.places/{query}.json",
            access_token=self._api_key,
            limit=limit,
        )
        return [self._to_canonical(f) for f in data.get("features", [])]

    async def health(self) -> None:
        r = await self._client.head(self._base_url, timeout=2.0)
        if r.status_code >= 500:
            raise RuntimeError(f"upstream returned {r.status_code}")

    async def reverse(self, lat: float, lng: float) -> CanonicalPlace | None:
        data = await self._get(
            f"/geocoding/v5/mapbox.places/{lng},{lat}.json",
            access_token=self._api_key,
            limit=1,
        )
        feats = data.get("features", [])
        return self._to_canonical(feats[0]) if feats else None

    @staticmethod
    def _to_canonical(feature: dict) -> CanonicalPlace:
        lng, lat = feature["center"]
        ctx = {c["id"].split(".")[0]: c for c in feature.get("context", [])}
        country_code = (ctx.get("country", {}).get("short_code") or "ZZ").upper()[:2]
        return CanonicalPlace(
            id=feature["id"],
            name=feature.get("text", feature.get("place_name", "")),
            country_code=country_code,
            lat=lat,
            lng=lng,
            provider="mapbox",
            raw=feature,
        )
