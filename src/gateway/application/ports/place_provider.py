from abc import ABC, abstractmethod

from gateway.domain.places import CanonicalPlace


class PlaceProvider(ABC):
    name: str

    @abstractmethod
    async def geocode(self, query: str, *, limit: int = 5) -> list[CanonicalPlace]: ...

    @abstractmethod
    async def reverse(self, lat: float, lng: float) -> CanonicalPlace | None: ...

    async def health(self) -> None:
        """Cheap probe used by /v1/ready. Default no-op so adapters may opt in.

        Override to make a HEAD/lightweight call against the upstream. Raise on
        failure; the readiness endpoint catches and reports the exception name.
        """
        return None
