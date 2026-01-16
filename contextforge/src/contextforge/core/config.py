"""ContextForge Configuration"""

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ContextForgeConfig(BaseSettings):
    """ContextForge configuration. Sync URLs auto-convert to async."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
    
    framework_db_url: str = Field(
        validation_alias=AliasChoices("FRAMEWORK_DB_URL", "framework_db_url"),
    )
    
    db_schema: str = Field(
        default="agent",
        description="PostgreSQL schema for ContextForge tables",
    )
    
    db_pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Database connection pool size",
    )
    
    db_max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum overflow connections beyond pool_size",
    )
    
    db_echo: bool = Field(
        default=False,
        description="Echo SQL statements (for debugging)",
    )
    
    # ===================
    # Search Settings
    # ===================
    
    search_bm25_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Weight for BM25 (keyword) search in hybrid search",
    )
    
    search_vector_weight: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Weight for vector (semantic) search in hybrid search",
    )
    
    search_default_limit: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Default number of results to return from search",
    )
    
    search_rrf_k: int = Field(
        default=60,
        ge=1,
        description="RRF (Reciprocal Rank Fusion) constant k",
    )
    
    # ===================
    # Admin UI Settings
    # ===================
    
    admin_ui_enabled: bool = Field(
        default=True,
        description="Enable Admin UI at admin_ui_path",
    )
    
    admin_ui_path: str = Field(
        default="/admin",
        description="URL path for Admin UI",
    )
    
    admin_ui_title: str = Field(
        default="ContextForge Admin",
        description="Title shown in Admin UI",
    )
    
    # ===================
    # Feature Flags
    # ===================
    
    enable_queryforge: bool = Field(
        default=True,
        description="Enable QueryForge (NL-to-SQL) features",
    )
    
    enable_staging: bool = Field(
        default=True,
        description="Enable staging/review workflow",
    )
    
    enable_analytics: bool = Field(
        default=True,
        description="Enable usage analytics",
    )
    
    # ===================
    # API Settings
    # ===================
    
    api_prefix: str = Field(
        default="/api",
        description="API route prefix",
    )
    
    cors_origins: str = Field(
        default="*",
        description="Comma-separated list of allowed CORS origins, or '*' for all",
    )
    
    # ===================
    # Validators
    # ===================
    
    @field_validator("framework_db_url")
    @classmethod
    def validate_framework_db_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("framework_db_url must be a PostgreSQL URL")
        if "asyncpg" not in v and "+asyncpg" not in v:
            # Auto-fix sync URL to async
            v = v.replace("postgresql://", "postgresql+asyncpg://")
        return v
    
    @field_validator("search_bm25_weight", "search_vector_weight")
    @classmethod
    def validate_weights(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("Weight must be between 0.0 and 1.0")
        return v
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]
