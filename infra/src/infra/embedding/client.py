import os
from typing import Optional

from infra.settings.ssl import get_ssl_settings


MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class EmbeddingClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None,
        timeout: float = 60.0,
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = base_url or os.environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
        self._model = model
        self._timeout = timeout
        self._client = None
        self._http_client = None

        if dimensions is not None:
            self._dimensions = dimensions
        elif model in MODEL_DIMENSIONS:
            self._dimensions = MODEL_DIMENSIONS[model]
        else:
            self._dimensions = 1536

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError("openai package required. Install with: pip install openai")

            try:
                import httpx
            except ImportError:
                raise ImportError("httpx package required. Install with: pip install httpx")

            ssl_settings = get_ssl_settings()
            ca_cert = ssl_settings.get_ca_cert()

            self._http_client = httpx.AsyncClient(verify=ca_cert)
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
                http_client=self._http_client,
            )
        return self._client

    async def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * self._dimensions

        client = self._get_client()

        kwargs = {
            "input": text,
            "model": self._model,
        }

        if (
            self._model.startswith("text-embedding-3-")
            and self._dimensions != MODEL_DIMENSIONS.get(self._model)
        ):
            kwargs["dimensions"] = self._dimensions

        response = await client.embeddings.create(**kwargs)
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        non_empty_indices = []
        non_empty_texts = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_indices.append(i)
                non_empty_texts.append(text)

        if not non_empty_texts:
            return [[0.0] * self._dimensions for _ in texts]

        client = self._get_client()

        kwargs = {
            "input": non_empty_texts,
            "model": self._model,
        }

        if (
            self._model.startswith("text-embedding-3-")
            and self._dimensions != MODEL_DIMENSIONS.get(self._model)
        ):
            kwargs["dimensions"] = self._dimensions

        response = await client.embeddings.create(**kwargs)

        embeddings_by_index = {item.index: item.embedding for item in response.data}

        result: list[list[float]] = [[0.0] * self._dimensions for _ in texts]
        for i, original_idx in enumerate(non_empty_indices):
            result[original_idx] = embeddings_by_index[i]

        return result

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> "EmbeddingClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
