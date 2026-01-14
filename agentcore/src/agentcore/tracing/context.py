"""Trace context for request-scoped tracing."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

if TYPE_CHECKING:
    from langfuse import Langfuse
    from langfuse.client import StatefulSpanClient, StatefulTraceClient


# Context variable for current trace
_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar(
    "current_trace", default=None
)


@dataclass
class TraceContext:
    """Request-scoped trace context.
    
    Tracks metrics and holds Langfuse references for a single request.
    """

    trace_id: str
    session_id: str
    user_id: str
    agent_id: Optional[str] = None

    # Metrics
    inference_calls: int = 0
    tool_calls: int = 0
    knowledge_retrievals: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None

    # Langfuse references (optional - None if tracing disabled)
    _langfuse: Optional["Langfuse"] = field(default=None, repr=False)
    _trace: Optional["StatefulTraceClient"] = field(default=None, repr=False)
    _span_stack: list["StatefulSpanClient"] = field(default_factory=list, repr=False)

    # Extra metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        session_id: str,
        user_id: str,
        agent_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        langfuse: Optional["Langfuse"] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "TraceContext":
        """Create a new trace context and set it as current."""
        ctx = cls(
            trace_id=trace_id or str(uuid4()),
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            _langfuse=langfuse,
            metadata=metadata or {},
        )
        _current_trace.set(ctx)
        return ctx

    @classmethod
    def current(cls) -> Optional["TraceContext"]:
        """Get current trace context."""
        return _current_trace.get()

    @classmethod
    def require_current(cls) -> "TraceContext":
        """Get current trace context, raising if not set."""
        ctx = _current_trace.get()
        if ctx is None:
            raise RuntimeError("No active trace context")
        return ctx

    def clear(self) -> None:
        """Clear this context from contextvars."""
        _current_trace.set(None)

    @property
    def current_span(self) -> Optional["StatefulSpanClient"]:
        """Get the current (innermost) span."""
        return self._span_stack[-1] if self._span_stack else None

    def push_span(self, span: "StatefulSpanClient") -> None:
        """Push a span onto the stack."""
        self._span_stack.append(span)

    def pop_span(self) -> Optional["StatefulSpanClient"]:
        """Pop and return the current span."""
        return self._span_stack.pop() if self._span_stack else None

    @property
    def duration_ms(self) -> Optional[float]:
        """Get trace duration in milliseconds."""
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds() * 1000

    def record_inference(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Record an inference call."""
        self.inference_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def record_tool_call(self) -> None:
        """Record a tool call."""
        self.tool_calls += 1

    def record_knowledge_retrieval(self) -> None:
        """Record a knowledge retrieval."""
        self.knowledge_retrievals += 1

    def end(self) -> None:
        """End the trace."""
        self.ended_at = datetime.now(timezone.utc)

    def to_summary(self) -> dict[str, Any]:
        """Get trace summary for logging."""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "inference_calls": self.inference_calls,
            "tool_calls": self.tool_calls,
            "knowledge_retrievals": self.knowledge_retrievals,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "duration_ms": self.duration_ms,
        }
