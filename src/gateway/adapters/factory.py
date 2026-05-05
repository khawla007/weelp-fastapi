from typing import TypeVar

T = TypeVar("T")


class AdapterFactory:
    def __init__(self) -> None:
        self._registry: dict[tuple[type, str], object] = {}

    def register(self, port: type[T], name: str, instance: T) -> None:
        self._registry[(port, name)] = instance

    def get(self, port: type[T], name: str) -> T:
        try:
            return self._registry[(port, name)]  # type: ignore[return-value]
        except KeyError as e:
            raise ValueError(f"No adapter registered for {port.__name__}:{name}") from e


factory = AdapterFactory()
