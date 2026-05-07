import time

import httpx
from purgatory import AsyncCircuitBreakerFactory
from purgatory.domain.model import OpenedState
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from gateway.config import settings
from gateway.observability.logging import logger
from gateway.observability.metrics import record_breaker_state

_breaker_factory: AsyncCircuitBreakerFactory | None = None


def _get_breaker_factory() -> AsyncCircuitBreakerFactory:
    global _breaker_factory
    if _breaker_factory is None:
        _breaker_factory = AsyncCircuitBreakerFactory(
            default_threshold=settings.circuit_breaker_threshold,
            default_ttl=settings.circuit_breaker_ttl_seconds,
        )
    return _breaker_factory


def reset_breaker_factory() -> None:
    """Test hook: drop the global factory so tests get a fresh state."""
    global _breaker_factory
    _breaker_factory = None


class CircuitOpenError(httpx.HTTPError):
    """Raised when the circuit breaker is open. Maps to a 503 at the route layer."""


class BaseHttpAdapter:
    name: str = "base"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str,
        api_key: str,
        default_headers: dict[str, str] | None = None,
    ):
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._default_headers = default_headers
        self._breaker = None

    async def _get_circuit_breaker(self):
        if self._breaker is None:
            factory = _get_breaker_factory()
            self._breaker = await factory.get_breaker(self.name)
        return self._breaker

    async def _get(self, path: str, **params) -> dict:
        provider = getattr(self, "name", self.__class__.__name__)
        breaker = await self._get_circuit_breaker()
        t0 = time.perf_counter()
        try:
            async with breaker:
                data = await self._do_get(path, **params)
        except OpenedState as exc:
            record_breaker_state(provider, breaker.context.state)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.warning(
                "adapter.circuit_open",
                provider=provider,
                path=path,
                latency_ms=latency_ms,
                cache_hit=False,
            )
            raise CircuitOpenError(
                f"Circuit breaker open for provider '{provider}'"
            ) from exc
        except Exception as exc:
            record_breaker_state(provider, breaker.context.state)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.warning(
                "adapter.upstream_error",
                provider=provider,
                path=path,
                latency_ms=latency_ms,
                cache_hit=False,
                error=type(exc).__name__,
            )
            raise

        record_breaker_state(provider, breaker.context.state)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            "adapter.upstream_call",
            provider=provider,
            path=path,
            latency_ms=latency_ms,
            cache_hit=False,
        )
        return data

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, max=2.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _do_get(self, path: str, **params) -> dict:
        r = await self._client.get(
            f"{self._base_url}{path}",
            params=params,
            headers=self._default_headers,
            timeout=5.0,
        )
        r.raise_for_status()
        return r.json()
