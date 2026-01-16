"""Pytest fixtures for ContextForge tests."""

import pytest


TEST_FRAMEWORK_DB_URL = "postgresql+asyncpg://test:test@testhost:5432/testdb"


@pytest.fixture
def mock_framework_db_url():
    """Provide a test database URL."""
    return TEST_FRAMEWORK_DB_URL


@pytest.fixture
def basic_config(mock_framework_db_url):
    """Provide a basic ContextForgeConfig."""
    from contextforge import ContextForgeConfig
    return ContextForgeConfig(framework_db_url=mock_framework_db_url)


@pytest.fixture
def mock_embedding_provider():
    """Provide a mock embedding provider."""
    from contextforge.providers.embedding.mock import MockEmbeddingProvider
    return MockEmbeddingProvider(dimensions=384)


@pytest.fixture
def mock_llm_provider():
    """Provide a mock LLM provider."""
    from contextforge.providers.llm.mock import MockLLMProvider
    return MockLLMProvider()


@pytest.fixture
def noop_auth_provider():
    """Provide a no-op auth provider."""
    from contextforge.providers.auth.noop import NoopAuthProvider
    return NoopAuthProvider()


@pytest.fixture
def contextforge_instance(mock_framework_db_url, mock_embedding_provider, noop_auth_provider):
    """Provide a configured ContextForge instance."""
    from contextforge import ContextForge
    return ContextForge(
        framework_db_url=mock_framework_db_url,
        embedding_provider=mock_embedding_provider,
        auth_provider=noop_auth_provider,
    )
