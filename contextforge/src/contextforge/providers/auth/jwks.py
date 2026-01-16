"""
JWKS Auth Provider

JWKS-based JWT validation for Azure AD and ADFS.
Supports automatic key rotation via JWKS endpoint caching.

Installation:
    pip install contextforge[jwt]
    # or
    pip install pyjwt[crypto] aiohttp

Usage:
    from contextforge.providers.auth import JWKSAuthProvider
    
    # Azure AD
    provider = JWKSAuthProvider(
        jwks_url="https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys",
        issuer="https://login.microsoftonline.com/{tenant}/v2.0",
        audience="api://your-app-id",
    )
    
    cf = ContextForge(
        database_url="...",
        auth_provider=provider,
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from fastapi import Request

from contextforge.protocols.auth import AuthContext
from contextforge.core.exceptions import AuthenticationError, ConfigurationError


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JWTValidationResult:
    """
    Immutable container for JWT validation results.
    
    Thread-safe and suitable for concurrent access.
    All collections are immutable (frozenset, tuple).
    """
    token: str
    decoded_claims: Dict[str, Any]
    user_id: str
    email: str
    display_name: str
    groups: FrozenSet[str] = field(default_factory=frozenset)
    roles: FrozenSet[str] = field(default_factory=frozenset)
    issuer: str = ""
    audience: str = ""
    expires_at: Optional[datetime] = None
    issued_at: Optional[datetime] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


class JWKSCache:
    """Thread-safe cache for JWKS keys with automatic expiration."""
    
    def __init__(self, ttl_minutes: int = 60):
        self._cache: Dict[str, Tuple[List[Dict], datetime]] = {}
        self._lock = threading.RLock()
        self._ttl = timedelta(minutes=ttl_minutes)
    
    def get(self, url: str) -> Optional[List[Dict]]:
        """Get cached keys if not expired."""
        with self._lock:
            if url not in self._cache:
                return None
            keys, timestamp = self._cache[url]
            if datetime.utcnow() - timestamp > self._ttl:
                del self._cache[url]
                return None
            return keys
    
    def set(self, url: str, keys: List[Dict]) -> None:
        """Cache keys with current timestamp."""
        with self._lock:
            self._cache[url] = (keys, datetime.utcnow())
    
    def clear(self) -> None:
        """Clear all cached keys."""
        with self._lock:
            self._cache.clear()


class JWKSAuthProvider:
    """
    Enterprise-grade JWT authentication provider with JWKS support.
    
    Features:
    - JWKS key caching with automatic expiration
    - Multiple issuer support (Azure AD + ADFS fallback)
    - RS256/RS384/RS512 algorithm support
    - Configurable claim mapping
    - Thread-safe operation
    
    Args:
        jwks_url: Primary JWKS endpoint URL
        issuer: Expected token issuer (or list of issuers)
        audience: Expected token audience (optional)
        algorithms: Allowed signing algorithms (default: ["RS256"])
        cache_ttl_minutes: JWKS cache TTL (default: 60)
        user_id_claim: Claim for user ID (default: "sub")
        email_claim: Claim for email (default: "email", falls back to "upn")
        name_claim: Claim for display name (default: "name")
        groups_claim: Claim for group memberships (default: "groups")
        roles_claim: Claim for roles (default: "roles")
        admin_role: Role that grants admin access (default: "admin")
        allow_anonymous: Allow unauthenticated requests (default: False)
        fallback_jwks_url: Secondary JWKS endpoint for failover (optional)
        fallback_issuer: Secondary issuer for failover (optional)
    
    Example - Azure AD:
        provider = JWKSAuthProvider(
            jwks_url="https://login.microsoftonline.com/common/discovery/v2.0/keys",
            issuer="https://login.microsoftonline.com/{tenant-id}/v2.0",
            audience="api://your-client-id",
            groups_claim="groups",
        )
    
    Example - Dual provider (Azure AD + ADFS):
        provider = JWKSAuthProvider(
            jwks_url="https://login.microsoftonline.com/common/discovery/v2.0/keys",
            issuer="https://login.microsoftonline.com/{tenant}/v2.0",
            audience="api://your-app",
            fallback_jwks_url="https://adfs.company.com/adfs/discovery/keys",
            fallback_issuer="https://adfs.company.com/adfs",
        )
    """
    
    def __init__(
        self,
        jwks_url: str,
        issuer: str | List[str],
        audience: Optional[str | List[str]] = None,
        algorithms: Optional[List[str]] = None,
        cache_ttl_minutes: int = 60,
        user_id_claim: str = "sub",
        email_claim: str = "email",
        name_claim: str = "name",
        groups_claim: str = "groups",
        roles_claim: str = "roles",
        admin_role: str = "admin",
        allow_anonymous: bool = False,
        fallback_jwks_url: Optional[str] = None,
        fallback_issuer: Optional[str] = None,
        verify_ssl: bool = True,
    ):
        self._jwks_url = jwks_url
        self._issuers = [issuer] if isinstance(issuer, str) else issuer
        self._audiences = (
            [audience] if isinstance(audience, str) 
            else (audience or [])
        )
        self._algorithms = algorithms or ["RS256"]
        self._verify_ssl = verify_ssl
        
        # Fallback configuration
        self._fallback_jwks_url = fallback_jwks_url
        if fallback_issuer:
            self._issuers.append(fallback_issuer)
        
        # Claim mapping
        self._user_id_claim = user_id_claim
        self._email_claim = email_claim
        self._name_claim = name_claim
        self._groups_claim = groups_claim
        self._roles_claim = roles_claim
        self._admin_role = admin_role
        self._allow_anonymous = allow_anonymous
        
        # Cache
        self._cache = JWKSCache(ttl_minutes=cache_ttl_minutes)
        
        # Lazy-loaded modules
        self._jwt = None
        self._aiohttp = None
    
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
                    "Run: pip install contextforge[jwt] or pip install pyjwt[crypto]"
                )
        return self._jwt
    
    async def _get_aiohttp(self):
        """Lazy load aiohttp."""
        if self._aiohttp is None:
            try:
                import aiohttp
                self._aiohttp = aiohttp
            except ImportError:
                raise ConfigurationError(
                    "aiohttp library not installed. "
                    "Run: pip install aiohttp"
                )
        return self._aiohttp
    
    async def _fetch_jwks(self, url: str) -> List[Dict]:
        """Fetch JWKS keys from endpoint with caching."""
        # Check cache first
        cached = self._cache.get(url)
        if cached is not None:
            return cached
        
        aiohttp = await self._get_aiohttp()
        ssl_context = None if self._verify_ssl else False
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    ssl=ssl_context,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
            if "keys" not in data:
                raise ValueError("Invalid JWKS response: 'keys' not found")
            
            keys = data["keys"]
            self._cache.set(url, keys)
            logger.debug(f"Fetched {len(keys)} keys from {url}")
            return keys
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching JWKS from {url}")
            raise AuthenticationError("Authentication service unavailable")
        except Exception as e:
            logger.error(f"Error fetching JWKS from {url}: {e}")
            raise AuthenticationError(f"Failed to fetch signing keys: {e}")
    
    async def _get_signing_key(self, token: str, jwks_url: str) -> Any:
        """Get the signing key for a token based on its kid claim."""
        try:
            header = self._jwt_module.get_unverified_header(token)
        except Exception as e:
            raise AuthenticationError(f"Invalid token header: {e}")
        
        kid = header.get("kid")
        if not kid:
            raise AuthenticationError("Token missing 'kid' header")
        
        keys = await self._fetch_jwks(jwks_url)
        
        for key in keys:
            if key.get("kid") == kid:
                try:
                    jwk_json = json.dumps(key)
                    return self._jwt_module.algorithms.RSAAlgorithm.from_jwk(jwk_json)
                except Exception as e:
                    logger.warning(f"Failed to parse key {kid}: {e}")
                    continue
        
        raise AuthenticationError(f"No matching signing key found for kid: {kid}")
    
    async def _validate_token(self, token: str) -> JWTValidationResult:
        """
        Validate JWT token and return immutable result.
        
        Tries primary JWKS endpoint first, falls back to secondary if configured.
        """
        jwt_module = self._jwt_module
        last_error: Optional[Exception] = None
        
        # Try each JWKS URL
        jwks_urls = [self._jwks_url]
        if self._fallback_jwks_url:
            jwks_urls.append(self._fallback_jwks_url)
        
        for jwks_url in jwks_urls:
            try:
                signing_key = await self._get_signing_key(token, jwks_url)
                
                # Try each issuer
                for issuer in self._issuers:
                    try:
                        options = {
                            "verify_signature": True,
                            "verify_exp": True,
                            "verify_iss": True,
                            "verify_aud": bool(self._audiences),
                            "require": ["exp", "iss"],
                        }
                        
                        decode_kwargs = {
                            "jwt": token,
                            "key": signing_key,
                            "algorithms": self._algorithms,
                            "options": options,
                            "issuer": issuer,
                        }
                        
                        if self._audiences:
                            decode_kwargs["audience"] = self._audiences
                        
                        claims = jwt_module.decode(**decode_kwargs)
                        
                        # Extract user info from claims
                        return self._extract_validation_result(token, claims)
                        
                    except jwt_module.InvalidIssuerError:
                        logger.debug(f"Issuer mismatch for {issuer}, trying next")
                        continue
                    except jwt_module.InvalidAudienceError:
                        logger.debug(f"Audience mismatch for issuer {issuer}")
                        continue
                        
            except AuthenticationError:
                raise
            except jwt_module.ExpiredSignatureError:
                raise AuthenticationError("Token has expired")
            except jwt_module.InvalidSignatureError:
                logger.debug(f"Invalid signature with {jwks_url}, trying fallback")
                last_error = AuthenticationError("Invalid token signature")
                continue
            except jwt_module.InvalidTokenError as e:
                last_error = AuthenticationError(f"Invalid token: {e}")
                continue
            except Exception as e:
                logger.warning(f"Token validation failed with {jwks_url}: {e}")
                last_error = e
                continue
        
        # If we get here, all attempts failed
        if last_error:
            raise last_error if isinstance(last_error, AuthenticationError) else AuthenticationError(str(last_error))
        raise AuthenticationError("Token validation failed")
    
    def _extract_validation_result(
        self, 
        token: str, 
        claims: Dict[str, Any]
    ) -> JWTValidationResult:
        """Extract user info from validated claims into immutable result."""
        # User ID
        user_id = str(claims.get(self._user_id_claim, claims.get("sub", "unknown")))
        
        # Email - try multiple claim names
        email = (
            claims.get(self._email_claim) or 
            claims.get("upn") or 
            claims.get("preferred_username") or
            ""
        )
        
        # Display name
        display_name = (
            claims.get(self._name_claim) or
            claims.get("given_name", "") + " " + claims.get("family_name", "") or
            email.split("@")[0] if email else "Unknown"
        ).strip()
        
        # Groups - handle both list and single value
        raw_groups = claims.get(self._groups_claim, [])
        if isinstance(raw_groups, str):
            raw_groups = [raw_groups]
        groups = frozenset(str(g) for g in raw_groups)
        
        # Roles - try multiple claim names (Azure AD uses 'roles', others use 'role')
        raw_roles = claims.get(self._roles_claim) or claims.get("role", [])
        if isinstance(raw_roles, str):
            raw_roles = [raw_roles]
        roles = frozenset(str(r) for r in raw_roles)
        
        # Timestamps
        exp = claims.get("exp")
        iat = claims.get("iat")
        
        return JWTValidationResult(
            token=token,
            decoded_claims=claims,
            user_id=user_id,
            email=email,
            display_name=display_name,
            groups=groups,
            roles=roles,
            issuer=claims.get("iss", ""),
            audience=claims.get("aud", "") if isinstance(claims.get("aud"), str) else "",
            expires_at=datetime.utcfromtimestamp(exp) if exp else None,
            issued_at=datetime.utcfromtimestamp(iat) if iat else None,
        )
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract Bearer token from Authorization header."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None
    
    async def get_current_user(self, request: Request) -> AuthContext:
        """
        Authenticate request and return AuthContext.
        
        Implements contextforge.protocols.auth.AuthProvider protocol.
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
        
        result = await self._validate_token(token)
        
        return AuthContext(
            user_id=result.user_id,
            tenant_ids=list(result.groups),  # Map groups to tenants
            roles=list(result.roles),
            is_admin=self._admin_role in result.roles,
            metadata={
                "email": result.email,
                "display_name": result.display_name,
                "groups": list(result.groups),
                "issuer": result.issuer,
                "token_claims": result.decoded_claims,
            },
        )
    
    async def check_tenant_access(
        self,
        user: AuthContext,
        tenant_id: str,
    ) -> bool:
        """Check if user can access tenant."""
        return user.can_access_tenant(tenant_id)
    
    async def validate_token(self, token: str) -> JWTValidationResult:
        """
        Validate a token directly (useful for WebSocket, background jobs).
        
        Returns JWTValidationResult for rich token info, or raises AuthenticationError.
        """
        if not token:
            raise AuthenticationError("Empty token")
        return await self._validate_token(token)
    
    def clear_cache(self) -> None:
        """Clear the JWKS key cache (useful for testing or key rotation)."""
        self._cache.clear()
        logger.info("JWKS cache cleared")
    
    def __repr__(self) -> str:
        return (
            f"JWKSAuthProvider("
            f"jwks_url={self._jwks_url!r}, "
            f"issuers={self._issuers!r}, "
            f"algorithms={self._algorithms!r})"
        )
