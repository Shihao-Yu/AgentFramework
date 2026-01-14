"""OpenAI-compatible embedding client."""

import asyncio
from typing import Optional

import httpx
import numpy as np

from agentcore.settings.embedding import EmbeddingSettings


class EmbeddingClient:
    """OpenAI-compatible embedding client with rate limiting.
    
    Supports OpenAI API and compatible services like Azure OpenAI,
    BottleRocket, or any service with the same API format.
    
    Example:
        ```python
        settings = EmbeddingSettings(
            base_url="https://api.openai.com/v1",
            api_key="sk-...",
            model="text-embedding-ada-002",
        )
        client = EmbeddingClient(settings)
        
        vector = await client.embed("Hello, world!")
        # vector.shape => (1536,)
        ```
    """

    def __init__(self, settings: Optional[EmbeddingSettings] = None):
        self._settings = settings or EmbeddingSettings()
        self._semaphore = asyncio.Semaphore(self._settings.max_concurrent)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._settings.dimension

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self._settings.api_key:
                headers["Authorization"] = f"Bearer {self._settings.api_key}"
            
            self._client = httpx.AsyncClient(
                base_url=self._settings.base_url,
                headers=headers,
                timeout=httpx.Timeout(self._settings.timeout_seconds),
            )
        return self._client

    async def embed(self, text: str) -> np.ndarray:
        """Embed text and return normalized vector.
        
        Args:
            text: Text to embed
            
        Returns:
            Normalized embedding vector as float32 numpy array
            
        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        async with self._semaphore:
            client = await self._get_client()
            
            response = await client.post(
                "/embeddings",
                json={
                    "model": self._settings.model,
                    "input": text,
                },
            )
            response.raise_for_status()
            
            data = response.json()
            embedding = data["data"][0]["embedding"]
            
            # Convert to numpy and normalize
            vector = np.array(embedding, dtype=np.float32)
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
            
            return vector

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed multiple texts efficiently.
        
        Uses a single API call when possible (OpenAI supports batch input).
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of normalized embedding vectors
        """
        if not texts:
            return []
        
        async with self._semaphore:
            client = await self._get_client()
            
            response = await client.post(
                "/embeddings",
                json={
                    "model": self._settings.model,
                    "input": texts,
                },
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Sort by index to maintain order
            embeddings_data = sorted(data["data"], key=lambda x: x["index"])
            
            vectors = []
            for item in embeddings_data:
                vector = np.array(item["embedding"], dtype=np.float32)
                norm = np.linalg.norm(vector)
                if norm > 0:
                    vector = vector / norm
                vectors.append(vector)
            
            return vectors

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "EmbeddingClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


class MockEmbeddingClient:
    """Mock embedding client for testing without API calls.
    
    Uses hash-based seeding for reproducible pseudo-embeddings.
    NOT semantically meaningful - only for testing code paths.
    """

    def __init__(self, dimension: int = 1536):
        self._dimension = dimension
        self._cache: dict[str, np.ndarray] = {}

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> np.ndarray:
        """Generate pseudo-embedding based on text hash."""
        if text not in self._cache:
            seed = hash(text.lower()[:100]) % (2**32)
            rng = np.random.RandomState(seed)
            embedding = rng.randn(self._dimension).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)
            self._cache[text] = embedding
        return self._cache[text]

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Generate pseudo-embeddings for multiple texts."""
        return [await self.embed(text) for text in texts]

    async def close(self) -> None:
        """No-op for mock client."""
        pass

    async def __aenter__(self) -> "MockEmbeddingClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
