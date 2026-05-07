"""Standalone uvicorn launcher for the Phase 9 perf baseline.

Substitutes Redis with fakeredis (in-process) and Mapbox httpx calls with a
canned response so the run measures *gateway overhead* deterministically.
The cache-hit profile records the cost of a hot cache path; the cache-miss
profile records the same path through the cache decorator + a stubbed
upstream call. Real-network upstream latency is intentionally factored out
so the number doesn't drift with mapbox.com weather.

Run on its own port (default 9101) so it doesn't collide with a dev gateway.
Stop with Ctrl+C.
"""

from __future__ import annotations

import os
import sys

import fakeredis.aioredis
import httpx
import redis.asyncio
import uvicorn

os.environ.setdefault("MAPBOX_TOKEN", "perf-token")
os.environ.setdefault("JWT_SECRET", "perf-secret-32-bytes-padded-xxxxx")
os.environ.setdefault("NOMINATIM_USER_AGENT", "weelp-gw-perf/0.1 (perf@local)")
os.environ.setdefault("RATE_LIMIT_PER_MIN", "1000000")
os.environ.setdefault("USER_RATE_LIMIT_PER_MIN", "1000000")
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")

_shared_fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
redis.asyncio.from_url = lambda *a, **kw: _shared_fake  # type: ignore[assignment]


_SAMPLE_MAPBOX = {
    "features": [
        {
            "id": "place.42",
            "text": "Sample",
            "place_name": "Sample, FR",
            "center": [2.35, 48.86],
            "context": [
                {"id": "country.fr", "short_code": "fr", "text": "France"}
            ],
        }
    ]
}


_orig_send = httpx.AsyncClient.send


async def _stub_send(self, request, *args, **kwargs):  # type: ignore[override]
    if "api.mapbox.com" in str(request.url):
        return httpx.Response(200, json=_SAMPLE_MAPBOX, request=request)
    return await _orig_send(self, request, *args, **kwargs)


httpx.AsyncClient.send = _stub_send  # type: ignore[assignment]


def main() -> int:
    from gateway.main import app

    port = int(os.getenv("PERF_PORT", "9101"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
