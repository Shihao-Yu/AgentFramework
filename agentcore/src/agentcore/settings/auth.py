"""Auth settings for authentication configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """Settings for authentication and authorization."""

    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    user_cache_ttl_seconds: int = 300
    token_validation_enabled: bool = True
    allow_anonymous: bool = False
    default_permissions: list[str] = []
