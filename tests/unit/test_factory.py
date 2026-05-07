"""AdapterFactory: register/get/all_for/clear and the missing-key error path."""

import pytest

from gateway.adapters.factory import AdapterFactory
from gateway.application.ports.place_provider import PlaceProvider
from gateway.domain.places import CanonicalPlace


class _Stub(PlaceProvider):
    name = "stub"

    async def geocode(self, query: str, *, limit: int = 5) -> list[CanonicalPlace]:
        return []

    async def reverse(self, lat: float, lng: float) -> CanonicalPlace | None:
        return None


def test_get_unknown_adapter_raises_value_error():
    f = AdapterFactory()
    with pytest.raises(ValueError, match="No adapter registered for PlaceProvider:ghost"):
        f.get(PlaceProvider, "ghost")


def test_register_then_get_round_trip():
    f = AdapterFactory()
    inst = _Stub()
    f.register(PlaceProvider, "stub", inst)
    assert f.get(PlaceProvider, "stub") is inst


def test_all_for_returns_only_matching_port():
    f = AdapterFactory()
    inst = _Stub()
    f.register(PlaceProvider, "a", inst)
    f.register(PlaceProvider, "b", inst)
    f.register(str, "noise", "ignored")
    pairs = dict(f.all_for(PlaceProvider))
    assert pairs == {"a": inst, "b": inst}


def test_clear_drops_all_registrations():
    f = AdapterFactory()
    f.register(PlaceProvider, "a", _Stub())
    f.clear()
    with pytest.raises(ValueError):
        f.get(PlaceProvider, "a")
