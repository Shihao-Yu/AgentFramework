"""
Mock Embedding Provider

For testing and development without external dependencies.
"""

import hashlib


class MockEmbeddingProvider:
    """
    Mock embedding provider for testing.
    
    Generates deterministic pseudo-embeddings based on text hash.
    Useful for testing without loading real models.
    
    Args:
        dimensions: Embedding dimensions (default: 384)
    
    Example:
        provider = MockEmbeddingProvider(dimensions=384)
        embedding = await provider.embed("test")
        assert len(embedding) == 384
    """
    
    def __init__(self, dimensions: int = 384):
        self._dimensions = dimensions
    
    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        return self._dimensions
    
    async def embed(self, text: str) -> list[float]:
        """Generate deterministic pseudo-embedding from text hash."""
        return self._hash_to_embedding(text)
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return [self._hash_to_embedding(text) for text in texts]
    
    def _hash_to_embedding(self, text: str) -> list[float]:
        """Convert text to deterministic embedding via hash."""
        # Use SHA-256 hash to generate pseudo-random but deterministic values
        hash_bytes = hashlib.sha256(text.encode()).digest()
        
        # Extend hash to fill dimensions
        extended = hash_bytes * ((self._dimensions // len(hash_bytes)) + 1)
        
        # Convert to floats in range [-1, 1]
        embedding = []
        for i in range(self._dimensions):
            # Convert byte to float in range [-1, 1]
            value = (extended[i] / 127.5) - 1.0
            embedding.append(value)
        
        # Normalize
        norm = sum(v * v for v in embedding) ** 0.5
        if norm > 0:
            embedding = [v / norm for v in embedding]
        
        return embedding
