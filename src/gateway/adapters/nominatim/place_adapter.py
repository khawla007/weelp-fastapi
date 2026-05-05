from gateway.adapters.base import BaseHttpAdapter
from gateway.application.ports.place_provider import PlaceProvider
from gateway.domain.places import CanonicalPlace


class NominatimPlaceAdapter(BaseHttpAdapter, PlaceProvider):
    name = "nominatim"

    async def geocode(self, query: str, *, limit: int = 5) -> list[CanonicalPlace]:
        data = await self._get(
            "/search",
            q=query,
            format="jsonv2",
            limit=limit,
            addressdetails=1,
        )
        return [self._to_canonical(row) for row in data]

    async def reverse(self, lat: float, lng: float) -> CanonicalPlace | None:
        data = await self._get(
            "/reverse",
            lat=lat,
            lon=lng,
            format="jsonv2",
            addressdetails=1,
        )
        if not data or "error" in data:
            return None
        return self._to_canonical(data)

    @staticmethod
    def _to_canonical(row: dict) -> CanonicalPlace:
        addr = row.get("address") or {}
        country_code = (addr.get("country_code") or "ZZ").upper()[:2]
        place_id = row.get("place_id") or row.get("osm_id") or row.get("display_name", "")
        return CanonicalPlace(
            id=str(place_id),
            name=row.get("name") or row.get("display_name") or "",
            country_code=country_code,
            lat=float(row["lat"]),
            lng=float(row["lon"]),
            provider="nominatim",
            raw=row,
        )
