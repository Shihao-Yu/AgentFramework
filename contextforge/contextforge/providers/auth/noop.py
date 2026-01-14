"""
No-op Auth Provider

Allows all access without authentication.
FOR DEVELOPMENT/TESTING ONLY.
"""

from fastapi import Request
from contextforge.protocols.auth import AuthContext


class NoopAuthProvider:
    """
    Auth provider that allows all access.
    
    WARNING: Use only for development and testing!
    
    All requests are treated as admin with access to all tenants.
    
    Args:
        default_user_id: User ID to use (default: "dev-user")
        default_tenant_id: Tenant ID to use (default: "default")
    
    Example:
        provider = NoopAuthProvider()
        user = await provider.get_current_user(request)
        # user.is_admin == True
        # user.can_access_tenant("any-tenant") == True
    """
    
    def __init__(
        self,
        default_user_id: str = "dev-user",
        default_tenant_id: str = "default",
    ):
        self.default_user_id = default_user_id
        self.default_tenant_id = default_tenant_id
    
    async def get_current_user(self, request: Request) -> AuthContext:
        """Return admin context for all requests."""
        return AuthContext(
            user_id=self.default_user_id,
            tenant_ids=[self.default_tenant_id],
            roles=["admin"],
            is_admin=True,
        )
    
    async def check_tenant_access(
        self,
        user: AuthContext,
        tenant_id: str,
    ) -> bool:
        """Always return True."""
        return True
