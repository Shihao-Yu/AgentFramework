"""Knowledge settings for ContextForge integration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class KnowledgeSettings(BaseSettings):
    """Settings for ContextForge knowledge retrieval."""

    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ContextForge API connection
    base_url: str = "http://localhost:8000"
    timeout_seconds: float = 30.0

    # Search defaults
    default_limit: int = 10
    max_limit: int = 50

    # Hybrid search weights
    hybrid_search_enabled: bool = True
    bm25_weight: float = 0.3
    vector_weight: float = 0.7

    # Caching
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes

    # Content limits
    max_content_length: int = 10000  # Truncate long content in bundles
