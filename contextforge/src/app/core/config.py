"""
Application configuration settings.

Uses pydantic-settings for environment variable management.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
    
    # Application
    APP_NAME: str = "Knowledge Base API"
    DEBUG: bool = False
    API_PREFIX: str = "/api"
    
    # Database
    FRAMEWORK_DB_URL: str = "postgresql+asyncpg://user:password@localhost:5432/knowledge_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_SCHEMA: str = "agent"
    
    # Embedding Configuration
    # Common dimensions by model:
    #   - OpenAI text-embedding-3-small: 1536 (default)
    #   - OpenAI text-embedding-3-large: 3072
    #   - Sentence Transformers (all-MiniLM-L6-v2): 384
    #   - Cohere embed-v3: 1024
    EMBEDDING_DIMENSION: int = 1536
    
    # Search Configuration
    SEARCH_BM25_WEIGHT: float = 0.4
    SEARCH_VECTOR_WEIGHT: float = 0.6
    SEARCH_DEFAULT_LIMIT: int = 10
    
    # QueryForge Execution
    QUERYFORGE_EXECUTION_TIMEOUT: int = 30  # seconds
    QUERYFORGE_MAX_ROWS: int = 1000
    
    # Pipeline Configuration
    PIPELINE_SIMILARITY_SKIP_THRESHOLD: float = 0.95
    PIPELINE_SIMILARITY_VARIANT_THRESHOLD: float = 0.85
    PIPELINE_SIMILARITY_MERGE_THRESHOLD: float = 0.70
    PIPELINE_MIN_BODY_LENGTH: int = 30
    PIPELINE_MIN_CLOSURE_NOTES_LENGTH: int = 30
    PIPELINE_CONFIDENCE_THRESHOLD: float = 0.7
    PIPELINE_SKIP_THRESHOLD: Optional[float] = None
    PIPELINE_VARIANT_THRESHOLD: Optional[float] = None
    PIPELINE_MERGE_THRESHOLD: Optional[float] = None
    
    # Maintenance
    VERSION_RETENTION_DAYS: int = 90
    HIT_RETENTION_DAYS: int = 365
    
    # Redis Sentinel Configuration
    # Set REDIS_SENTINEL_HOSTS to enable Sentinel mode (comma-separated host:port pairs)
    # Example: "sentinel1:26379,sentinel2:26379,sentinel3:26379"
    REDIS_SENTINEL_HOSTS: Optional[str] = None
    REDIS_SENTINEL_MASTER: str = "mymaster"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    # Graph Cache
    GRAPH_CACHE_TTL: int = 300  # seconds (5 minutes)
    GRAPH_CACHE_KEY_PREFIX: str = "contextforge:graph"
    
    # Langfuse
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    
    # CORS (comma-separated list of origins, or "*" for all)
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000"
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_LIMIT: int = 100  # Requests per window
    RATE_LIMIT_DEFAULT_WINDOW: int = 60  # Window in seconds
    RATE_LIMIT_SEARCH_LIMIT: int = 200   # Higher limit for search endpoints
    RATE_LIMIT_WRITE_LIMIT: int = 50     # Lower limit for write operations
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


# Global settings instance
settings = Settings()
