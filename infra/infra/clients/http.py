from typing import Any, Optional


class HttpClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        headers: Optional[dict[str, str]] = None,
    ):
        self._base_url = base_url
        self._timeout = timeout
        self._headers = headers or {}
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
            except ImportError:
                raise ImportError("httpx package required. Install with: pip install httpx")

            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                headers=self._headers,
            )
        return self._client

    async def get(self, url: str, **kwargs: Any) -> Any:
        client = self._get_client()
        response = await client.get(url, **kwargs)
        response.raise_for_status()
        return response.json()

    async def post(self, url: str, json: Optional[dict] = None, **kwargs: Any) -> Any:
        client = self._get_client()
        response = await client.post(url, json=json, **kwargs)
        response.raise_for_status()
        return response.json()

    async def put(self, url: str, json: Optional[dict] = None, **kwargs: Any) -> Any:
        client = self._get_client()
        response = await client.put(url, json=json, **kwargs)
        response.raise_for_status()
        return response.json()

    async def delete(self, url: str, **kwargs: Any) -> Any:
        client = self._get_client()
        response = await client.delete(url, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "HttpClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
