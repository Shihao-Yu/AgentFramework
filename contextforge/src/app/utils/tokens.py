"""
Token counting utilities for LLM context management.

Provides efficient token counting using tiktoken with caching.
Supports multiple models and encodings.

Usage:
    counter = TokenCounter()
    count = counter.count("Hello, world!")
    truncated = counter.truncate("Long text...", max_tokens=100)
"""

import logging
from functools import lru_cache
from typing import List, Optional

logger = logging.getLogger(__name__)

# Try to import tiktoken
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning(
        "tiktoken not installed. Token counting will use approximation. "
        "Install with: pip install tiktoken"
    )


# Approximate tokens per character for fallback
APPROX_CHARS_PER_TOKEN = 4


@lru_cache(maxsize=16)
def _get_encoding(model: str) -> Optional["tiktoken.Encoding"]:
    """
    Get cached encoding for a model.
    
    Args:
        model: Model name (e.g., "gpt-4", "gpt-3.5-turbo")
        
    Returns:
        tiktoken Encoding object, or None if tiktoken not available
    """
    if not TIKTOKEN_AVAILABLE:
        return None
    
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        # Model not found - use appropriate fallback
        if "gpt-4o" in model:
            return tiktoken.get_encoding("o200k_base")
        elif "gpt-4" in model or "gpt-3.5" in model:
            return tiktoken.get_encoding("cl100k_base")
        else:
            # Default to cl100k_base (most common)
            return tiktoken.get_encoding("cl100k_base")


