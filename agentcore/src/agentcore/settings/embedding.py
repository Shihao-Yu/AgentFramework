"""Embedding settings."""

from pydantic_settings import SettingsConfigDict

from agentcore.settings.base import BaseAppSettings


class EmbeddingSettings(BaseAppSettings):
    """Settings for embedding service."""

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_")

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "text-embedding-ada-002"
    dimension: int = 1536
    max_concurrent: int = 32
    timeout_seconds: float = 30.0
