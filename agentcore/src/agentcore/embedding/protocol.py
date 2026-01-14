"""Embedding protocol definition."""

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class EmbeddingProtocol(Protocol):
    """Protocol for embedding clients."""

    async def embed(self, text: str) -> np.ndarray:
        """Embed text and return vector.
        
        Args:
            text: Text to embed
            
        Returns:
            Normalized embedding vector as numpy array
        """
        ...

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of normalized embedding vectors
        """
        ...
