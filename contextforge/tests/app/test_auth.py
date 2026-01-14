"""
Tests for authentication flows in ContextForge.

Tests cover:
- No-auth mode (development)
- Header-based auth (API gateway)
- JWT auth placeholder
- Tenant ID extraction
- Required auth enforcement
"""

import pytest
from unittest.mock import patch
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_current_user,
    get_current_user_id,
    get_current_user_required,
    get_user_tenant_ids,
)


@pytest.fixture
def app():
    """Create a test FastAPI app with auth endpoints."""
    app = FastAPI()
    
    @app.get("/user")
    async def get_user_endpoint(user: dict = Depends(get_current_user)):
        return user
    
    @app.get("/user-id")
    async def get_user_id_endpoint(user_id: str = Depends(get_current_user_id)):
        return {"user_id": user_id}
    
    @app.get("/user-required")
    async def get_user_required_endpoint(user: dict = Depends(get_current_user_required)):
        return user
    
    @app.get("/tenants")
    async def get_tenants_endpoint(tenant_ids: list = Depends(get_user_tenant_ids)):
        return {"tenant_ids": tenant_ids}
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestNoAuthMode:
    """Test AUTH_MODE=none (development mode)."""

    def test_anonymous_user_in_none_mode(self, client):
        """Should return dev-user when no headers provided."""
        with patch.dict('os.environ', {'AUTH_MODE': 'none'}):
            response = client.get("/user")
            
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "dev-user"
            assert data["is_authenticated"] is True

    def test_custom_user_in_none_mode(self, client):
        """Should use X-User-ID header when provided."""
        with patch.dict('os.environ', {'AUTH_MODE': 'none'}):
            response = client.get(
                "/user",
                headers={"X-User-ID": "test-user-123"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "test-user-123"
            assert data["is_authenticated"] is True

    def test_custom_tenants_in_none_mode(self, client):
        """Should use X-Tenant-IDs header when provided."""
        with patch.dict('os.environ', {'AUTH_MODE': 'none'}):
            response = client.get(
                "/user",
                headers={
                    "X-User-ID": "test-user",
                    "X-Tenant-IDs": "tenant-a, tenant-b, tenant-c"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["tenant_ids"] == ["tenant-a", "tenant-b", "tenant-c"]


class TestHeaderAuthMode:
    """Test AUTH_MODE=header (API gateway mode)."""

    def test_anonymous_without_headers(self, client):
        """Should return anonymous user when no headers provided."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get("/user")
            
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "anonymous"
            assert data["is_authenticated"] is False

    def test_authenticated_with_user_header(self, client):
        """Should authenticate when X-User-ID provided."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get(
                "/user",
                headers={"X-User-ID": "gateway-user-456"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "gateway-user-456"
            assert data["is_authenticated"] is True

    def test_default_tenants_for_authenticated(self, client):
        """Authenticated users should get default tenants if not specified."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get(
                "/user",
                headers={"X-User-ID": "user-123"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "default" in data["tenant_ids"]
            assert "shared" in data["tenant_ids"]

    def test_custom_tenants_with_header(self, client):
        """Should use X-Tenant-IDs when provided."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get(
                "/user",
                headers={
                    "X-User-ID": "user-123",
                    "X-Tenant-IDs": "org-a,org-b"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["tenant_ids"] == ["org-a", "org-b"]

    def test_tenant_ids_trimmed(self, client):
        """Tenant IDs should be trimmed of whitespace."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get(
                "/user",
                headers={
                    "X-User-ID": "user-123",
                    "X-Tenant-IDs": "  org-a  ,  org-b  ,  org-c  "
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["tenant_ids"] == ["org-a", "org-b", "org-c"]


class TestJWTAuthMode:
    """Test AUTH_MODE=jwt (placeholder - not fully implemented)."""

    def test_jwt_mode_falls_back_to_anonymous(self, client):
        """JWT mode should fall back to anonymous (not implemented)."""
        with patch.dict('os.environ', {'AUTH_MODE': 'jwt'}):
            response = client.get(
                "/user",
                headers={"Authorization": "Bearer fake-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            # JWT not implemented, should fall back to anonymous
            assert data["user_id"] == "anonymous"
            assert data["is_authenticated"] is False


class TestRequiredAuth:
    """Test get_current_user_required dependency."""

    def test_required_auth_rejects_anonymous(self, client):
        """Should return 401 when user is not authenticated."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get("/user-required")
            
            assert response.status_code == 401
            assert "Authentication required" in response.json()["detail"]

    def test_required_auth_accepts_authenticated(self, client):
        """Should accept authenticated user."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get(
                "/user-required",
                headers={"X-User-ID": "valid-user"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "valid-user"
            assert data["is_authenticated"] is True

    def test_required_auth_includes_www_authenticate_header(self, client):
        """401 response should include WWW-Authenticate header."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get("/user-required")
            
            assert response.status_code == 401
            assert "WWW-Authenticate" in response.headers


class TestLegacyUserIdDependency:
    """Test get_current_user_id legacy dependency."""

    def test_returns_user_id_string(self, client):
        """Should return just the user_id string."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get(
                "/user-id",
                headers={"X-User-ID": "legacy-user"}
            )
            
            assert response.status_code == 200
            assert response.json() == {"user_id": "legacy-user"}

    def test_returns_anonymous_when_not_authenticated(self, client):
        """Should return 'anonymous' when not authenticated."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get("/user-id")
            
            assert response.status_code == 200
            assert response.json() == {"user_id": "anonymous"}


class TestTenantIdsDependency:
    """Test get_user_tenant_ids dependency."""

    def test_returns_tenant_ids_list(self, client):
        """Should return list of tenant IDs."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get(
                "/tenants",
                headers={
                    "X-User-ID": "user",
                    "X-Tenant-IDs": "t1,t2,t3"
                }
            )
            
            assert response.status_code == 200
            assert response.json() == {"tenant_ids": ["t1", "t2", "t3"]}

    def test_returns_defaults_when_not_specified(self, client):
        """Should return default tenants when not specified."""
        with patch.dict('os.environ', {'AUTH_MODE': 'header'}):
            response = client.get("/tenants")
            
            assert response.status_code == 200
            tenant_ids = response.json()["tenant_ids"]
            assert "default" in tenant_ids
            assert "shared" in tenant_ids


class TestAuthModeEnvironmentVariable:
    """Test AUTH_MODE environment variable handling."""

    def test_default_auth_mode_is_header(self, client):
        """Default AUTH_MODE should be 'header'."""
        # Clear AUTH_MODE to test default
        with patch.dict('os.environ', {}, clear=True):
            # This should use the default which is 'header' in the code
            response = client.get("/user")
            
            assert response.status_code == 200
            # With no headers and header mode, should be anonymous
            data = response.json()
            assert data["user_id"] == "anonymous"

    def test_invalid_auth_mode_treated_as_header(self, client):
        """Invalid AUTH_MODE should fall back to header behavior."""
        with patch.dict('os.environ', {'AUTH_MODE': 'invalid_mode'}):
            response = client.get("/user")
            
            assert response.status_code == 200
            # Should fall through to return anonymous
            data = response.json()
            assert data["user_id"] == "anonymous"
