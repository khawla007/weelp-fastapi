"""Cache decorator emits cache.miss / cache.hit as OTel span events.

The cache hop is invisible in Jaeger without these events — a 5 ms hit and
a 200 ms miss render identically until you cross-reference structlog by
request_id. This test substitutes `trace.get_current_span()` with a tracer
that hands back a recording span, fires two cached requests against the
in-process app, and asserts the events landed on those spans. The recording
span machinery is test-only; production wiring in `observability/tracing.py`
is untouched.
"""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)


SAMPLE_MAPBOX_RESPONSE = {
    "features": [
        {
            "id": "place.42",
            "text": "Paris",
            "place_name": "Paris, France",
            "center": [2.35, 48.86],
            "context": [
                {"id": "country.fr", "short_code": "fr", "text": "France"}
            ],
        }
    ]
}


@pytest.mark.asyncio
async def test_cache_miss_then_hit_emits_span_events(monkeypatch, app_with_fake_redis):
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")

    from gateway.observability import cache as cache_module

    span_holder: dict[str, object] = {}

    class _StubTrace:
        @staticmethod
        def get_current_span():
            span = tracer.start_span("cache.test")
            span_holder.setdefault("spans", []).append(span)  # type: ignore[union-attr]
            return span

    monkeypatch.setattr(cache_module, "trace", _StubTrace)

    with TestClient(app_with_fake_redis) as client:
        with respx.mock(base_url="https://api.mapbox.com", assert_all_called=False) as mock:
            mock.get("/geocoding/v5/mapbox.places/paris.json").mock(
                return_value=httpx.Response(200, json=SAMPLE_MAPBOX_RESPONSE)
            )
            r1 = client.get(
                "/v1/places/geocode", params={"q": "paris", "provider": "mapbox"}
            )
            assert r1.status_code == 200
            r2 = client.get(
                "/v1/places/geocode", params={"q": "paris", "provider": "mapbox"}
            )
            assert r2.status_code == 200

    for span in span_holder.get("spans", []):  # type: ignore[union-attr]
        span.end()  # type: ignore[attr-defined]

    spans = exporter.get_finished_spans()
    miss = [
        e for s in spans for e in s.events if e.name == "cache.miss"
    ]
    hit = [
        e for s in spans for e in s.events if e.name == "cache.hit"
    ]

    assert len(miss) == 1, "first request should record cache.miss"
    assert len(hit) == 1, "second request should record cache.hit"

    miss_attrs = dict(miss[0].attributes or {})
    hit_attrs = dict(hit[0].attributes or {})
    assert miss_attrs.get("namespace") == "geocode"
    assert miss_attrs.get("provider") == "mapbox"
    assert "key" in miss_attrs
    assert hit_attrs.get("namespace") == "geocode"
    assert hit_attrs.get("provider") == "mapbox"


def test_cache_decorator_safe_when_tracing_disabled():
    """`trace.get_current_span()` returns INVALID_SPAN when no provider is wired —
    `add_event` is a no-op there. This test asserts that contract holds, so the
    cache decorator's `span.add_event(...)` calls don't raise in default
    test/dev shape (no OTLP endpoint set, no tracer provider installed)."""
    span = otel_trace.get_current_span()
    assert span is otel_trace.INVALID_SPAN or not span.is_recording()
    # Must not raise.
    span.add_event("cache.hit", {"namespace": "x", "provider": "y", "key": "z"})