class TokenCounter:
    """
    Production-ready token counter with caching.
    
    Features:
    - Model-specific encoding selection
    - LRU caching for encodings
    - Fallback to character-based approximation
    - Text truncation by token count
    - Text chunking by token count
    
    Example:
        counter = TokenCounter(default_model="gpt-4")
        
        # Count tokens
        count = counter.count("Hello, world!")
        
        # Truncate to fit context
        truncated = counter.truncate(long_text, max_tokens=4000)
        
        # Chunk for processing
        chunks = counter.chunk(long_text, chunk_size=1000, overlap=100)
    """
    
    def __init__(
        self,
        default_model: str = "gpt-4",
        approx_chars_per_token: float = APPROX_CHARS_PER_TOKEN,
    ):
        """
        Initialize token counter.
        
        Args:
            default_model: Default model for encoding selection
            approx_chars_per_token: Approximation ratio when tiktoken unavailable
        """
        self.default_model = default_model
        self.approx_chars_per_token = approx_chars_per_token
        
        # Validate tiktoken availability
        if TIKTOKEN_AVAILABLE:
            # Pre-warm cache for default model
            _get_encoding(default_model)
    
    @property
    def is_exact(self) -> bool:
        """Whether token counting is exact (tiktoken) or approximate."""
        return TIKTOKEN_AVAILABLE
    
    def count(self, text: str, model: Optional[str] = None) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to count tokens for
            model: Model to use for encoding (default: default_model)
            
        Returns:
            Number of tokens
        """
        if not text:
            return 0
        
        model = model or self.default_model
        encoding = _get_encoding(model)
        
        if encoding:
            return len(encoding.encode(text))
        
        # Fallback: approximate by character count
        return int(len(text) / self.approx_chars_per_token)
    
    def count_messages(
        self,
        messages: List[dict],
        model: Optional[str] = None,
    ) -> int:
        """
        Count tokens in chat messages including formatting overhead.
        
        Args:
            messages: List of message dicts with "role" and "content"
            model: Model to use for encoding
            
        Returns:
            Total token count including overhead
        """
        model = model or self.default_model
        encoding = _get_encoding(model)
        
        # Overhead per message varies by model
        tokens_per_message = 3
        tokens_per_name = 1
        
        total = 0
        
        for message in messages:
            total += tokens_per_message
            
            for key, value in message.items():
                if encoding:
                    total += len(encoding.encode(str(value)))
                else:
                    total += int(len(str(value)) / self.approx_chars_per_token)
                
                if key == "name":
                    total += tokens_per_name
        
        # Reply priming
        total += 3
        
        return total
    
    def truncate(
        self,
        text: str,
        max_tokens: int,
        model: Optional[str] = None,
        suffix: str = "...",
    ) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed
            model: Model to use for encoding
            suffix: Suffix to add when truncating (default: "...")
            
        Returns:
            Truncated text (unchanged if already within limit)
        """
        if not text:
            return text
        
        model = model or self.default_model
        encoding = _get_encoding(model)
        
        if encoding:
            tokens = encoding.encode(text)
            
            if len(tokens) <= max_tokens:
                return text
            
            # Reserve space for suffix
            suffix_tokens = len(encoding.encode(suffix)) if suffix else 0
            truncate_at = max(0, max_tokens - suffix_tokens)
            
            truncated = encoding.decode(tokens[:truncate_at])
            return truncated + suffix if suffix else truncated
        
        # Fallback: approximate truncation
        max_chars = int(max_tokens * self.approx_chars_per_token)
        
        if len(text) <= max_chars:
            return text
        
        suffix_chars = len(suffix) if suffix else 0
        truncate_at = max(0, max_chars - suffix_chars)
        
        return text[:truncate_at] + suffix if suffix else text[:truncate_at]
    
    def chunk(
        self,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 100,
        model: Optional[str] = None,
    ) -> List[str]:
        """
        Split text into chunks by token count with overlap.
        
        Args:
            text: Text to chunk
            chunk_size: Target tokens per chunk
            overlap: Overlap tokens between chunks
            model: Model to use for encoding
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        model = model or self.default_model
        encoding = _get_encoding(model)
        
        if encoding:
            tokens = encoding.encode(text)
            
            if len(tokens) <= chunk_size:
                return [text]
            
            chunks = []
            start = 0
            
            while start < len(tokens):
                end = start + chunk_size
                chunk_tokens = tokens[start:end]
                chunks.append(encoding.decode(chunk_tokens))
                
                # Move start forward, accounting for overlap
                start = end - overlap
                if start <= chunks[-1] if chunks else 0:
                    start = end  # Prevent infinite loop
            
            return chunks
        
        # Fallback: character-based chunking
        char_chunk_size = int(chunk_size * self.approx_chars_per_token)
        char_overlap = int(overlap * self.approx_chars_per_token)
        
        if len(text) <= char_chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + char_chunk_size
            chunks.append(text[start:end])
            start = end - char_overlap
            if start <= 0:
                start = end
        
        return chunks
    
    def fits_context(
        self,
        text: str,
        max_tokens: int,
        model: Optional[str] = None,
    ) -> bool:
        """
        Check if text fits within token limit.
        
        Args:
            text: Text to check
            max_tokens: Maximum tokens allowed
            model: Model to use for encoding
            
        Returns:
            True if text fits, False otherwise
        """
        return self.count(text, model) <= max_tokens
    
    def remaining_tokens(
        self,
        used_tokens: int,
        max_tokens: int,
    ) -> int:
        """
        Calculate remaining tokens in context window.
        
        Args:
            used_tokens: Tokens already used
            max_tokens: Total context window size
            
        Returns:
            Remaining tokens (minimum 0)
        """
        return max(0, max_tokens - used_tokens)


# Default singleton for convenience
_default_counter: Optional[TokenCounter] = None


def get_token_counter(model: str = "gpt-4") -> TokenCounter:
    """
    Get or create default token counter.
    
    Args:
        model: Default model for encoding
        
    Returns:
        TokenCounter instance
    """
    global _default_counter
    if _default_counter is None:
        _default_counter = TokenCounter(default_model=model)
    return _default_counter


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Convenience function to count tokens.
    
    Args:
        text: Text to count
        model: Model to use for encoding
        
    Returns:
        Token count
    """
    return get_token_counter(model).count(text, model)
