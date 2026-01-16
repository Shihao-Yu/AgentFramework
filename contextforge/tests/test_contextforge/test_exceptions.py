"""Tests for ContextForge exceptions."""

import pytest
from contextforge.core.exceptions import (
    ContextForgeError,
    ConfigurationError,
    DatabaseError,
    TenantNotFoundError,
    NodeNotFoundError,
    EmbeddingError,
    AuthenticationError,
    AuthorizationError,
)


class TestExceptionHierarchy:

    def test_base_exception(self):
        error = ContextForgeError("test error")
        assert str(error) == "test error"
        assert isinstance(error, Exception)

    def test_configuration_error(self):
        error = ConfigurationError("Invalid config", config_key="framework_db_url")
        assert "Invalid config" in str(error)
        assert error.config_key == "framework_db_url"
        assert isinstance(error, ContextForgeError)

    def test_database_error(self):
        error = DatabaseError("Connection failed", operation="connect")
        assert "Connection failed" in str(error)
        assert error.operation == "connect"
        assert isinstance(error, ContextForgeError)

    def test_tenant_not_found_error(self):
        error = TenantNotFoundError("Tenant not found", tenant_id="tenant-123")
        assert error.tenant_id == "tenant-123"
        assert isinstance(error, ContextForgeError)

    def test_node_not_found_error(self):
        error = NodeNotFoundError("Node not found", node_id="node-456")
        assert error.node_id == "node-456"
        assert isinstance(error, ContextForgeError)

    def test_embedding_error(self):
        error = EmbeddingError(
            "Embedding failed",
            provider="openai",
            model="text-embedding-3-small",
        )
        assert error.provider == "openai"
        assert error.model == "text-embedding-3-small"
        assert isinstance(error, ContextForgeError)

    def test_authentication_error(self):
        error = AuthenticationError("Invalid token")
        assert "Invalid token" in str(error)
        assert isinstance(error, ContextForgeError)

    def test_authorization_error(self):
        error = AuthorizationError("Access denied", tenant_id="tenant-789")
        assert error.tenant_id == "tenant-789"
        assert isinstance(error, ContextForgeError)
