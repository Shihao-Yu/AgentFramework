"""
Auth Provider Protocol

Implement this protocol to provide custom authentication/authorization.
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from fastapi import Request


@dataclass
class AuthContext:
    """
    Authentication context containing user information.
    
    Attributes:
        email: User's email address (primary identifier)
        tenant_ids: List of tenant IDs the user can access
        roles: User's roles (e.g., ["admin", "editor"])
        is_admin: Whether user has admin privileges
        metadata: Additional user metadata (display_name, etc.)
    """
    email: str
    tenant_ids: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    is_admin: bool = False
    metadata: dict = field(default_factory=dict)
    
    def can_access_tenant(self, tenant_id: str) -> bool:
        """Check if user can access a specific tenant."""
        if self.is_admin:
            return True
        return tenant_id in self.tenant_ids
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        if self.is_admin:
            return True
        return role in self.roles


@runtime_checkable
class AuthProvider(Protocol):
    """
    Protocol for authentication providers.
    
    Implement this to integrate with your auth system
    (JWT, OAuth, API keys, custom, etc.)
    
    Example - Header-based auth:
        class HeaderAuthProvider(AuthProvider):
            async def get_current_user(self, request: Request) -> AuthContext:
                email = request.headers.get("X-User-Email", "anonymous@local")
                tenant_id = request.headers.get("X-Tenant-ID", "default")
                return AuthContext(
                    email=email,
                    tenant_ids=[tenant_id],
                )
            
            async def check_tenant_access(
                self, user: AuthContext, tenant_id: str
            ) -> bool:
                return user.can_access_tenant(tenant_id)
    
    Example - JWT auth:
        class JWTAuthProvider(AuthProvider):
            def __init__(self, secret_key: str):
                self.secret_key = secret_key
            
            async def get_current_user(self, request: Request) -> AuthContext:
                token = request.headers.get("Authorization", "").replace("Bearer ", "")
                if not token:
                    return AuthContext(email="anonymous@local")
                
                payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
                return AuthContext(
                    email=payload.get("email") or payload["sub"],
                    tenant_ids=payload.get("tenants", []),
                    roles=payload.get("roles", []),
                    is_admin="admin" in payload.get("roles", []),
                )
    """
    
    async def get_current_user(self, request: Request) -> AuthContext:
        """
        Extract user information from request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            AuthContext with user information
        """
        ...
    
    async def check_tenant_access(
        self,
        user: AuthContext,
        tenant_id: str,
    ) -> bool:
        """
        Check if user can access a specific tenant.
        
        Args:
            user: Current user context
            tenant_id: Tenant to check access for
            
        Returns:
            True if user can access tenant
        """
        ...
