"""Embedding module for vector embeddings."""

from agentcore.embedding.client import EmbeddingClient, MockEmbeddingClient
from agentcore.embedding.protocol import EmbeddingProtocol

__all__ = ["EmbeddingClient", "MockEmbeddingClient", "EmbeddingProtocol"]
