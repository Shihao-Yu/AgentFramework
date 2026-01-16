"""
OpenAI Embedding Provider

Uses OpenAI's text-embedding-3-small/large models for vector embeddings.

Installation:
    pip install contextforge[openai]
    # or
    pip install openai

Usage:
    from contextforge.providers.embedding import OpenAIEmbeddingProvider
    
    provider = OpenAIEmbeddingProvider(
        api_key="sk-...",
        model="text-embedding-3-small",  # or "text-embedding-3-large"
    )
    
    embedding = await provider.embed("Hello world")
"""

from __future__ import annotations

import os
from typing import Optional

from contextforge.core.exceptions import EmbeddingError, ConfigurationError


class OpenAIEmbeddingProvider:
    """
    OpenAI embedding provider using the embeddings API.
    
    Supports:
    - text-embedding-3-small (1536 dimensions, recommended)
    - text-embedding-3-large (3072 dimensions, higher quality)
    - text-embedding-ada-002 (1536 dimensions, legacy)
    
    Args:
        api_key: OpenAI API key (default: from CONTEXTFORGE_OPENAI_API_KEY env var)
        model: Model name (default: text-embedding-3-small)
        dimensions: Override embedding dimensions (only for text-embedding-3-* models)
        batch_size: Maximum texts per batch request (default: 100)
    
    Example:
        provider = OpenAIEmbeddingProvider()
        
        # Single embedding
        embedding = await provider.embed("Search query")
        
        # Batch embeddings
        embeddings = await provider.embed_batch([
            "Document 1",
            "Document 2",
            "Document 3",
        ])
    """
    
    # Model dimension defaults
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None,
        batch_size: int = 100,
        timeout: float = 60.0,
    ):
        self._api_key = api_key or os.environ.get("CONTEXTFORGE_OPENAI_API_KEY")
        if not self._api_key:
            raise ConfigurationError(
                "OpenAI API key not provided. "
                "Set CONTEXTFORGE_OPENAI_API_KEY environment variable or pass api_key parameter."
            )
        
        self._model = model
        self._batch_size = batch_size
        self._timeout = timeout
        self._client = None
        
        # Determine dimensions
        if dimensions is not None:
            self._dimensions = dimensions
        elif model in self.MODEL_DIMENSIONS:
            self._dimensions = self.MODEL_DIMENSIONS[model]
        else:
            # Unknown model, will be set on first call
            self._dimensions = None
    
    @property
    def dimensions(self) -> int:
        """Return the embedding vector dimensions."""
        if self._dimensions is None:
            # Default fallback
            return 1536
        return self._dimensions
    
    @property
    def _openai_client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ConfigurationError(
                    "OpenAI library not installed. "
                    "Run: pip install contextforge[openai]"
                )
            
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                timeout=self._timeout,
            )
        return self._client
    
    async def embed(self, text: str) -> list[float]:
        """
        Generate embedding vector for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
            
        Raises:
            EmbeddingError: If API call fails
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.dimensions
        
        try:
            # Prepare request kwargs
            kwargs = {
                "input": text,
                "model": self._model,
            }
            
            # Only include dimensions for text-embedding-3-* models
            if (
                self._model.startswith("text-embedding-3-")
                and self._dimensions is not None
                and self._dimensions != self.MODEL_DIMENSIONS.get(self._model)
            ):
                kwargs["dimensions"] = self._dimensions
            
            response = await self._openai_client.embeddings.create(**kwargs)
            embedding = response.data[0].embedding
            
            # Update dimensions if not set
            if self._dimensions is None:
                self._dimensions = len(embedding)
            
            return embedding
            
        except Exception as e:
            raise EmbeddingError(
                f"OpenAI embedding failed: {str(e)}",
                provider="openai",
                model=self._model,
            ) from e
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embedding vectors for multiple texts.
        
        Handles batching automatically for large lists.
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors (same order as input)
            
        Raises:
            EmbeddingError: If API call fails
        """
        if not texts:
            return []
        
        # Handle empty strings
        non_empty_indices = []
        non_empty_texts = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_indices.append(i)
                non_empty_texts.append(text)
        
        # If all empty, return zero vectors
        if not non_empty_texts:
            return [[0.0] * self.dimensions for _ in texts]
        
        try:
            all_embeddings = []
            
            # Process in batches
            for i in range(0, len(non_empty_texts), self._batch_size):
                batch = non_empty_texts[i : i + self._batch_size]
                
                # Prepare request kwargs
                kwargs = {
                    "input": batch,
                    "model": self._model,
                }
                
                if (
                    self._model.startswith("text-embedding-3-")
                    and self._dimensions is not None
                    and self._dimensions != self.MODEL_DIMENSIONS.get(self._model)
                ):
                    kwargs["dimensions"] = self._dimensions
                
                response = await self._openai_client.embeddings.create(**kwargs)
                
                # OpenAI returns embeddings sorted by index
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # Update dimensions if not set
                if self._dimensions is None and batch_embeddings:
                    self._dimensions = len(batch_embeddings[0])
            
            # Reconstruct full result with zero vectors for empty texts
            result = [[0.0] * self.dimensions for _ in texts]
            for idx, embedding in zip(non_empty_indices, all_embeddings):
                result[idx] = embedding
            
            return result
            
        except Exception as e:
            raise EmbeddingError(
                f"OpenAI batch embedding failed: {str(e)}",
                provider="openai",
                model=self._model,
            ) from e
    
    def __repr__(self) -> str:
        return f"OpenAIEmbeddingProvider(model={self._model!r}, dimensions={self.dimensions})"
