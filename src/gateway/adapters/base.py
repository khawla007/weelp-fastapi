import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class BaseHttpAdapter:
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, max=2.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _get(self, path: str, **params) -> dict:
        r = await self._client.get(
            f"{self._base_url}{path}",
            params=params,
            headers=self._default_headers,
            timeout=5.0,
        )
        r.raise_for_status()
        return r.json()
