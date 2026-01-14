"""Tests for ContextForge providers."""

import pytest
from contextforge.providers.embedding.mock import MockEmbeddingProvider
from contextforge.providers.llm.mock import MockLLMProvider
from contextforge.providers.auth.header import HeaderAuthProvider
from contextforge.providers.auth.noop import NoopAuthProvider
from contextforge.protocols.auth import AuthContext


class TestMockEmbeddingProvider:
    """Test MockEmbeddingProvider."""

    def test_dimensions(self):
        """Provider should return correct dimensions."""
        provider = MockEmbeddingProvider(dimensions=384)
        assert provider.dimensions == 384
        
        provider = MockEmbeddingProvider(dimensions=1536)
        assert provider.dimensions == 1536

    @pytest.mark.asyncio
    async def test_embed_single(self):
        """embed() should return vector of correct size."""
        provider = MockEmbeddingProvider(dimensions=384)
        embedding = await provider.embed("test text")
        
        assert isinstance(embedding, list)
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """embed_batch() should return vectors for all inputs."""
        provider = MockEmbeddingProvider(dimensions=384)
        texts = ["text 1", "text 2", "text 3"]
        embeddings = await provider.embed_batch(texts)
        
        assert len(embeddings) == 3
        for emb in embeddings:
            assert len(emb) == 384

    @pytest.mark.asyncio
    async def test_embed_empty(self):
        """embed() should handle empty text."""
        provider = MockEmbeddingProvider(dimensions=384)
        embedding = await provider.embed("")
        
        assert len(embedding) == 384

    @pytest.mark.asyncio
    async def test_embed_batch_empty(self):
        """embed_batch() should handle empty list."""
        provider = MockEmbeddingProvider(dimensions=384)
        embeddings = await provider.embed_batch([])
        
        assert embeddings == []


class TestMockLLMProvider:
    """Test MockLLMProvider."""

    @pytest.mark.asyncio
    async def test_generate(self):
        """generate() should return mock response."""
        provider = MockLLMProvider()
        response = await provider.generate("test prompt")
        
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self):
        """generate() should accept system prompt."""
        provider = MockLLMProvider()
        response = await provider.generate(
            prompt="test prompt",
            system_prompt="You are a helpful assistant",
        )
        
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_generate_json(self):
        """generate_json() should return dict."""
        provider = MockLLMProvider()
        response = await provider.generate_json("Return JSON")
        
        assert isinstance(response, dict)


class TestHeaderAuthProvider:
    """Test HeaderAuthProvider."""

    @pytest.mark.asyncio
    async def test_extract_from_headers(self):
        """Should extract user info from headers."""
        from unittest.mock import MagicMock
        
        provider = HeaderAuthProvider()
        
        request = MagicMock()
        request.headers = {
            "X-User-ID": "user-123",
            "X-Tenant-ID": "tenant-456",
        }
        
        auth = await provider.get_current_user(request)
        
        assert auth.user_id == "user-123"
        assert "tenant-456" in auth.tenant_ids

    @pytest.mark.asyncio
    async def test_default_values(self):
        """Should use defaults when headers missing."""
        from unittest.mock import MagicMock
        
        provider = HeaderAuthProvider(default_tenant="my-tenant")
        
        request = MagicMock()
        request.headers = {}
        
        auth = await provider.get_current_user(request)
        
        assert auth.user_id == "anonymous"
        assert "my-tenant" in auth.tenant_ids

    @pytest.mark.asyncio
    async def test_check_tenant_access(self):
        """Should check tenant access correctly."""
        provider = HeaderAuthProvider()
        
        user = AuthContext(
            user_id="user-1",
            tenant_ids=["tenant-a", "tenant-b"],
        )
        
        assert await provider.check_tenant_access(user, "tenant-a") is True
        assert await provider.check_tenant_access(user, "tenant-c") is False

    @pytest.mark.asyncio
    async def test_admin_access(self):
        """Admin should have access to all tenants."""
        provider = HeaderAuthProvider()
        
        admin = AuthContext(
            user_id="admin",
            tenant_ids=[],
            is_admin=True,
        )
        
        assert await provider.check_tenant_access(admin, "any-tenant") is True


class TestNoopAuthProvider:
    """Test NoopAuthProvider."""

    @pytest.mark.asyncio
    async def test_always_returns_anonymous(self):
        """Should always return anonymous user."""
        from unittest.mock import MagicMock
        
        provider = NoopAuthProvider()
        
        request = MagicMock()
        request.headers = {"X-User-ID": "ignored"}
        
        auth = await provider.get_current_user(request)
        
        assert auth.user_id == "anonymous"
        assert auth.is_admin is True

    @pytest.mark.asyncio
    async def test_always_allows_access(self):
        """Should allow access to any tenant."""
        provider = NoopAuthProvider()
        
        user = AuthContext(user_id="anyone")
        
        assert await provider.check_tenant_access(user, "any-tenant") is True


class TestAuthContext:
    """Test AuthContext dataclass."""

    def test_can_access_tenant(self):
        """can_access_tenant should check tenant_ids."""
        ctx = AuthContext(
            user_id="user-1",
            tenant_ids=["tenant-a", "tenant-b"],
        )
        
        assert ctx.can_access_tenant("tenant-a") is True
        assert ctx.can_access_tenant("tenant-c") is False

    def test_admin_can_access_any_tenant(self):
        """Admin should access any tenant."""
        ctx = AuthContext(
            user_id="admin",
            tenant_ids=[],
            is_admin=True,
        )
        
        assert ctx.can_access_tenant("any-tenant") is True

    def test_has_role(self):
        """has_role should check roles list."""
        ctx = AuthContext(
            user_id="user-1",
            roles=["editor", "viewer"],
        )
        
        assert ctx.has_role("editor") is True
        assert ctx.has_role("admin") is False

    def test_admin_has_all_roles(self):
        """Admin should have all roles."""
        ctx = AuthContext(
            user_id="admin",
            roles=[],
            is_admin=True,
        )
        
        assert ctx.has_role("any-role") is True
