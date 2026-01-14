"""
Embedding Provider Protocol

Implement this protocol to provide custom embedding generation.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """
    Protocol for embedding generation providers.
    
    Implement this to integrate with your embedding service
    (OpenAI, Cohere, SentenceTransformers, custom model, etc.)
    
    Example:
        class MyEmbeddingProvider(EmbeddingProvider):
            def __init__(self, api_key: str):
                self.client = MyEmbeddingService(api_key)
            
            async def embed(self, text: str) -> list[float]:
                return await self.client.embed(text)
            
            async def embed_batch(self, texts: list[str]) -> list[list[float]]:
                return await self.client.embed_batch(texts)
            
            @property
            def dimensions(self) -> int:
                return 1024
    """
    
    async def embed(self, text: str) -> list[float]:
        """
        Generate embedding vector for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        ...
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embedding vectors for multiple texts.
        
        More efficient than calling embed() multiple times when
        the provider supports batching.
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors
        """
        ...
    
    @property
    def dimensions(self) -> int:
        """
        Return the embedding vector dimensions.
        
        Common values:
        - 384 (all-MiniLM-L6-v2)
        - 768 (all-mpnet-base-v2)
        - 1024 (text-embedding-3-large with dimensions=1024)
        - 1536 (text-embedding-3-small, text-embedding-ada-002)
        """
        ...
