from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar(
    "current_trace", default=None
)


@dataclass
class TraceContext:
    trace_id: str
    session_id: str
    user_id: str
    agent_id: Optional[str] = None

    inference_calls: int = 0
    tool_calls: int = 0
    knowledge_retrievals: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None

    _langfuse: Optional[Any] = field(default=None, repr=False)
    _trace: Optional[Any] = field(default=None, repr=False)
    _span_stack: list[Any] = field(default_factory=list, repr=False)

    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        session_id: str,
        user_id: str,
        agent_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "TraceContext":
        ctx = cls(
            trace_id=trace_id or str(uuid4()),
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            metadata=metadata or {},
        )
        _current_trace.set(ctx)
        return ctx

    @classmethod
    def current(cls) -> Optional["TraceContext"]:
        return _current_trace.get()

    @classmethod
    def require_current(cls) -> "TraceContext":
        ctx = _current_trace.get()
        if ctx is None:
            raise RuntimeError("No active trace context")
        return ctx

    def clear(self) -> None:
        _current_trace.set(None)

    @property
    def current_span(self) -> Optional[Any]:
        return self._span_stack[-1] if self._span_stack else None

    def push_span(self, span: Any) -> None:
        self._span_stack.append(span)

    def pop_span(self) -> Optional[Any]:
        return self._span_stack.pop() if self._span_stack else None

    @property
    def duration_ms(self) -> Optional[float]:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds() * 1000

    def record_inference(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.inference_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def record_tool_call(self) -> None:
        self.tool_calls += 1

    def record_knowledge_retrieval(self) -> None:
        self.knowledge_retrievals += 1

    def end(self) -> None:
        self.ended_at = datetime.now(timezone.utc)

    def to_summary(self) -> dict[str, Any]:
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
