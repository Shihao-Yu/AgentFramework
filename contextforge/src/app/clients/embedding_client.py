"""
Abstract interface for embedding generation.

Implement this interface with your embedding service (OpenAI, Cohere, custom model, etc.)
"""

from abc import ABC, abstractmethod
from typing import List

from app.clients.base import BaseClient
from app.core.config import settings


class EmbeddingClient(BaseClient):
    """
    Abstract interface for embedding generation.
    
    Implementations should connect to your embedding service
    (e.g., OpenAI text-embedding-3-small, Cohere, custom model).
    
    Expected embedding dimension: Configured via EMBEDDING_DIMENSION (default: 1536)
    
    Common dimensions by model:
    - OpenAI text-embedding-3-small: 1536
    - OpenAI text-embedding-3-large: 3072
    - Sentence Transformers (all-MiniLM-L6-v2): 384
    - Cohere embed-v3: 1024
    
    Example implementation:
    
    ```python
    class OpenAIEmbeddingClient(EmbeddingClient):
        def __init__(self, api_key: str):
            self.client = openai.AsyncOpenAI(api_key=api_key)
            self.model = "text-embedding-3-small"
        
        async def embed(self, text: str) -> List[float]:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=settings.EMBEDDING_DIMENSION
            )
            return response.data[0].embedding
        
        async def embed_batch(self, texts: List[str]) -> List[List[float]]:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=settings.EMBEDDING_DIMENSION
            )
            return [item.embedding for item in response.data]
    ```
    """
    
    @property
    def expected_dimension(self) -> int:
        """Expected embedding dimension from config."""
        return settings.EMBEDDING_DIMENSION
    
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
        try:
            result = await self.embed("health check")
            return len(result) == self.expected_dimension
        except Exception:
            return False
