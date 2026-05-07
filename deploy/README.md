# Deploying the Weelp Integration Gateway

This folder is the operational packaging for the FastAPI gateway. The Dockerfile, compose files, and nginx snippet are the entire surface area you need to take the service from a clean checkout to a process running behind `gateway.weelp.com`.

For the *why* behind the architecture, read [`../../docs/fast-api/Roadmap.md`](../../docs/fast-api/Roadmap.md) — §6 (Operational Concerns) is the canonical table for secrets, logging, metrics, and health endpoints. Don't duplicate that table here; link to it.

## Prerequisites

- Docker Engine ≥ 24 with the Compose v2 plugin (`docker compose version` must work).
- Host nginx (the gateway expects to sit behind the same nginx that already fronts the Laravel + Next.js services). Adding a second reverse proxy inside the compose stack creates two TLS stories and two rate-limit layers; don't.
- A `.env` file at the repo root, derived from `.env.example`. `JWT_SECRET` and `MAPBOX_TOKEN` must be filled before first boot — staging and prod values *diverge*; never reuse one across environments.

## First bring-up

```bash
cd weelp/fastapi
cp .env.example .env
# Open .env and fill MAPBOX_TOKEN, JWT_SECRET (32+ bytes), and CORS_ORIGINS.
# Confirm REDIS_URL points at redis://redis:6379/0 (the in-container DNS name).

docker compose up -d --build
docker compose logs -f gateway   # wait for "gateway.startup"

curl -s http://localhost:9100/v1/health    # → {"status":"ok"}
curl -s 'http://localhost:9100/v1/places/geocode?q=paris&limit=2' | head
```

The second identical geocode call should answer in 5–20 ms — that's the Redis cache. If it doesn't, check `docker compose ps redis` and `docker compose exec gateway redis-cli -h redis ping`.

## Production overlay

```bash
docker compose -f docker-compose.yml -f compose.prod.yml up -d
```

What the overlay changes vs the base file:

| Change | Why |
|---|---|
| Redis port unmapped | Nothing on the host should be poking Redis directly in prod. |
| Gateway port bound to `127.0.0.1` only | Host nginx is the only public-facing path. |
| `restart: unless-stopped` on both services | A crash recovers without a human; only an explicit `docker compose down` keeps the service down. |

Verify the merged config before applying it:

```bash
docker compose -f docker-compose.yml -f compose.prod.yml config
```

## nginx

Copy [`nginx/gateway.weelp.com.conf`](nginx/gateway.weelp.com.conf) into `/etc/nginx/sites-available/`, symlink into `sites-enabled/`, and reload:

```bash
sudo ln -sf /etc/nginx/sites-available/gateway.weelp.com.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo nginx -s reload
```

The snippet:

- terminates TLS (Let's Encrypt cert path baked in — adjust if you renew via something else);
- proxies to `127.0.0.1:9100`;
- forwards `Authorization`, `X-Forwarded-For`, and `X-Request-ID` so the gateway's `RequestIdMiddleware` can preserve trace ids across the hop;
- *does not* rate-limit `/v1/places/*`. The gateway's slowapi limiter is the source of truth — don't double up.

End-to-end smoke after nginx is wired:

```bash
curl -H "X-Request-ID: phase6-smoke" https://gateway.weelp.com/v1/health
# Expect 200 OK. Tail the gateway log: request_id=phase6-smoke must appear in
# the line for that request — proves the proxy preserved the inbound id.
```

## Environment variable contract

Two URL-shaped vars live in two repos and mean different things:

| Variable | Repo | Meaning |
|---|---|---|
| `GATEWAY_PUBLIC_URL` | `weelp/fastapi/.env` | The gateway's outbound view of itself — used for log enrichment and any future webhook signing. |
| `NEXT_PUBLIC_GATEWAY_URL` | `weelp/frontend/.env` | The frontend's view of the gateway — what the browser hits. |

In dev they're the same string (`http://localhost:9100`). In prod they're conceptually distinct namespaces (frontend → public hostname, gateway → its own self-reference) even when the values match.

`JWT_SECRET` lives in **both** the Laravel backend `.env` and the gateway `.env`. They must match exactly, byte for byte. Rotation is a coordinated two-stage deploy — see `weelp/docs/fast-api/documentation/phase4/phase-4.md`.

## Health checks

| Probe | Source | Use |
|---|---|---|
| `GET /v1/health` | gateway | Liveness — does the process respond? |
| `redis-cli ping` | redis container | Compose dependency gate (`condition: service_healthy`). |
| Dockerfile `HEALTHCHECK` | container runtime | Lets orchestrators (compose, swarm, k8s) see liveness without curl gymnastics from the host. |

Roadmap §6 keeps the canonical operational table — read it before adding new probes here.

## What's *not* in this folder

- TLS certificates. Use certbot or your existing cert workflow.
- Backups. Redis is a cache; losing the volume costs you a few seconds of latency on the next request, not data.
- Secret distribution. Bring secrets in through whatever already works for the Laravel and Next.js services (Docker secrets, sealed env files, KMS) — adding a third pattern just for the gateway doesn't earn its complexity.
