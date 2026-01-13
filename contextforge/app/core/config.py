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
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/knowledge_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_SCHEMA: str = "agent"
    
    # Search Configuration
    SEARCH_BM25_WEIGHT: float = 0.4
    SEARCH_VECTOR_WEIGHT: float = 0.6
    SEARCH_DEFAULT_LIMIT: int = 10
    
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
    
    # CORS (comma-separated list of origins, or "*" for all)
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000"
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


# Global settings instance
settings = Settings()
