"""
Auth Provider Protocol

Defines the contract for authentication providers in the infra layer.
Implement this protocol to integrate custom auth systems (JWT, OAuth, API keys, etc.)

This protocol uses EnrichedUser for rich user context including permissions,
unlike the simpler AuthContext in contextforge which is tenant-focused.

Example - JWKS-based JWT auth:
    class EnterpriseJWTAuthProvider:
        def __init__(self, jwks_url: str, issuer: str):
            self.jwks_url = jwks_url
            self.issuer = issuer
        
        async def authenticate(self, request: Request) -> EnrichedUser:
            token = self._extract_token(request)
            claims = await self._validate_with_jwks(token)
            return EnrichedUser.from_jwt_claims(claims, token)
        
        async def validate_token(self, token: str) -> EnrichedUser:
            claims = await self._validate_with_jwks(token)
            return EnrichedUser.from_jwt_claims(claims, token)

Example - API key auth:
    class APIKeyAuthProvider:
        async def authenticate(self, request: Request) -> EnrichedUser:
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                return EnrichedUser.anonymous()
            
            user_data = await self._lookup_api_key(api_key)
            return EnrichedUser(**user_data)
"""

from typing import Optional, Protocol, runtime_checkable

from fastapi import Request

from infra.auth.models import EnrichedUser


@runtime_checkable
class AuthProvider(Protocol):
    """
    Protocol for authentication providers.
    
    Implement this to integrate with enterprise auth systems
    (Azure AD, Okta, Auth0, custom JWKS endpoints, etc.)
    
    The protocol provides two methods:
    - authenticate: Extract and validate credentials from HTTP request
    - validate_token: Validate a token directly (useful for WebSocket, background jobs)
    
    Implementations should:
    - Return EnrichedUser.anonymous() for unauthenticated requests (if allowed)
    - Raise AuthenticationError for invalid credentials
    - Include permissions/roles in the returned EnrichedUser
    """
    
    async def authenticate(self, request: Request) -> EnrichedUser:
        """
        Authenticate a request and return user context.
        
        Extract credentials from the request (headers, cookies, etc.),
        validate them, and return an EnrichedUser with full context.
        
        Args:
            request: FastAPI request object
            
        Returns:
            EnrichedUser with user info, permissions, and metadata
            
        Raises:
            AuthenticationError: If credentials are invalid or missing (when required)
        """
        ...
    
    async def validate_token(self, token: str) -> EnrichedUser:
        """
        Validate a token directly and return user context.
        
        Useful for scenarios where you have a token but no HTTP request:
        - WebSocket connections
        - Background job authentication
        - Service-to-service calls
        
        Args:
            token: The authentication token (JWT, API key, etc.)
            
        Returns:
            EnrichedUser with user info, permissions, and metadata
            
        Raises:
            AuthenticationError: If token is invalid or expired
        """
        ...
    
    async def refresh_user(self, user: EnrichedUser) -> EnrichedUser:
        """
        Refresh user information (optional).
        
        Re-fetch user permissions and metadata from the auth source.
        Useful for long-running sessions where permissions may change.
        
        Default implementation returns the user unchanged.
        
        Args:
            user: Current user context
            
        Returns:
            Updated EnrichedUser with fresh permissions
        """
        ...


class BaseAuthProvider:
    """
    Base class for auth providers with sensible defaults.
    
    Extend this class for convenience methods and default implementations.
    """
    
    async def authenticate(self, request: Request) -> EnrichedUser:
        """Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement authenticate()")
    
    async def validate_token(self, token: str) -> EnrichedUser:
        """Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement validate_token()")
    
    async def refresh_user(self, user: EnrichedUser) -> EnrichedUser:
        """Default: return user unchanged."""
        return user
    
    def _extract_bearer_token(self, request: Request) -> Optional[str]:
        """Helper to extract Bearer token from Authorization header."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None
    
    def _extract_api_key(
        self, 
        request: Request, 
        header_name: str = "X-API-Key"
    ) -> Optional[str]:
        """Helper to extract API key from header."""
        return request.headers.get(header_name)
