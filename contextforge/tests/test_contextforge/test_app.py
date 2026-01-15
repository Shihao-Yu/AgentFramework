"""Tests for ContextForge main application class."""

import pytest
from unittest.mock import patch

from contextforge import ContextForge, ContextForgeConfig
from contextforge.core.exceptions import ConfigurationError
from contextforge.providers.embedding.mock import MockEmbeddingProvider
from contextforge.providers.auth.noop import NoopAuthProvider


TEST_DB_URL = "postgresql+asyncpg://test:test@testhost:5432/testdb"


class TestContextForgeInit:

    def test_init_requires_embedding_provider_or_sentence_transformers(self):
        """Should raise if no embedding provider and sentence-transformers not installed."""
        with patch.dict('sys.modules', {'sentence_transformers': None}):
            with patch('contextforge.core.app.SentenceTransformersProvider') as mock:
                mock.side_effect = ImportError("not installed")
                with pytest.raises(ConfigurationError) as exc_info:
                    ContextForge(database_url=TEST_DB_URL)
                assert "embedding_provider" in str(exc_info.value)

    def test_init_with_custom_providers(self):
        """Should accept custom providers."""
        embedding = MockEmbeddingProvider(dimensions=768)
        auth = NoopAuthProvider()
        
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=embedding,
            auth_provider=auth,
        )
        
        assert cf.embedding_provider is embedding
        assert cf.auth_provider is auth

    def test_init_with_config(self):
        """Should accept full config object."""
        embedding = MockEmbeddingProvider()
        config = ContextForgeConfig(database_url=TEST_DB_URL, db_schema="custom")
        
        cf = ContextForge(config=config, embedding_provider=embedding)
        
        assert cf.config.db_schema == "custom"


class TestContextForgeRouter:

    def test_router_property(self):
        """Should return APIRouter."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        from fastapi import APIRouter
        assert isinstance(cf.router, APIRouter)

    def test_router_cached(self):
        """Router should be cached."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        assert cf.router is cf.router


class TestContextForgeApp:

    def test_app_property(self):
        """Should return FastAPI app."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        from fastapi import FastAPI
        assert isinstance(cf.app, FastAPI)

    def test_app_cached(self):
        """App should be cached."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        assert cf.app is cf.app


class TestContextForgeDatabase:

    def test_engine_property(self):
        """Should create async engine."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        from sqlalchemy.ext.asyncio import AsyncEngine
        assert isinstance(cf.engine, AsyncEngine)

    def test_engine_cached(self):
        """Engine should be cached."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        assert cf.engine is cf.engine

    @pytest.mark.asyncio
    async def test_dispose(self):
        """dispose() should cleanup engine."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        _ = cf.engine
        assert cf._engine is not None
        
        await cf.dispose()
        
        assert cf._engine is None


class TestContextForgeDependencies:

    def test_get_current_user_returns_depends(self):
        """get_current_user should return Depends object."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        from fastapi.params import Depends as DependsClass
        assert isinstance(cf.get_current_user(), DependsClass)

    def test_require_tenant_access_returns_depends(self):
        """require_tenant_access should return Depends object."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        from fastapi.params import Depends as DependsClass
        assert isinstance(cf.require_tenant_access(), DependsClass)


class TestContextForgeGetContext:

    def test_get_context_requires_query_or_request(self):
        """get_context should raise if neither query nor request provided."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        with pytest.raises(ValueError) as exc_info:
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                cf.get_context(tenant_ids=["test"])
            )
        assert "query" in str(exc_info.value)

    def test_get_context_requires_tenant_ids_or_request(self):
        """get_context should raise if neither tenant_ids nor request provided."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        with pytest.raises(ValueError) as exc_info:
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                cf.get_context(query="test query")
            )
        assert "tenant_ids" in str(exc_info.value)

    def test_get_context_method_exists(self):
        """get_context method should exist on ContextForge."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        assert hasattr(cf, 'get_context')
        assert callable(cf.get_context)

    def test_get_context_is_async(self):
        """get_context should be an async method."""
        cf = ContextForge(
            database_url=TEST_DB_URL,
            embedding_provider=MockEmbeddingProvider(),
        )
        
        import asyncio
        assert asyncio.iscoroutinefunction(cf.get_context)
