"""
Embedding providers.

Available providers:
    - SentenceTransformersProvider: Local embeddings using HuggingFace models
    - OpenAIEmbeddingProvider: OpenAI text-embedding-3-small/large
    - MockEmbeddingProvider: Mock provider for testing

Usage:
    from contextforge.providers.embedding import OpenAIEmbeddingProvider
    
    provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
"""

from contextforge.providers.embedding.sentence_transformers import SentenceTransformersProvider
from contextforge.providers.embedding.mock import MockEmbeddingProvider

# Lazy import for optional dependency
def __getattr__(name):
    if name == "OpenAIEmbeddingProvider":
        from contextforge.providers.embedding.openai import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "SentenceTransformersProvider",
    "MockEmbeddingProvider",
    "OpenAIEmbeddingProvider",
]
