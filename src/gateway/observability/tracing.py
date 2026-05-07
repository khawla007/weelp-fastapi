"""OpenTelemetry tracing setup.

`OTEL_EXPORTER_OTLP_ENDPOINT` is the on/off switch — when unset, every call here
becomes a no-op (a single `tracing.disabled` log line at startup), so the gateway
boots cleanly even if the collector is unreachable. Sampling defaults to 10% via
the env contract documented in `.env.example`.

The auto-instrumentations cover FastAPI, httpx, and redis. We layer one
gateway-specific concern on top: tying the existing `X-Request-ID` value to the
active span as `gateway.request_id` so a structlog line and an OTel trace can be
cross-referenced from either side.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from gateway.observability.logging import logger

_initialised: bool = False


def configure_tracing(app: FastAPI) -> None:
    """Wire OTel auto-instrumentations onto the FastAPI app.

    Idempotent — safe to call from `main` import time.
    """
    global _initialised
    if _initialised:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("tracing.disabled", reason="OTEL_EXPORTER_OTLP_ENDPOINT unset")
        _initialised = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning("tracing.import_failed", error=type(exc).__name__)
        _initialised = True
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", "weelp-gateway")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, server_request_hook=_attach_request_id)
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()

    logger.info(
        "tracing.enabled",
        endpoint=endpoint,
        service_name=service_name,
        sampler=os.getenv("OTEL_TRACES_SAMPLER", "parentbased_traceidratio"),
        sampler_arg=os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1"),
    )
    _initialised = True


def _attach_request_id(span, scope) -> None:
    """FastAPI server hook — copy the inbound X-Request-ID onto the span.

    `RequestIdMiddleware` runs *after* OTel's ASGI instrumentation captures the
    server span, so we read the raw header here. Falls back silently if the
    header is missing or malformed.
    """
    if span is None or not span.is_recording():
        return
    headers = scope.get("headers") or []
    for raw_name, raw_value in headers:
        try:
            name = raw_name.decode("latin-1").lower()
        except Exception:
            continue
        if name == "x-request-id":
            try:
                span.set_attribute("gateway.request_id", raw_value.decode("latin-1"))
            except Exception:
                pass
            return


def reset_for_tests() -> None:
    global _initialised
    _initialised = False
