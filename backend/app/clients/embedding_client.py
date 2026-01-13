"""
Abstract interface for embedding generation.

Implement this interface with your embedding service (OpenAI, Cohere, custom model, etc.)
"""

from abc import ABC, abstractmethod
from typing import List

from app.clients.base import BaseClient


class EmbeddingClient(BaseClient):
    """
    Abstract interface for embedding generation.
    
    Implementations should connect to your embedding service
    (e.g., OpenAI text-embedding-3-large, Cohere, custom model).
    
    Expected embedding dimension: 1024
    
    Example implementation:
    
    ```python
    class OpenAIEmbeddingClient(EmbeddingClient):
        def __init__(self, api_key: str):
            self.client = openai.AsyncOpenAI(api_key=api_key)
            self.model = "text-embedding-3-large"
        
        async def embed(self, text: str) -> List[float]:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=1024
            )
            return response.data[0].embedding
        
        async def embed_batch(self, texts: List[str]) -> List[List[float]]:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=1024
            )
            return [item.embedding for item in response.data]
    ```
    """
    
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding vector for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of 1024 floats representing the embedding vector
            
        Raises:
            Exception: If embedding generation fails
        """
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embedding vectors for multiple texts.
        
        More efficient than calling embed() multiple times.
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors (each 1024 floats)
            
        Raises:
            Exception: If embedding generation fails
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Check if embedding service is available.
        
        Default implementation tries to embed a simple text.
        Override if your service has a dedicated health endpoint.
        """
        try:
            result = await self.embed("health check")
            return len(result) == 1024
        except Exception:
            return False


class MockEmbeddingClient(EmbeddingClient):
    """
    Mock implementation that returns zero vectors.
    
    Use this for:
    - Testing without external dependencies
    - Development when embedding service is unavailable
    
    Replace with actual implementation for production.
    """
    
    EMBEDDING_DIM = 1024
    
    async def embed(self, text: str) -> List[float]:
        """Return a zero vector."""
        return [0.0] * self.EMBEDDING_DIM
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Return zero vectors for each text."""
        return [[0.0] * self.EMBEDDING_DIM for _ in texts]
    
    async def health_check(self) -> bool:
        """Always returns True."""
        return True
