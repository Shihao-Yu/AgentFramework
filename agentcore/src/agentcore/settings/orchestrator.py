"""Orchestrator settings."""

from pydantic_settings import SettingsConfigDict

from agentcore.settings.base import BaseAppSettings


class OrchestratorSettings(BaseAppSettings):
    """Settings for orchestrator."""

    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_")

    discovery_top_k: int = 5
    use_llm_routing: bool = True
    routing_model: str = "gpt-4"
    max_parallel_agents: int = 5
    agent_timeout: float = 60.0
    fallback_agent: str = "default"
