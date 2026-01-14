"""Unit tests for AgentAPI module."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agentcore.api.models import (
    HealthResponse,
    QueryContext,
    QueryLocale,
    QueryRequest,
)
from agentcore.api.server import AgentAPI
from agentcore.auth.models import Permission
from agentcore.registry.models import AgentInfo


class MockAgent:
    """Mock agent for testing."""
    
    agent_id = "test-agent"
    name = "Test Agent"
    description = "A test agent"
    version = "1.0.0"
    team = "test-team"
    capabilities = ["search", "create"]
    domains = ["test"]
    example_queries = ["Find something", "Create something"]
    
    async def handle_message(self, ctx, message, attachments=None):
        yield {"type": "progress", "payload": {"status": "Processing"}}
        yield {"type": "markdown", "payload": "## Result\n\nDone!"}


class TestQueryModels:
    """Tests for query request/response models."""

    def test_query_locale_defaults(self):
        locale = QueryLocale()
        
        assert locale.timezone == "UTC"
        assert locale.language == "en-US"

    def test_query_locale_custom(self):
        locale = QueryLocale(timezone="America/Los_Angeles", language="ko-KR")
        
        assert locale.timezone == "America/Los_Angeles"
        assert locale.language == "ko-KR"

    def test_query_context_minimal(self):
        ctx = QueryContext(user_id=123)
        
        assert ctx.user_id == 123
        assert ctx.username == ""
        assert ctx.permissions == []
        assert ctx.is_admin is False

    def test_query_context_full(self):
        ctx = QueryContext(
            user_id=123,
            username="testuser",
            email="test@example.com",
            display_name="Test User",
            permissions=["Admin", "Buyer"],
            is_admin=True,
            is_buyer=True,
            entity_id=456,
            entity_name="Test Entity",
        )
        
        assert ctx.user_id == 123
        assert ctx.username == "testuser"
        assert ctx.email == "test@example.com"
        assert ctx.is_admin is True
        assert ctx.is_buyer is True
        assert "Admin" in ctx.permissions
        assert ctx.entity_id == 456

    def test_query_request_minimal(self):
        request = QueryRequest(
            query="Find something",
            session_id="session-123",
            context=QueryContext(user_id=1),
        )
        
        assert request.query == "Find something"
        assert request.session_id == "session-123"
        assert request.request_id is None
        assert request.context.user_id == 1
        assert request.locale.timezone == "UTC"
        assert request.attachments == []

    def test_query_request_full(self):
        request = QueryRequest(
            query="Find PO 12345",
            session_id="session-123",
            request_id="request-456",
            context=QueryContext(
                user_id=123,
                permissions=["Buyer"],
            ),
            locale=QueryLocale(timezone="America/New_York"),
            attachments=[{"name": "file.pdf", "size": 1024}],
        )
        
        assert request.query == "Find PO 12345"
        assert request.request_id == "request-456"
        assert request.locale.timezone == "America/New_York"
        assert len(request.attachments) == 1

    def test_health_response(self):
        response = HealthResponse(
            agent_id="test-agent",
            version="2.0.0",
        )
        
        assert response.status == "healthy"
        assert response.agent_id == "test-agent"
        assert response.version == "2.0.0"


class TestAgentAPI:
    """Tests for AgentAPI class."""

    def test_init_creates_app(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent)
        
        assert api.app is not None
        assert api.app.title == "Test Agent"
        assert api.app.version == "1.0.0"

    def test_init_with_registry(self):
        agent = MockAgent()
        registry = MagicMock()
        
        api = AgentAPI(agent=agent, registry=registry)
        
        assert api._registry is registry

    def test_init_with_custom_base_url(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent, base_url="http://my-agent:9000")
        
        assert api._base_url == "http://my-agent:9000"

    def test_get_agent_info(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent, base_url="http://test:8000")
        
        info = api._get_agent_info()
        
        assert isinstance(info, AgentInfo)
        assert info.agent_id == "test-agent"
        assert info.name == "Test Agent"
        assert info.description == "A test agent"
        assert info.version == "1.0.0"
        assert info.base_url == "http://test:8000"
        assert "search" in info.capabilities
        assert "test" in info.domains

    def test_create_request_context(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent)
        
        request = QueryRequest(
            query="Test query",
            session_id="session-123",
            request_id="request-456",
            context=QueryContext(
                user_id=123,
                username="testuser",
                email="test@example.com",
                display_name="Test User",
                permissions=["Admin", "Buyer"],
                is_admin=True,
                is_buyer=True,
            ),
            locale=QueryLocale(timezone="America/Los_Angeles", language="en-US"),
        )
        
        ctx = api._create_request_context(request)
        
        assert ctx.user.user_id == 123
        assert ctx.user.username == "testuser"
        assert ctx.user.email == "test@example.com"
        assert ctx.user.is_admin is True
        assert ctx.user.is_buyer is True
        assert Permission.ADMIN in ctx.user.permissions
        assert Permission.BUYER in ctx.user.permissions
        assert ctx.session_id == "session-123"
        assert ctx.request_id == "request-456"
        assert ctx.locale.timezone == "America/Los_Angeles"

    def test_create_request_context_with_invalid_permissions(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent)
        
        request = QueryRequest(
            query="Test",
            session_id="s1",
            context=QueryContext(
                user_id=1,
                permissions=["Admin", "InvalidPermission", "Buyer"],
            ),
        )
        
        ctx = api._create_request_context(request)
        
        assert Permission.ADMIN in ctx.user.permissions
        assert Permission.BUYER in ctx.user.permissions
        assert len(ctx.user.permissions) == 2

    def test_create_request_context_generates_request_id(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent)
        
        request = QueryRequest(
            query="Test",
            session_id="s1",
            context=QueryContext(user_id=1),
        )
        
        ctx = api._create_request_context(request)
        
        assert ctx.request_id is not None
        assert len(ctx.request_id) > 0

    def test_format_sse_event(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent)
        
        data = {"type": "progress", "payload": {"status": "Working"}}
        result = api._format_sse_event(data)
        
        assert result == 'data: {"type": "progress", "payload": {"status": "Working"}}\n\n'

    def test_format_sse_event_with_complex_payload(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent)
        
        data = {
            "type": "markdown",
            "payload": "## Title\n\nContent with \"quotes\" and 'apostrophes'",
        }
        result = api._format_sse_event(data)
        
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "markdown"


class TestAgentAPILifecycle:
    """Tests for AgentAPI startup/shutdown lifecycle."""

    @pytest.mark.asyncio
    async def test_startup_without_registry(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent)
        
        await api._startup()

    @pytest.mark.asyncio
    async def test_startup_with_registry(self):
        agent = MockAgent()
        registry = AsyncMock()
        
        api = AgentAPI(agent=agent, registry=registry)
        await api._startup()
        
        registry.register.assert_called_once()
        call_args = registry.register.call_args[0][0]
        assert call_args.agent_id == "test-agent"

    @pytest.mark.asyncio
    async def test_shutdown_without_registry(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent)
        
        await api._shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_with_registry(self):
        agent = MockAgent()
        registry = AsyncMock()
        
        api = AgentAPI(agent=agent, registry=registry)
        await api._startup()
        await api._shutdown()
        
        registry.unregister.assert_called_once_with("test-agent")

    @pytest.mark.asyncio
    async def test_shutdown_handles_unregister_error(self):
        agent = MockAgent()
        registry = AsyncMock()
        registry.unregister.side_effect = Exception("Connection error")
        
        api = AgentAPI(agent=agent, registry=registry)
        await api._startup()
        await api._shutdown()


class TestAgentAPIQueryHandling:
    """Tests for query handling."""

    @pytest.mark.asyncio
    async def test_handle_query_yields_events(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent)
        
        request = QueryRequest(
            query="Find something",
            session_id="s1",
            context=QueryContext(user_id=1),
        )
        
        events = []
        async for event in api._handle_query(request):
            events.append(event)
        
        assert len(events) >= 3
        
        progress_event = events[0]
        assert "progress" in progress_event
        
        markdown_event = events[1]
        assert "markdown" in markdown_event
        
        done_event = events[-1]
        assert "done" in done_event

    @pytest.mark.asyncio
    async def test_handle_query_handles_error(self):
        class FailingAgent(MockAgent):
            async def handle_message(self, ctx, message, attachments=None):
                raise ValueError("Something went wrong")
                yield
        
        agent = FailingAgent()
        api = AgentAPI(agent=agent)
        
        request = QueryRequest(
            query="Fail",
            session_id="s1",
            context=QueryContext(user_id=1),
        )
        
        events = []
        async for event in api._handle_query(request):
            events.append(event)
        
        assert len(events) == 1
        assert "error" in events[0]
        assert "Something went wrong" in events[0]


class TestAgentAPIRoutes:
    """Tests for route setup."""

    def test_routes_are_registered(self):
        agent = MockAgent()
        api = AgentAPI(agent=agent)
        
        routes = [r.path for r in api.app.routes]
        
        assert "/health" in routes
        assert "/capabilities" in routes
        assert "/api/v1/query" in routes
        assert "/ws" in routes
