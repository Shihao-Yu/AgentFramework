"""
SentenceTransformers Embedding Provider (Default)

Uses local SentenceTransformers models for embedding generation.
Works offline without API keys.
"""

from typing import Optional
import asyncio
from functools import partial


class SentenceTransformersProvider:
    """
    Embedding provider using SentenceTransformers.
    
    This is the default provider - works offline without API keys.
    
    Args:
        model_name: Model to use (default: "all-MiniLM-L6-v2")
        device: Device to run on ("cpu", "cuda", "mps")
        normalize: Whether to normalize embeddings (default: True)
    
    Popular models:
        - "all-MiniLM-L6-v2": 384 dims, fast, good quality (default)
        - "all-mpnet-base-v2": 768 dims, better quality, slower
        - "multi-qa-MiniLM-L6-cos-v1": 384 dims, optimized for Q&A
    
    Example:
        provider = SentenceTransformersProvider()
        embedding = await provider.embed("Hello world")
        print(len(embedding))  # 384
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
        normalize: bool = True,
    ):
        self.model_name = model_name
        self.device = device
        self.normalize = normalize
        self._model = None
        self._dimensions: Optional[int] = None
    
    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for SentenceTransformersProvider. "
                    "Install with: pip install sentence-transformers"
                )
            
            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
            )
            # Get dimensions from a test embedding
            test_embedding = self._model.encode("test", normalize_embeddings=self.normalize)
            self._dimensions = len(test_embedding)
        return self._model
    
    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        if self._dimensions is None:
            self._load_model()
        return self._dimensions
    
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        model = self._load_model()
        
        # Run in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            partial(model.encode, text, normalize_embeddings=self.normalize),
        )
        return embedding.tolist()
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []
        
        model = self._load_model()
        
        # Run in thread pool
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            partial(
                model.encode,
                texts,
                normalize_embeddings=self.normalize,
                show_progress_bar=False,
            ),
        )
        return [emb.tolist() for emb in embeddings]
