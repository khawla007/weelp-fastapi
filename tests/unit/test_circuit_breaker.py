import asyncio

import httpx
import pytest
import respx

from gateway.adapters import base as base_module
from gateway.adapters.base import BaseHttpAdapter, CircuitOpenError


class FlakyAdapter(BaseHttpAdapter):
    name = "flaky"


@pytest.fixture(autouse=True)
def _reset_breaker():
    base_module.reset_breaker_factory()
    yield
    base_module.reset_breaker_factory()


@pytest.mark.asyncio
async def test_breaker_opens_after_threshold_failures(monkeypatch):
    monkeypatch.setattr("gateway.config.settings.circuit_breaker_threshold", 3)
    monkeypatch.setattr("gateway.config.settings.circuit_breaker_ttl_seconds", 1)

    async with httpx.AsyncClient() as client:
        adapter = FlakyAdapter(
            client, base_url="https://flaky.test", api_key="k"
        )
        with respx.mock(base_url="https://flaky.test", assert_all_called=False) as mock:
            route = mock.get("/probe").mock(return_value=httpx.Response(500))

            for _ in range(3):
                with pytest.raises(httpx.HTTPStatusError):
                    await adapter._get("/probe")

            calls_before_open = route.call_count

            with pytest.raises(CircuitOpenError):
                await adapter._get("/probe")

            assert route.call_count == calls_before_open


@pytest.mark.asyncio
async def test_breaker_half_open_recovers(monkeypatch):
    monkeypatch.setattr("gateway.config.settings.circuit_breaker_threshold", 2)
    monkeypatch.setattr("gateway.config.settings.circuit_breaker_ttl_seconds", 1)

    async with httpx.AsyncClient() as client:
        adapter = FlakyAdapter(
            client, base_url="https://flaky2.test", api_key="k"
        )
        with respx.mock(base_url="https://flaky2.test", assert_all_called=False) as mock:
            route = mock.get("/probe").mock(return_value=httpx.Response(500))

            for _ in range(2):
                with pytest.raises(httpx.HTTPStatusError):
                    await adapter._get("/probe")

            with pytest.raises(CircuitOpenError):
                await adapter._get("/probe")

            await asyncio.sleep(1.2)

            route.mock(return_value=httpx.Response(200, json={"ok": True}))
            result = await adapter._get("/probe")
            assert result == {"ok": True}
