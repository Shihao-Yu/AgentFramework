"""Base settings for AgentCore."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    """Base settings with common configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


class EnvironmentSettings(BaseAppSettings):
    """Environment-level settings."""

    model_config = SettingsConfigDict(env_prefix="APP_")

    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
