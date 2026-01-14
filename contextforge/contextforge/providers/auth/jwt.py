"""
JWT Auth Provider

Validates JWT tokens for authentication.

Installation:
    pip install contextforge[jwt]
    # or
    pip install pyjwt

Usage:
    from contextforge.providers.auth import JWTAuthProvider
    
    provider = JWTAuthProvider(
        secret_key="your-secret-key",
        algorithms=["HS256"],
    )
    
    cf = ContextForge(
        database_url="...",
        auth_provider=provider,
    )
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Request

from contextforge.protocols.auth import AuthContext
from contextforge.core.exceptions import AuthenticationError, ConfigurationError


class JWTAuthProvider:
    """
    JWT token authentication provider.
    
    Extracts and validates JWT tokens from Authorization header.
    Supports custom claim mapping for user_id, tenant_ids, and roles.
    
    Args:
        secret_key: Secret key for token validation (or from JWT_SECRET_KEY env var)
        algorithms: List of allowed algorithms (default: ["HS256"])
        audience: Expected audience claim (optional)
        issuer: Expected issuer claim (optional)
        user_id_claim: JWT claim for user ID (default: "sub")
        tenant_claim: JWT claim for tenant IDs (default: "tenants")
        roles_claim: JWT claim for roles (default: "roles")
        admin_role: Role name that grants admin access (default: "admin")
        allow_anonymous: Allow requests without token (default: False)
    
    Expected JWT payload structure:
        {
            "sub": "user-123",
            "tenants": ["tenant-a", "tenant-b"],
            "roles": ["editor", "admin"],
            "exp": 1699999999
        }
    
    Example:
        provider = JWTAuthProvider(
            secret_key="my-secret",
            admin_role="superuser",
        )
        
        cf = ContextForge(auth_provider=provider)
    """
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithms: Optional[list[str]] = None,
        audience: Optional[str] = None,
        issuer: Optional[str] = None,
        user_id_claim: str = "sub",
        tenant_claim: str = "tenants",
        roles_claim: str = "roles",
        admin_role: str = "admin",
        allow_anonymous: bool = False,
    ):
        self._secret_key = secret_key or os.environ.get("JWT_SECRET_KEY")
        if not self._secret_key:
            raise ConfigurationError(
                "JWT secret key not provided. "
                "Set JWT_SECRET_KEY environment variable or pass secret_key parameter."
            )
        
        self._algorithms = algorithms or ["HS256"]
        self._audience = audience
        self._issuer = issuer
        self._user_id_claim = user_id_claim
        self._tenant_claim = tenant_claim
        self._roles_claim = roles_claim
        self._admin_role = admin_role
        self._allow_anonymous = allow_anonymous
        
        self._jwt = None
    
    @property
    def _jwt_module(self):
        """Lazy load PyJWT."""
        if self._jwt is None:
            try:
                import jwt
                self._jwt = jwt
            except ImportError:
                raise ConfigurationError(
                    "PyJWT library not installed. "
                    "Run: pip install contextforge[jwt]"
                )
        return self._jwt
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from Authorization header."""
        auth_header = request.headers.get("Authorization", "")
        
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        
        return None
    
    async def get_current_user(self, request: Request) -> AuthContext:
        """
        Extract and validate JWT token from request.
        
        Returns AuthContext with user info from token claims.
        """
        token = self._extract_token(request)
        
        if not token:
            if self._allow_anonymous:
                return AuthContext(
                    user_id="anonymous",
                    tenant_ids=[],
                    roles=[],
                    is_admin=False,
                )
            raise AuthenticationError("Missing authentication token")
        
        try:
            decode_options = {}
            if self._audience:
                decode_options["audience"] = self._audience
            if self._issuer:
                decode_options["issuer"] = self._issuer
            
            payload = self._jwt_module.decode(
                token,
                self._secret_key,
                algorithms=self._algorithms,
                options=decode_options,
            )
            
        except self._jwt_module.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except self._jwt_module.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
        
        user_id = payload.get(self._user_id_claim, "unknown")
        tenant_ids = payload.get(self._tenant_claim, [])
        roles = payload.get(self._roles_claim, [])
        
        if isinstance(tenant_ids, str):
            tenant_ids = [tenant_ids]
        if isinstance(roles, str):
            roles = [roles]
        
        is_admin = self._admin_role in roles
        
        return AuthContext(
            user_id=str(user_id),
            tenant_ids=tenant_ids,
            roles=roles,
            is_admin=is_admin,
            metadata={"token_payload": payload},
        )
    
    async def check_tenant_access(
        self,
        user: AuthContext,
        tenant_id: str,
    ) -> bool:
        """Check if user can access the specified tenant."""
        return user.can_access_tenant(tenant_id)
    
    def __repr__(self) -> str:
        return f"JWTAuthProvider(algorithms={self._algorithms!r}, allow_anonymous={self._allow_anonymous})"
