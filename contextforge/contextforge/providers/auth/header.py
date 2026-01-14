"""
Header-based Auth Provider

Trusts user/tenant information from HTTP headers.
Suitable for use behind an auth gateway.
"""

from fastapi import Request
from contextforge.protocols.auth import AuthContext


class HeaderAuthProvider:
    """
    Auth provider that reads user info from HTTP headers.
    
    Use this when your app is behind an auth gateway/proxy
    that sets user headers after authentication.
    
    Args:
        user_id_header: Header containing user ID (default: "X-User-ID")
        tenant_id_header: Header containing tenant ID (default: "X-Tenant-ID")
        roles_header: Header containing comma-separated roles (default: "X-User-Roles")
        admin_role: Role name that grants admin access (default: "admin")
        default_tenant: Default tenant if header missing (default: "default")
    
    Example:
        # Request headers:
        # X-User-ID: user123
        # X-Tenant-ID: acme
        # X-User-Roles: editor,viewer
        
        provider = HeaderAuthProvider()
        user = await provider.get_current_user(request)
        # user.user_id == "user123"
        # user.tenant_ids == ["acme"]
        # user.roles == ["editor", "viewer"]
    """
    
    def __init__(
        self,
        user_id_header: str = "X-User-ID",
        tenant_id_header: str = "X-Tenant-ID",
        roles_header: str = "X-User-Roles",
        admin_role: str = "admin",
        default_tenant: str = "default",
    ):
        self.user_id_header = user_id_header
        self.tenant_id_header = tenant_id_header
        self.roles_header = roles_header
        self.admin_role = admin_role
        self.default_tenant = default_tenant
    
    async def get_current_user(self, request: Request) -> AuthContext:
        """Extract user context from request headers."""
        user_id = request.headers.get(self.user_id_header, "anonymous")
        tenant_id = request.headers.get(self.tenant_id_header, self.default_tenant)
        roles_str = request.headers.get(self.roles_header, "")
        
        roles = [r.strip() for r in roles_str.split(",") if r.strip()]
        is_admin = self.admin_role in roles
        
        return AuthContext(
            user_id=user_id,
            tenant_ids=[tenant_id],
            roles=roles,
            is_admin=is_admin,
        )
    
    async def check_tenant_access(
        self,
        user: AuthContext,
        tenant_id: str,
    ) -> bool:
        """Check if user can access tenant."""
        return user.can_access_tenant(tenant_id)
