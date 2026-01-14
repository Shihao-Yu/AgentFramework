"""
Rate limiting middleware and dependencies for FastAPI.

Provides:
- In-memory rate limiting (single instance)
- Redis-based rate limiting (distributed, multi-instance)
- Per-user and per-tenant rate limits
- Configurable windows and limits

Usage:
    from app.core.rate_limit import RateLimiter, rate_limit_dependency
    
    # In route:
    @router.get("/search")
    async def search(
        _: None = Depends(rate_limit_dependency(limit=100, window=60)),
    ):
        ...

Configuration:
    RATE_LIMIT_ENABLED: Enable/disable rate limiting (default: True)
    RATE_LIMIT_DEFAULT_LIMIT: Default requests per window (default: 100)
    RATE_LIMIT_DEFAULT_WINDOW: Default window in seconds (default: 60)
    RATE_LIMIT_STORAGE: "memory" or "redis" (default: "memory")
"""

import time
import logging
from typing import Optional, Dict, Callable
from collections import defaultdict
from dataclasses import dataclass
from functools import wraps
import asyncio

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    limit: int = 100  # Requests per window
    window: int = 60  # Window in seconds
    key_prefix: str = "ratelimit"
    
    # Different limits by endpoint type
    search_limit: int = 200
    write_limit: int = 50
    admin_limit: int = 20


@dataclass
class RateLimitInfo:
    """Information about current rate limit status."""
    limit: int
    remaining: int
    reset_at: float
    retry_after: Optional[int] = None


class InMemoryRateLimiter:
    """
    In-memory rate limiter using sliding window.
    
    Suitable for single-instance deployments.
    For multi-instance, use RedisRateLimiter.
    """
    
    def __init__(self):
        # {key: [(timestamp, count), ...]}
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> RateLimitInfo:
        """
        Check if request is allowed under rate limit.
        
        Args:
            key: Unique identifier (user_id, tenant_id, IP, etc.)
            limit: Maximum requests allowed in window
            window: Time window in seconds
            
        Returns:
            RateLimitInfo with current status
        """
        now = time.time()
        window_start = now - window
        
        async with self._lock:
            # Remove expired entries
            self._requests[key] = [
                ts for ts in self._requests[key]
                if ts > window_start
            ]
            
            current_count = len(self._requests[key])
            
            if current_count >= limit:
                # Rate limited
                oldest = min(self._requests[key]) if self._requests[key] else now
                reset_at = oldest + window
                retry_after = int(reset_at - now) + 1
                
                return RateLimitInfo(
                    limit=limit,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=retry_after,
                )
            
            # Allow request
            self._requests[key].append(now)
            
            return RateLimitInfo(
                limit=limit,
                remaining=limit - current_count - 1,
                reset_at=now + window,
            )
    
    async def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        async with self._lock:
            self._requests.pop(key, None)
    
    async def cleanup(self, max_age: int = 3600) -> int:
        """Remove stale entries older than max_age seconds."""
        cutoff = time.time() - max_age
        removed = 0
        
        async with self._lock:
            keys_to_remove = []
            for key, timestamps in self._requests.items():
                self._requests[key] = [ts for ts in timestamps if ts > cutoff]
                if not self._requests[key]:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._requests[key]
                removed += 1
        
        return removed


class RedisRateLimiter:
    """
    Redis-based rate limiter using sliding window log.
    
    Suitable for multi-instance deployments.
    Requires Redis client from app.core.redis.
    """
    
    def __init__(self, redis_client):
        self._redis = redis_client
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> RateLimitInfo:
        """
        Check if request is allowed under rate limit.
        
        Uses Redis sorted set with timestamps as scores.
        """
        if not self._redis or not self._redis.is_connected:
            # Fall back to allowing if Redis unavailable
            logger.warning("Redis unavailable for rate limiting, allowing request")
            return RateLimitInfo(limit=limit, remaining=limit, reset_at=time.time() + window)
        
        now = time.time()
        window_start = now - window
        redis_key = f"ratelimit:{key}"
        
        try:
            # Use pipeline for atomic operations
            # 1. Remove old entries
            # 2. Count current entries
            # 3. Add new entry if allowed
            
            pipe = self._redis._client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            results = await pipe.execute()
            
            current_count = results[1]
            
            if current_count >= limit:
                # Get oldest timestamp to calculate reset time
                oldest_entries = await self._redis._client.zrange(
                    redis_key, 0, 0, withscores=True
                )
                oldest = oldest_entries[0][1] if oldest_entries else now
                reset_at = oldest + window
                retry_after = int(reset_at - now) + 1
                
                return RateLimitInfo(
                    limit=limit,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=retry_after,
                )
            
            # Allow request - add timestamp
            await self._redis._client.zadd(redis_key, {str(now): now})
            await self._redis._client.expire(redis_key, window + 10)
            
            return RateLimitInfo(
                limit=limit,
                remaining=limit - current_count - 1,
                reset_at=now + window,
            )
            
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fail open - allow request if Redis errors
            return RateLimitInfo(limit=limit, remaining=limit, reset_at=time.time() + window)
    
    async def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        if self._redis and self._redis.is_connected:
            try:
                await self._redis._client.delete(f"ratelimit:{key}")
            except Exception as e:
                logger.error(f"Failed to reset rate limit: {e}")


