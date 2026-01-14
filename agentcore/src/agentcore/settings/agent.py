"""Agent settings for behavior configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Settings for agent behavior."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ReAct loop limits
    max_iterations: int = 10
    max_tool_calls_per_iteration: int = 5
    max_context_tokens: int = 8000

    # Result handling
    use_compact_results: bool = True
    max_result_chars: int = 5000

    # Timeouts
    tool_timeout_seconds: float = 30.0
    sub_agent_timeout_seconds: float = 60.0
    total_timeout_seconds: float = 300.0  # 5 minutes

    # Replanning
    enable_replanning: bool = True
    max_replans: int = 3
