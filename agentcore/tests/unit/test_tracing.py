"""Unit tests for tracing module."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from agentcore.tracing.context import TraceContext
from agentcore.tracing.client import TracingClient, MockTracingClient
from agentcore.tracing.decorators import trace_agent, trace_tool
from agentcore.auth.models import EnrichedUser, Permission
from agentcore.auth.context import RequestContext


# Fixtures
@pytest.fixture
def user():
    return EnrichedUser(
        user_id=1,
        username="testuser",
        email="test@example.com",
        display_name="Test User",
        department="Engineering",
        title="Engineer",
        entity_id=1,
        entity_name="Test Entity",
        permissions=frozenset([Permission.BUYER]),
        token="test-token",
    )


@pytest.fixture
def request_ctx(user):
    return RequestContext.create(
        user=user,
        session_id="test-session",
        request_id="test-request",
    )


class TestTraceContext:
    """Tests for TraceContext."""

    def test_create(self):
        ctx = TraceContext.create(
            session_id="sess-123",
            user_id="user-456",
            agent_id="test-agent",
        )
        
        assert ctx.session_id == "sess-123"
        assert ctx.user_id == "user-456"
        assert ctx.agent_id == "test-agent"
        assert ctx.trace_id is not None
        assert ctx.inference_calls == 0
        assert ctx.tool_calls == 0
        
        # Clean up
        ctx.clear()

    def test_current_context(self):
        # Initially no context
        assert TraceContext.current() is None
        
        # Create context
        ctx = TraceContext.create(
            session_id="sess-123",
            user_id="user-456",
        )
        
        # Now should be available
        assert TraceContext.current() is ctx
        
        # Clean up
        ctx.clear()
        assert TraceContext.current() is None

    def test_require_current_raises(self):
        with pytest.raises(RuntimeError, match="No active trace context"):
            TraceContext.require_current()

    def test_record_metrics(self):
        ctx = TraceContext.create(
            session_id="sess-123",
            user_id="user-456",
        )
        
        ctx.record_inference(input_tokens=100, output_tokens=50)
        assert ctx.inference_calls == 1
        assert ctx.total_input_tokens == 100
        assert ctx.total_output_tokens == 50
        
        ctx.record_tool_call()
        assert ctx.tool_calls == 1
        
        ctx.record_knowledge_retrieval()
        assert ctx.knowledge_retrievals == 1
        
        ctx.clear()

    def test_end_and_duration(self):
        ctx = TraceContext.create(
            session_id="sess-123",
            user_id="user-456",
        )
        
        assert ctx.duration_ms is None
        
        ctx.end()
        
        assert ctx.ended_at is not None
        assert ctx.duration_ms is not None
        assert ctx.duration_ms >= 0
        
        ctx.clear()

    def test_to_summary(self):
        ctx = TraceContext.create(
            session_id="sess-123",
            user_id="user-456",
            agent_id="test-agent",
        )
        
        ctx.record_inference(input_tokens=100, output_tokens=50)
        ctx.record_tool_call()
        ctx.end()
        
        summary = ctx.to_summary()
        
        assert summary["session_id"] == "sess-123"
        assert summary["user_id"] == "user-456"
        assert summary["agent_id"] == "test-agent"
        assert summary["inference_calls"] == 1
        assert summary["tool_calls"] == 1
        assert summary["total_input_tokens"] == 100
        assert summary["total_output_tokens"] == 50
        assert summary["duration_ms"] is not None
        
        ctx.clear()


class TestMockTracingClient:
    """Tests for MockTracingClient."""

    def test_start_and_end_trace(self, request_ctx):
        client = MockTracingClient()
        
        trace_ctx = client.start_trace(
            ctx=request_ctx,
            name="test_trace",
            agent_id="test-agent",
        )
        
        assert len(client.traces) == 1
        assert client.traces[0]["name"] == "test_trace"
        assert client.traces[0]["agent_id"] == "test-agent"
        
        client.end_trace(trace_ctx, output="test output")
        
        assert client.traces[0]["output"] == "test output"
        assert "summary" in client.traces[0]

    def test_log_decision(self, request_ctx):
        client = MockTracingClient()
        trace_ctx = client.start_trace(ctx=request_ctx, name="test")
        
        client.log_decision(
            trace_ctx=trace_ctx,
            decision_type="routing",
            decision="selected_agent",
            reasoning="Best match for query",
            options=["agent1", "agent2"],
        )
        
        assert len(client.decisions) == 1
        assert client.decisions[0]["decision_type"] == "routing"
        assert client.decisions[0]["decision"] == "selected_agent"
        assert client.decisions[0]["options"] == ["agent1", "agent2"]

    def test_log_event(self, request_ctx):
        client = MockTracingClient()
        trace_ctx = client.start_trace(ctx=request_ctx, name="test")
        
        client.log_event(
            trace_ctx=trace_ctx,
            name="custom_event",
            metadata={"key": "value"},
        )
        
        assert len(client.events) == 1
        assert client.events[0]["name"] == "custom_event"
        assert client.events[0]["metadata"] == {"key": "value"}

    def test_clear(self, request_ctx):
        client = MockTracingClient()
        trace_ctx = client.start_trace(ctx=request_ctx, name="test")
        client.log_decision(trace_ctx, "type", "decision", "reason")
        client.log_event(trace_ctx, "event")
        
        client.clear()
        
        assert len(client.traces) == 0
        assert len(client.decisions) == 0
        assert len(client.events) == 0


class TestTracingClientDisabled:
    """Tests for TracingClient when disabled."""

    def test_disabled_by_default_without_credentials(self, request_ctx):
        # Without credentials, client should be effectively disabled
        client = TracingClient()
        
        trace_ctx = client.start_trace(ctx=request_ctx, name="test")
        
        # Should still create a TraceContext
        assert trace_ctx is not None
        assert trace_ctx.trace_id is not None
        
        # But no Langfuse trace
        assert trace_ctx._trace is None
        
        client.end_trace(trace_ctx)


class TestDecorators:
    """Tests for tracing decorators."""

    @pytest.mark.asyncio
    async def test_trace_agent_without_context(self):
        """Decorator should work without active trace context."""
        @trace_agent("test_method")
        async def test_method(x: int) -> int:
            return x * 2
        
        # Should work without trace context
        result = await test_method(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_trace_tool_without_context(self):
        """Tool decorator should work without active trace context."""
        @trace_tool("test_tool")
        async def test_tool(query: str) -> str:
            return f"Result: {query}"
        
        result = await test_tool("test")
        assert result == "Result: test"

    def test_trace_agent_sync(self):
        """Decorator should work with sync functions."""
        @trace_agent("sync_method")
        def sync_method(x: int) -> int:
            return x * 2
        
        result = sync_method(5)
        assert result == 10

    def test_trace_tool_sync(self):
        """Tool decorator should work with sync functions."""
        @trace_tool("sync_tool")
        def sync_tool(query: str) -> str:
            return f"Result: {query}"
        
        result = sync_tool("test")
        assert result == "Result: test"
