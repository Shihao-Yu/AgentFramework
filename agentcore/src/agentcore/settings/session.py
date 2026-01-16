"""Session settings for AgentCore."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class SessionSettings(BaseSettings):
    """Settings for session persistence."""

    model_config = SettingsConfigDict(env_prefix="SESSION_")

    framework_db_url: str = "postgresql+asyncpg://localhost:5432/agent_sessions"
    db_schema: str = "agent"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: float = 30.0
    session_ttl_hours: int = 24
    max_messages_per_session: int = 100
    echo_sql: bool = False
