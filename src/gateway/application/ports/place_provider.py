from abc import ABC, abstractmethod

from gateway.domain.places import CanonicalPlace


class PlaceProvider(ABC):
    name: str

    @abstractmethod
    async def geocode(self, query: str, *, limit: int = 5) -> list[CanonicalPlace]: ...

    @abstractmethod
    async def reverse(self, lat: float, lng: float) -> CanonicalPlace | None: ...