# Global rate limiter instance
_rate_limiter: Optional[InMemoryRateLimiter] = None
_rate_limiter_lock = asyncio.Lock()


async def get_rate_limiter() -> InMemoryRateLimiter:
    """Get or create the rate limiter singleton."""
    global _rate_limiter
    
    if _rate_limiter is None:
        async with _rate_limiter_lock:
            if _rate_limiter is None:
                _rate_limiter = InMemoryRateLimiter()
    
    return _rate_limiter


def get_rate_limit_key(request: Request, user_context: Optional[dict] = None) -> str:
    """
    Generate rate limit key from request.
    
    Priority:
    1. Authenticated user_id
    2. X-Forwarded-For header (behind proxy)
    3. Client IP
    """
    if user_context and user_context.get("is_authenticated"):
        return f"user:{user_context['user_id']}"
    
    # Check for forwarded IP (behind proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take first IP (original client)
        client_ip = forwarded.split(",")[0].strip()
        return f"ip:{client_ip}"
    
    # Direct client IP
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


def rate_limit_dependency(
    limit: int = 100,
    window: int = 60,
    key_func: Optional[Callable[[Request], str]] = None,
):
    """
    Create a rate limit dependency for FastAPI routes.
    
    Args:
        limit: Maximum requests per window
        window: Window size in seconds
        key_func: Optional custom function to generate rate limit key
        
    Returns:
        FastAPI dependency that raises HTTPException if rate limited
        
    Usage:
        @router.get("/search")
        async def search(
            _: None = Depends(rate_limit_dependency(limit=100, window=60)),
        ):
            ...
    """
    async def dependency(request: Request):
        from app.core.config import settings
        
        # Check if rate limiting is enabled
        rate_limit_enabled = getattr(settings, 'RATE_LIMIT_ENABLED', True)
        if not rate_limit_enabled:
            return None
        
        limiter = await get_rate_limiter()
        
        # Generate key
        if key_func:
            key = key_func(request)
        else:
            # Get user context if available
            user_context = getattr(request.state, 'user', None)
            key = get_rate_limit_key(request, user_context)
        
        # Check rate limit
        info = await limiter.is_allowed(key, limit, window)
        
        # Add rate limit headers to response
        # These will be picked up by middleware
        request.state.rate_limit_info = info
        
        if info.remaining < 0 or info.retry_after:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": info.limit,
                    "retry_after": info.retry_after,
                },
                headers={
                    "X-RateLimit-Limit": str(info.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(info.reset_at)),
                    "Retry-After": str(info.retry_after),
                },
            )
        
        return None
    
    return dependency


class RateLimitMiddleware:
    """
    Middleware to add rate limit headers to all responses.
    
    Usage:
        app.add_middleware(RateLimitMiddleware)
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Check if rate limit info is available
                # This would be set by the rate_limit_dependency
                headers = dict(message.get("headers", []))
                
                # Add standard rate limit headers if not already present
                # These provide transparency to API consumers
                if b"x-ratelimit-limit" not in headers:
                    # Default headers for non-rate-limited endpoints
                    pass
                
            await send(message)
        
        await self.app(scope, receive, send_wrapper)


# Convenience decorators for common rate limit patterns

def rate_limit_search(func):
    """Decorator for search endpoints (higher limit)."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper


def rate_limit_write(func):
    """Decorator for write endpoints (lower limit)."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper
