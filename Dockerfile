# syntax=docker/dockerfile:1.7

# ─── Stage 1: build venv ────────────────────────────────────────────────────
FROM python:3.12-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Pin uv to the version on the dev box. Bump in lockstep with `uv --version`.
RUN pip install --no-cache-dir uv==0.8.22

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev


# ─── Stage 2: runtime ───────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src"

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system gateway && useradd --system --gid gateway --home /app gateway

WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src

USER gateway

EXPOSE 9100

# Defaults to 2 workers; override via WEB_CONCURRENCY at runtime.
ENV WEB_CONCURRENCY=2

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:9100/v1/health || exit 1

CMD ["sh", "-c", "uvicorn gateway.main:app --host 0.0.0.0 --port 9100 --workers ${WEB_CONCURRENCY:-2}"]
