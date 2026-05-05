# Weelp Integration Gateway (FastAPI)

Python FastAPI service that wraps third-party APIs (starting with Mapbox geocoding) behind a unified Adapter layer and exposes a canonical Pydantic schema to the Weelp frontend.

Full architecture and roadmap: `../docs/fast-api/Roadmap.md`.

## Quick start

```bash
cd weelp/fastapi

# Install (already done if .venv exists)
uv sync

# Run dev server
uv run uvicorn gateway.main:app --reload --port 9000

# Verify
curl -s http://localhost:9000/v1/health
curl -s 'http://localhost:9000/v1/places/geocode?q=marseille&limit=2'

# Swagger UI
# http://localhost:9000/docs
```

## Tests

```bash
uv run pytest -q
uv run ruff check src tests
```

## Layout

- `src/gateway/domain/` — canonical Pydantic DTOs
- `src/gateway/application/ports/` — abstract provider contracts (ABCs)
- `src/gateway/adapters/` — vendor-specific adapters; one per provider
- `src/gateway/infrastructure/` — FastAPI DI wiring
- `src/gateway/api/v1/` — HTTP routers

## Adding a new vendor

1. Create `src/gateway/adapters/<vendor>/<resource>_adapter.py` implementing the relevant port.
2. Register in `src/gateway/main.py` `lifespan()`.
3. Test with `respx`.
4. No frontend changes required.

## Env

Copy `.env.example` to `.env` and fill in your tokens. `.env` is gitignored.
