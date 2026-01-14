"""Tracing settings for Langfuse integration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class TracingSettings(BaseSettings):
    """Settings for Langfuse tracing."""

    model_config = SettingsConfigDict(
        env_prefix="LANGFUSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Langfuse credentials
    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"

    # Feature flags
    enabled: bool = True
    sample_rate: float = 1.0  # 0.0 to 1.0

    # What to trace
    trace_inference: bool = True
    trace_tools: bool = True
    trace_knowledge: bool = True
    trace_decisions: bool = True

    # Content limits
    max_content_length: int = 10000  # Truncate long content

    @property
    def is_configured(self) -> bool:
        """Check if Langfuse credentials are configured."""
        return bool(self.public_key and self.secret_key)
