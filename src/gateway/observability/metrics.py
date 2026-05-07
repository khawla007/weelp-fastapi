"""Prometheus metrics — exposed at `/metrics`.

Default HTTP histograms come from `prometheus-fastapi-instrumentator`; on top of
those we add two custom series:

- `gateway_cache_events_total{event,namespace,provider}` — cache hit/miss/set_failed
- `gateway_circuit_breaker_state{provider}` — 0=closed, 1=half-open, 2=open

Label cardinality is bounded on purpose: no `path` (one series per route would
explode after a year of growth) and no `request_id` (unbounded).
"""

from __future__ import annotations

from prometheus_client import REGISTRY, Counter, Gauge

cache_events: Counter = Counter(
    "gateway_cache_events_total",
    "Cache events emitted by the gateway route-level cache layer.",
    labelnames=("event", "namespace", "provider"),
)

circuit_breaker_state: Gauge = Gauge(
    "gateway_circuit_breaker_state",
    "Per-provider circuit breaker state. 0=closed, 1=half-open, 2=open.",
    labelnames=("provider",),
)


def record_cache_event(event: str, *, namespace: str, provider: str) -> None:
    """Bump the cache counter once. Wraps the structlog log site."""
    cache_events.labels(event=event, namespace=namespace, provider=provider).inc()


_BREAKER_STATE_NUMERIC = {"closed": 0, "half-open": 1, "opened": 2, "open": 2}


def record_breaker_state(provider: str, state: str) -> None:
    """Update the per-provider gauge from a purgatory state name."""
    circuit_breaker_state.labels(provider=provider).set(
        _BREAKER_STATE_NUMERIC.get(state, 0)
    )


def reset_for_tests() -> None:
    """Test hook — drop label values so tests start clean."""
    for collector in (cache_events, circuit_breaker_state):
        try:
            collector.clear()
        except AttributeError:
            pass


__all__ = [
    "REGISTRY",
    "cache_events",
    "circuit_breaker_state",
    "record_breaker_state",
    "record_cache_event",
    "reset_for_tests",
]
