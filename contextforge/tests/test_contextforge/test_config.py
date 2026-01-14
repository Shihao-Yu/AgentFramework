"""Tests for ContextForgeConfig."""

import pytest
from pydantic import ValidationError
from contextforge.core.config import ContextForgeConfig


TEST_DB_URL = "postgresql+asyncpg://test:test@testhost/testdb"


class TestContextForgeConfig:

    def test_database_url_required(self):
        """Config should require DATABASE_URL."""
        with pytest.raises(ValidationError):
            ContextForgeConfig()

    def test_default_values(self):
        """Config should have sensible defaults for non-db settings."""
        config = ContextForgeConfig(database_url=TEST_DB_URL)
        
        assert config.db_schema == "agent"
        assert config.db_pool_size == 10
        assert config.db_max_overflow == 20
        assert config.db_echo is False
        assert config.search_bm25_weight == 0.4
        assert config.search_vector_weight == 0.6
        assert config.admin_ui_enabled is True

    def test_custom_values(self):
        """Config should accept custom values."""
        config = ContextForgeConfig(
            database_url=TEST_DB_URL,
            db_schema="custom_schema",
            db_pool_size=20,
            admin_ui_enabled=False,
        )
        
        assert config.db_schema == "custom_schema"
        assert config.db_pool_size == 20
        assert config.admin_ui_enabled is False

    def test_cors_origins_list(self):
        """cors_origins should be parsed into list."""
        config = ContextForgeConfig(
            database_url=TEST_DB_URL,
            cors_origins="http://app.example.com,http://admin.example.com",
        )
        
        assert config.cors_origins_list == [
            "http://app.example.com",
            "http://admin.example.com",
        ]

    def test_env_variable_loading(self, monkeypatch):
        """Config should load DATABASE_URL from env."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://envhost/envdb")
        
        config = ContextForgeConfig()
        
        assert config.database_url == "postgresql+asyncpg://envhost/envdb"

    def test_sync_url_auto_converted(self):
        """postgresql:// should auto-convert to postgresql+asyncpg://"""
        config = ContextForgeConfig(database_url="postgresql://host/db")
        
        assert config.database_url == "postgresql+asyncpg://host/db"
