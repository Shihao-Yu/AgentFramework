"""Registry settings."""

from pydantic_settings import SettingsConfigDict

from agentcore.settings.base import BaseAppSettings


class RegistrySettings(BaseAppSettings):
    """Settings for agent registry."""

    model_config = SettingsConfigDict(env_prefix="REGISTRY_")

    redis_url: str = "redis://localhost:6379/0"
    key_prefix: str = "agentcore:agents"
    heartbeat_interval_seconds: int = 10
    agent_ttl_seconds: int = 30

    # Vector search
    embedding_dimension: int = 1536
    discovery_top_k: int = 5
