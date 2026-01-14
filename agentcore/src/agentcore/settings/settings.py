"""Aggregated settings for AgentCore."""

from functools import lru_cache
from typing import Optional

from agentcore.settings.agent import AgentSettings
from agentcore.settings.auth import AuthSettings
from agentcore.settings.embedding import EmbeddingSettings
from agentcore.settings.inference import InferenceSettings
from agentcore.settings.knowledge import KnowledgeSettings
from agentcore.settings.orchestrator import OrchestratorSettings
from agentcore.settings.registry import RegistrySettings
from agentcore.settings.session import SessionSettings
from agentcore.settings.tracing import TracingSettings


class Settings:
    """Aggregated settings for all AgentCore components."""

    def __init__(
        self,
        agent: Optional[AgentSettings] = None,
        auth: Optional[AuthSettings] = None,
        embedding: Optional[EmbeddingSettings] = None,
        inference: Optional[InferenceSettings] = None,
        knowledge: Optional[KnowledgeSettings] = None,
        orchestrator: Optional[OrchestratorSettings] = None,
        registry: Optional[RegistrySettings] = None,
        session: Optional[SessionSettings] = None,
        tracing: Optional[TracingSettings] = None,
    ):
        self.agent = agent or AgentSettings()
        self.auth = auth or AuthSettings()
        self.embedding = embedding or EmbeddingSettings()
        self.inference = inference or InferenceSettings()
        self.knowledge = knowledge or KnowledgeSettings()
        self.orchestrator = orchestrator or OrchestratorSettings()
        self.registry = registry or RegistrySettings()
        self.session = session or SessionSettings()
        self.tracing = tracing or TracingSettings()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
