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

    def all_for(self, port: type[T]) -> list[tuple[str, T]]:
        out: list[tuple[str, T]] = []
        for (p, name), inst in self._registry.items():
            if p is port:
                out.append((name, inst))  # type: ignore[arg-type]
        return out

    def clear(self) -> None:
        self._registry.clear()


factory = AdapterFactory()
