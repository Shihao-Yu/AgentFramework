"""Inference settings."""

from pydantic_settings import SettingsConfigDict

from agentcore.settings.base import BaseAppSettings


class InferenceSettings(BaseAppSettings):
    """Settings for inference service."""

    model_config = SettingsConfigDict(env_prefix="INFERENCE_")

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    default_model: str = "gpt-4"
    max_concurrent: int = 8
    timeout_seconds: float = 120.0
    temperature: float = 0.7
    max_tokens: int = 4096
    max_retries: int = 3
