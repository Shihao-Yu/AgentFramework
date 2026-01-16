import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_current_user,
    get_current_user_email,
    get_current_user_required,
    get_user_tenant_ids,
)


@pytest.fixture
def app():
    test_app = FastAPI()
    
    @test_app.get("/user")
    async def get_user_endpoint(user: dict = Depends(get_current_user)):
        return user
    
    @test_app.get("/user-email")
    async def get_user_email_endpoint(email: str = Depends(get_current_user_email)):
        return {"email": email}
    
    @test_app.get("/user-required")
    async def get_user_required_endpoint(user: dict = Depends(get_current_user_required)):
        return user
    
    @test_app.get("/tenants")
    async def get_tenants_endpoint(tenant_ids: list = Depends(get_user_tenant_ids)):
        return {"tenant_ids": tenant_ids}
    
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestUnauthenticatedRequests:

    def test_returns_anonymous_without_token(self, client):
        response = client.get("/user")
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "anonymous@local"
        assert data["is_authenticated"] is False
        assert "default" in data["tenant_ids"]
        assert "shared" in data["tenant_ids"]

    def test_returns_anonymous_with_invalid_auth_header(self, client):
        response = client.get("/user", headers={"Authorization": "InvalidFormat"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "anonymous@local"
        assert data["is_authenticated"] is False


class TestJWKSAuthentication:

    def test_valid_token_authenticates_user(self, client):
        mock_result = MagicMock()
        mock_result.email = "user@example.com"
        mock_result.display_name = "Test User"
        mock_result.groups = ["tenant-a", "tenant-b"]
        mock_result.roles = ["editor"]
        
        mock_provider = MagicMock()
        mock_provider.validate_token = AsyncMock(return_value=mock_result)
        
        with patch("app.core.dependencies._get_jwks_auth_provider", return_value=mock_provider):
            response = client.get(
                "/user",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["display_name"] == "Test User"
        assert data["tenant_ids"] == ["tenant-a", "tenant-b"]
        assert data["roles"] == ["editor"]
        assert data["is_authenticated"] is True

    def test_uses_default_tenant_when_no_groups(self, client):
        mock_result = MagicMock()
        mock_result.email = "user@example.com"
        mock_result.display_name = "Test User"
        mock_result.groups = None
        mock_result.roles = []
        
        mock_provider = MagicMock()
        mock_provider.validate_token = AsyncMock(return_value=mock_result)
        
        with patch("app.core.dependencies._get_jwks_auth_provider", return_value=mock_provider):
            response = client.get(
                "/user",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_ids"] == ["default"]

    def test_invalid_token_returns_anonymous(self, client):
        mock_provider = MagicMock()
        mock_provider.validate_token = AsyncMock(side_effect=Exception("Invalid token"))
        
        with patch("app.core.dependencies._get_jwks_auth_provider", return_value=mock_provider):
            response = client.get(
                "/user",
                headers={"Authorization": "Bearer invalid-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "anonymous@local"
        assert data["is_authenticated"] is False


class TestRequiredAuth:

    def test_rejects_unauthenticated_requests(self, client):
        response = client.get("/user-required")
        
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

    def test_includes_www_authenticate_header(self, client):
        response = client.get("/user-required")
        
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

    def test_accepts_authenticated_requests(self, client):
        mock_result = MagicMock()
        mock_result.email = "user@example.com"
        mock_result.display_name = "Test User"
        mock_result.groups = ["tenant-a"]
        mock_result.roles = ["viewer"]
        
        mock_provider = MagicMock()
        mock_provider.validate_token = AsyncMock(return_value=mock_result)
        
        with patch("app.core.dependencies._get_jwks_auth_provider", return_value=mock_provider):
            response = client.get(
                "/user-required",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["is_authenticated"] is True


class TestUserEmailDependency:

    def test_returns_email_string(self, client):
        mock_result = MagicMock()
        mock_result.email = "user@example.com"
        mock_result.display_name = "Test User"
        mock_result.groups = ["tenant-a"]
        mock_result.roles = []
        
        mock_provider = MagicMock()
        mock_provider.validate_token = AsyncMock(return_value=mock_result)
        
        with patch("app.core.dependencies._get_jwks_auth_provider", return_value=mock_provider):
            response = client.get(
                "/user-email",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 200
        assert response.json() == {"email": "user@example.com"}

    def test_returns_anonymous_when_unauthenticated(self, client):
        response = client.get("/user-email")
        
        assert response.status_code == 200
        assert response.json() == {"email": "anonymous@local"}


class TestTenantIdsDependency:

    def test_returns_tenant_ids_from_token(self, client):
        mock_result = MagicMock()
        mock_result.email = "user@example.com"
        mock_result.display_name = "Test User"
        mock_result.groups = ["t1", "t2", "t3"]
        mock_result.roles = []
        
        mock_provider = MagicMock()
        mock_provider.validate_token = AsyncMock(return_value=mock_result)
        
        with patch("app.core.dependencies._get_jwks_auth_provider", return_value=mock_provider):
            response = client.get(
                "/tenants",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 200
        assert response.json() == {"tenant_ids": ["t1", "t2", "t3"]}

    def test_returns_defaults_when_unauthenticated(self, client):
        response = client.get("/tenants")
        
        assert response.status_code == 200
        tenant_ids = response.json()["tenant_ids"]
        assert "default" in tenant_ids
        assert "shared" in tenant_ids
