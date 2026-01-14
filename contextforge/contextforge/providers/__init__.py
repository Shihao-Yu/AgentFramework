"""
Built-in providers for embedding, LLM, and auth.

Providers:
- embedding: SentenceTransformersProvider (default), OpenAIProvider, MockProvider
- llm: OpenAIProvider, MockProvider
- auth: HeaderAuthProvider, JWTAuthProvider, NoopAuthProvider
"""

from contextforge.providers.embedding import (
    SentenceTransformersProvider,
    MockEmbeddingProvider,
)
from contextforge.providers.auth import (
    HeaderAuthProvider,
    NoopAuthProvider,
)

__all__ = [
    # Embedding
    "SentenceTransformersProvider",
    "MockEmbeddingProvider",
    # Auth
    "HeaderAuthProvider",
    "NoopAuthProvider",
]
