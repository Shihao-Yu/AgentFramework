"""
Tests for rate limiting functionality.

Tests cover:
- In-memory rate limiter
- Rate limit dependency
- Key generation (user, IP)
- Rate limit headers
- 429 Too Many Requests response
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.core.rate_limit import (
    InMemoryRateLimiter,
    RateLimitInfo,
    get_rate_limit_key,
    rate_limit_dependency,
)


class TestInMemoryRateLimiter:
    """Test InMemoryRateLimiter class."""

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        """Should allow requests under the limit."""
        limiter = InMemoryRateLimiter()
        
        info = await limiter.is_allowed("user:123", limit=10, window=60)
        
        assert info.remaining == 9
        assert info.retry_after is None

    @pytest.mark.asyncio
    async def test_tracks_request_count(self):
        """Should track request count accurately."""
        limiter = InMemoryRateLimiter()
        
        for i in range(5):
            info = await limiter.is_allowed("user:123", limit=10, window=60)
        
        assert info.remaining == 5  # 10 - 5 = 5

    @pytest.mark.asyncio
    async def test_blocks_when_limit_reached(self):
        """Should block when limit is reached."""
        limiter = InMemoryRateLimiter()
        
        # Make 10 requests (the limit)
        for i in range(10):
            await limiter.is_allowed("user:123", limit=10, window=60)
        
        # 11th request should be blocked
        info = await limiter.is_allowed("user:123", limit=10, window=60)
        
        assert info.remaining == 0
        assert info.retry_after is not None
        assert info.retry_after > 0

    @pytest.mark.asyncio
    async def test_separate_keys_tracked_independently(self):
        """Different keys should be tracked independently."""
        limiter = InMemoryRateLimiter()
        
        # Use up all requests for user:123
        for i in range(10):
            await limiter.is_allowed("user:123", limit=10, window=60)
        
        # user:456 should still have requests available
        info = await limiter.is_allowed("user:456", limit=10, window=60)
        
        assert info.remaining == 9

    @pytest.mark.asyncio
    async def test_window_expiration(self):
        """Requests should expire after window."""
        limiter = InMemoryRateLimiter()
        
        # Make requests with a very short window
        await limiter.is_allowed("user:123", limit=10, window=0.1)
        
        # Wait for window to expire
        await asyncio.sleep(0.15)
        
        # Should have full limit again
        info = await limiter.is_allowed("user:123", limit=10, window=0.1)
        
        assert info.remaining == 9

    @pytest.mark.asyncio
    async def test_reset_clears_count(self):
        """Reset should clear the request count."""
        limiter = InMemoryRateLimiter()
        
        # Make some requests
        for i in range(5):
            await limiter.is_allowed("user:123", limit=10, window=60)
        
        # Reset
        await limiter.reset("user:123")
        
        # Should have full limit again
        info = await limiter.is_allowed("user:123", limit=10, window=60)
        
        assert info.remaining == 9

    @pytest.mark.asyncio
    async def test_cleanup_removes_stale_entries(self):
        """Cleanup should remove old entries."""
        limiter = InMemoryRateLimiter()
        
        # Add some requests
        await limiter.is_allowed("user:old", limit=10, window=0.1)
        await limiter.is_allowed("user:new", limit=10, window=60)
        
        # Wait for old window to expire
        await asyncio.sleep(0.15)
        
        # Cleanup with very short max_age
        removed = await limiter.cleanup(max_age=0.05)
        
        # Old entry should be removed
        assert removed >= 1


class TestRateLimitKey:
    """Test rate limit key generation."""

    def test_authenticated_user_key(self):
        """Should use user_id for authenticated users."""
        request = MagicMock()
        user_context = {"user_id": "user-123", "is_authenticated": True}
        
        key = get_rate_limit_key(request, user_context)
        
        assert key == "user:user-123"

    def test_unauthenticated_uses_ip(self):
        """Should use IP for unauthenticated requests."""
        request = MagicMock()
        request.headers = {}
        request.client.host = "192.168.1.100"
        user_context = {"user_id": "anonymous", "is_authenticated": False}
        
        key = get_rate_limit_key(request, user_context)
        
        assert key == "ip:192.168.1.100"

    def test_forwarded_ip_header(self):
        """Should use X-Forwarded-For header when present."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
        request.client.host = "192.168.1.100"
        user_context = None
        
        key = get_rate_limit_key(request, user_context)
        
        # Should use first IP (original client)
        assert key == "ip:10.0.0.1"

    def test_no_user_context(self):
        """Should handle None user context."""
        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"
        
        key = get_rate_limit_key(request, None)
        
        assert key == "ip:127.0.0.1"


