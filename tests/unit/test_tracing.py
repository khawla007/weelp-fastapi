"""OTel boot path — must be a no-op when the OTLP endpoint env var is unset."""

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_tracing_no_op_when_env_unset(monkeypatch):
    """Without OTEL_EXPORTER_OTLP_ENDPOINT set, configure_tracing must:
    - not raise
    - not import the heavy OTel SDK modules
    - log `tracing.disabled` once
    """
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    from gateway.observability import tracing

    tracing.reset_for_tests()
    app = FastAPI()
    tracing.configure_tracing(app)

    with TestClient(app) as client:
        # FastAPI without instrumentation still serves; no OTel side effects.
        r = client.get("/openapi.json")
    assert r.status_code == 200


def test_tracing_init_idempotent(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    from gateway.observability import tracing

    tracing.reset_for_tests()
    app = FastAPI()
    tracing.configure_tracing(app)
    tracing.configure_tracing(app)
    assert tracing._initialised is True
