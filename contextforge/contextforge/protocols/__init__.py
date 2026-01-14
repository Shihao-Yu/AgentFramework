"""
Protocol definitions for pluggable providers.

Use these protocols to implement custom embedding, LLM, or auth providers.
"""

from contextforge.protocols.embedding import EmbeddingProvider
from contextforge.protocols.llm import LLMProvider
from contextforge.protocols.auth import AuthProvider, AuthContext

__all__ = [
    "EmbeddingProvider",
    "LLMProvider", 
    "AuthProvider",
    "AuthContext",
]
