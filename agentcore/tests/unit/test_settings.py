"""Unit tests for settings module."""

import pytest

from agentcore.settings import (
    AgentSettings,
    AuthSettings,
    BaseAppSettings,
    EmbeddingSettings,
    InferenceSettings,
    KnowledgeSettings,
    OrchestratorSettings,
    RegistrySettings,
    SessionSettings,
    Settings,
    TracingSettings,
    get_settings,
)


class TestAgentSettings:

    def test_defaults(self):
        settings = AgentSettings()
        
        assert settings.max_iterations == 10
        assert settings.max_tool_calls_per_iteration == 5
        assert settings.max_context_tokens == 8000
        assert settings.use_compact_results is True
        assert settings.tool_timeout_seconds == 30.0
        assert settings.enable_replanning is True


class TestAuthSettings:

    def test_defaults(self):
        settings = AuthSettings()
        
        assert settings.user_cache_ttl_seconds == 300
        assert settings.token_validation_enabled is True
        assert settings.allow_anonymous is False
        assert settings.default_permissions == []


class TestEmbeddingSettings:

    def test_defaults(self):
        settings = EmbeddingSettings()
        
        assert settings.model == "text-embedding-ada-002"
        assert settings.max_concurrent == 32
        assert settings.timeout_seconds == 30.0


class TestInferenceSettings:

    def test_defaults(self):
        settings = InferenceSettings()
        
        assert settings.default_model == "gpt-4"
        assert settings.max_concurrent == 8
        assert settings.timeout_seconds == 120.0
        assert settings.temperature == 0.7


class TestKnowledgeSettings:

    def test_defaults(self):
        settings = KnowledgeSettings()
        
        assert settings.base_url == "http://localhost:8000"
        assert settings.default_limit == 10
        assert settings.hybrid_search_enabled is True
        assert settings.bm25_weight == 0.3
        assert settings.vector_weight == 0.7


class TestOrchestratorSettings:

    def test_defaults(self):
        settings = OrchestratorSettings()
        
        assert settings.discovery_top_k == 5
        assert settings.use_llm_routing is True
        assert settings.max_parallel_agents == 5


class TestRegistrySettings:

    def test_defaults(self):
        settings = RegistrySettings()
        
        assert settings.key_prefix == "agentcore:agents"
        assert settings.heartbeat_interval_seconds == 10
        assert settings.agent_ttl_seconds == 30
        assert settings.embedding_dimension == 1536


class TestSessionSettings:

    def test_defaults(self):
        settings = SessionSettings()
        
        assert settings.pool_size == 5
        assert settings.max_overflow == 10
        assert settings.session_ttl_hours == 24
        assert settings.max_messages_per_session == 100


class TestTracingSettings:

    def test_defaults(self):
        settings = TracingSettings()
        
        assert settings.host == "https://cloud.langfuse.com"
        assert settings.enabled is True
        assert settings.sample_rate == 1.0
        assert settings.trace_inference is True

    def test_is_configured_false_without_keys(self):
        settings = TracingSettings()
        
        assert settings.is_configured is False

    def test_is_configured_true_with_keys(self):
        settings = TracingSettings(public_key="pk-test", secret_key="sk-test")
        
        assert settings.is_configured is True


class TestSettingsAggregator:

    def test_creates_all_settings(self):
        settings = Settings()
        
        assert isinstance(settings.agent, AgentSettings)
        assert isinstance(settings.auth, AuthSettings)
        assert isinstance(settings.embedding, EmbeddingSettings)
        assert isinstance(settings.inference, InferenceSettings)
        assert isinstance(settings.knowledge, KnowledgeSettings)
        assert isinstance(settings.orchestrator, OrchestratorSettings)
        assert isinstance(settings.registry, RegistrySettings)
        assert isinstance(settings.session, SessionSettings)
        assert isinstance(settings.tracing, TracingSettings)

    def test_accepts_custom_settings(self):
        custom_agent = AgentSettings(max_iterations=20)
        custom_auth = AuthSettings(allow_anonymous=True)
        
        settings = Settings(agent=custom_agent, auth=custom_auth)
        
        assert settings.agent.max_iterations == 20
        assert settings.auth.allow_anonymous is True
        assert settings.inference.default_model == "gpt-4"


class TestGetSettings:

    def test_returns_settings(self):
        settings = get_settings()
        
        assert isinstance(settings, Settings)

    def test_returns_cached_instance(self):
        s1 = get_settings()
        s2 = get_settings()
        
        assert s1 is s2