class TestRateLimitDependency:
    """Test rate_limit_dependency function."""

    @pytest.fixture
    def app(self):
        """Create test app with rate-limited endpoint."""
        app = FastAPI()
        
        @app.get("/limited")
        async def limited_endpoint(
            _: None = Depends(rate_limit_dependency(limit=3, window=60)),
        ):
            return {"status": "ok"}
        
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_allows_requests_under_limit(self, client):
        """Should allow requests under limit."""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            
            response = client.get("/limited")
            
            assert response.status_code == 200

    def test_blocks_when_limit_exceeded(self, client):
        """Should return 429 when limit exceeded."""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            
            # Make requests up to limit
            for _ in range(3):
                client.get("/limited")
            
            # Next request should be blocked
            response = client.get("/limited")
            
            assert response.status_code == 429

    def test_429_includes_retry_after(self, client):
        """429 response should include Retry-After header."""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            
            # Exhaust limit
            for _ in range(3):
                client.get("/limited")
            
            response = client.get("/limited")
            
            assert response.status_code == 429
            assert "Retry-After" in response.headers

    def test_disabled_rate_limiting(self, client):
        """Should not limit when disabled."""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = False
            
            # Should allow unlimited requests
            for _ in range(10):
                response = client.get("/limited")
                assert response.status_code == 200


class TestRateLimitHeaders:
    """Test rate limit response headers."""

    @pytest.fixture
    def app(self):
        """Create test app with rate-limited endpoint."""
        app = FastAPI()
        
        @app.get("/limited")
        async def limited_endpoint(
            _: None = Depends(rate_limit_dependency(limit=5, window=60)),
        ):
            return {"status": "ok"}
        
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_429_includes_limit_header(self, client):
        """Should include X-RateLimit-Limit header."""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            
            # Exhaust limit
            for _ in range(5):
                client.get("/limited")
            
            response = client.get("/limited")
            
            assert "X-RateLimit-Limit" in response.headers
            assert response.headers["X-RateLimit-Limit"] == "5"

    def test_429_includes_remaining_header(self, client):
        """Should include X-RateLimit-Remaining header."""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            
            # Exhaust limit
            for _ in range(5):
                client.get("/limited")
            
            response = client.get("/limited")
            
            assert "X-RateLimit-Remaining" in response.headers
            assert response.headers["X-RateLimit-Remaining"] == "0"

    def test_429_includes_reset_header(self, client):
        """Should include X-RateLimit-Reset header."""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            
            # Exhaust limit
            for _ in range(5):
                client.get("/limited")
            
            response = client.get("/limited")
            
            assert "X-RateLimit-Reset" in response.headers


class TestRateLimitInfo:
    """Test RateLimitInfo dataclass."""

    def test_rate_limit_info_fields(self):
        """Should have correct fields."""
        info = RateLimitInfo(
            limit=100,
            remaining=50,
            reset_at=1234567890.0,
            retry_after=30,
        )
        
        assert info.limit == 100
        assert info.remaining == 50
        assert info.reset_at == 1234567890.0
        assert info.retry_after == 30

    def test_retry_after_optional(self):
        """retry_after should be optional."""
        info = RateLimitInfo(
            limit=100,
            remaining=50,
            reset_at=1234567890.0,
        )
        
        assert info.retry_after is None


class TestRateLimitErrorResponse:
    """Test rate limit error response format."""

    @pytest.fixture
    def app(self):
        """Create test app."""
        app = FastAPI()
        
        @app.get("/limited")
        async def limited_endpoint(
            _: None = Depends(rate_limit_dependency(limit=1, window=60)),
        ):
            return {"status": "ok"}
        
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_429_error_body_format(self, client):
        """429 response should have proper error body."""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            
            # Use up limit
            client.get("/limited")
            
            # Get rate limited response
            response = client.get("/limited")
            
            assert response.status_code == 429
            body = response.json()
            
            assert "detail" in body
            assert "error" in body["detail"]
            assert "rate limit" in body["detail"]["error"].lower()
            assert "limit" in body["detail"]
            assert "retry_after" in body["detail"]
