"""Tracing client for Langfuse integration."""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from agentcore.settings.tracing import TracingSettings
from agentcore.tracing.context import TraceContext

if TYPE_CHECKING:
    from agentcore.auth.context import RequestContext

logger = logging.getLogger(__name__)


class TracingClient:
    """Client for Langfuse tracing.
    
    Provides methods to create traces, spans, and generations.
    Falls back gracefully when Langfuse is not configured.
    """

    def __init__(self, settings: Optional[TracingSettings] = None):
        self._settings = settings or TracingSettings()
        self._langfuse: Optional[Any] = None

        if self._settings.is_configured and self._settings.enabled:
            try:
                from langfuse import Langfuse

                self._langfuse = Langfuse(
                    public_key=self._settings.public_key,
                    secret_key=self._settings.secret_key,
                    host=self._settings.host,
                )
                logger.info("Langfuse tracing initialized")
            except ImportError:
                logger.warning("Langfuse not installed, tracing disabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")

    @property
    def enabled(self) -> bool:
        """Check if tracing is enabled and configured."""
        return self._langfuse is not None and self._settings.enabled

    def _should_sample(self) -> bool:
        """Check if this request should be sampled."""
        return random.random() < self._settings.sample_rate

    def start_trace(
        self,
        ctx: "RequestContext",
        name: str,
        agent_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TraceContext:
        """Start a new trace for a request.
        
        Args:
            ctx: Request context with user/session info
            name: Trace name (e.g., "handle_message")
            agent_id: Optional agent identifier
            metadata: Optional additional metadata
            
        Returns:
            TraceContext that should be used for the duration of the request
        """
        trace_metadata = {
            "user_id": str(ctx.user.user_id),
            "username": ctx.user.username,
            "session_id": ctx.session_id,
            "request_id": ctx.request_id,
            **(metadata or {}),
        }

        trace_ctx = TraceContext.create(
            session_id=ctx.session_id,
            user_id=str(ctx.user.user_id),
            agent_id=agent_id,
            metadata=trace_metadata,
        )

        # Create Langfuse trace if enabled and sampled
        if self.enabled and self._should_sample():
            try:
                trace = self._langfuse.trace(
                    id=trace_ctx.trace_id,
                    name=name,
                    session_id=ctx.session_id,
                    user_id=str(ctx.user.user_id),
                    metadata=trace_metadata,
                )
                trace_ctx._langfuse = self._langfuse
                trace_ctx._trace = trace
            except Exception as e:
                logger.warning(f"Failed to create Langfuse trace: {e}")

        return trace_ctx

    def end_trace(
        self,
        trace_ctx: TraceContext,
        output: Optional[str] = None,
        level: str = "DEFAULT",
    ) -> None:
        """End a trace.
        
        Args:
            trace_ctx: The trace context to end
            output: Optional output/result to record
            level: Log level (DEFAULT, DEBUG, WARNING, ERROR)
        """
        trace_ctx.end()

        if trace_ctx._trace is not None:
            try:
                trace_ctx._trace.update(
                    output=self._truncate(output) if output else None,
                    level=level,
                    metadata={
                        **trace_ctx.metadata,
                        "summary": trace_ctx.to_summary(),
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to end Langfuse trace: {e}")

        trace_ctx.clear()

    def span(
        self,
        trace_ctx: TraceContext,
        name: str,
        input_data: Optional[Any] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "SpanContextManager":
        """Create a span context manager.
        
        Usage:
            with tracing.span(trace_ctx, "process_query") as span:
                # do work
                span.set_output(result)
        """
        return SpanContextManager(
            client=self,
            trace_ctx=trace_ctx,
            name=name,
            input_data=input_data,
            metadata=metadata,
        )

    def generation(
        self,
        trace_ctx: TraceContext,
        name: str,
        model: str,
        input_messages: list[dict[str, Any]],
        model_parameters: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "GenerationContextManager":
        """Create a generation context manager for LLM calls.
        
        Usage:
            with tracing.generation(trace_ctx, "completion", "gpt-4", messages) as gen:
                response = await llm.complete(messages)
                gen.set_output(response, usage={"input": 100, "output": 50})
        """
        return GenerationContextManager(
            client=self,
            trace_ctx=trace_ctx,
            name=name,
            model=model,
            input_messages=input_messages,
            model_parameters=model_parameters,
            metadata=metadata,
        )

    def log_decision(
        self,
        trace_ctx: TraceContext,
        decision_type: str,
        decision: str,
        reasoning: str,
        options: Optional[list[str]] = None,
    ) -> None:
        """Log a decision point in the trace.
        
        Args:
            trace_ctx: Current trace context
            decision_type: Type of decision (e.g., "routing", "tool_selection")
            decision: The decision made
            reasoning: Why this decision was made
            options: Available options that were considered
        """
        if not self._settings.trace_decisions:
            return

        if trace_ctx._trace is not None:
            try:
                parent = trace_ctx.current_span or trace_ctx._trace
                parent.event(
                    name=f"decision:{decision_type}",
                    metadata={
                        "decision_type": decision_type,
                        "decision": decision,
                        "reasoning": reasoning,
                        "options": options,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to log decision: {e}")

    def log_event(
        self,
        trace_ctx: TraceContext,
        name: str,
        metadata: Optional[dict[str, Any]] = None,
        level: str = "DEFAULT",
    ) -> None:
        """Log an event in the trace."""
        if trace_ctx._trace is not None:
            try:
                parent = trace_ctx.current_span or trace_ctx._trace
                parent.event(
                    name=name,
                    metadata=metadata,
                    level=level,
                )
            except Exception as e:
                logger.warning(f"Failed to log event: {e}")

    def _truncate(self, content: Optional[str]) -> Optional[str]:
        """Truncate content to max length."""
        if content is None:
            return None
        max_len = self._settings.max_content_length
        if len(content) > max_len:
            return content[:max_len] + f"... [truncated, total {len(content)} chars]"
        return content

    def flush(self) -> None:
        """Flush any pending traces to Langfuse."""
        if self._langfuse is not None:
            try:
                self._langfuse.flush()
            except Exception as e:
                logger.warning(f"Failed to flush Langfuse: {e}")

    def shutdown(self) -> None:
        """Shutdown the tracing client."""
        if self._langfuse is not None:
            try:
                self._langfuse.shutdown()
            except Exception as e:
                logger.warning(f"Failed to shutdown Langfuse: {e}")


class SpanContextManager:
    """Context manager for spans."""

    def __init__(
        self,
        client: TracingClient,
        trace_ctx: TraceContext,
        name: str,
        input_data: Optional[Any] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        self._client = client
        self._trace_ctx = trace_ctx
        self._name = name
        self._input_data = input_data
        self._metadata = metadata or {}
        self._span: Optional[Any] = None
        self._output: Optional[Any] = None
        self._level: str = "DEFAULT"
        self._start_time: datetime = datetime.now(timezone.utc)

    def __enter__(self) -> "SpanContextManager":
        if self._trace_ctx._trace is not None:
            try:
                parent = self._trace_ctx.current_span or self._trace_ctx._trace
                self._span = parent.span(
                    name=self._name,
                    input=self._client._truncate(str(self._input_data)) if self._input_data else None,
                    metadata=self._metadata,
                )
                self._trace_ctx.push_span(self._span)
            except Exception as e:
                logger.warning(f"Failed to create span: {e}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._span is not None:
            try:
                self._trace_ctx.pop_span()
                level = "ERROR" if exc_type is not None else self._level
                self._span.end(
                    output=self._client._truncate(str(self._output)) if self._output else None,
                    level=level,
                    metadata={
                        **self._metadata,
                        "duration_ms": (datetime.now(timezone.utc) - self._start_time).total_seconds() * 1000,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to end span: {e}")

    def set_output(self, output: Any) -> None:
        """Set the span output."""
        self._output = output

    def set_level(self, level: str) -> None:
        """Set the span level."""
        self._level = level

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the span."""
        self._metadata[key] = value


class GenerationContextManager:
    """Context manager for LLM generations."""

    def __init__(
        self,
        client: TracingClient,
        trace_ctx: TraceContext,
        name: str,
        model: str,
        input_messages: list[dict[str, Any]],
        model_parameters: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        self._client = client
        self._trace_ctx = trace_ctx
        self._name = name
        self._model = model
        self._input_messages = input_messages
        self._model_parameters = model_parameters or {}
        self._metadata = metadata or {}
        self._generation: Optional[Any] = None
        self._output: Optional[Any] = None
        self._usage: Optional[dict[str, int]] = None
        self._level: str = "DEFAULT"
        self._start_time: datetime = datetime.now(timezone.utc)

    def __enter__(self) -> "GenerationContextManager":
        if self._trace_ctx._trace is not None and self._client._settings.trace_inference:
            try:
                parent = self._trace_ctx.current_span or self._trace_ctx._trace
                self._generation = parent.generation(
                    name=self._name,
                    model=self._model,
                    input=self._input_messages,
                    model_parameters=self._model_parameters,
                    metadata=self._metadata,
                )
            except Exception as e:
                logger.warning(f"Failed to create generation: {e}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._generation is not None:
            try:
                level = "ERROR" if exc_type is not None else self._level
                
                # Record metrics
                if self._usage:
                    self._trace_ctx.record_inference(
                        input_tokens=self._usage.get("input", 0),
                        output_tokens=self._usage.get("output", 0),
                    )
                else:
                    self._trace_ctx.record_inference()

                self._generation.end(
                    output=self._output,
                    level=level,
                    usage=self._usage,
                    metadata={
                        **self._metadata,
                        "duration_ms": (datetime.now(timezone.utc) - self._start_time).total_seconds() * 1000,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to end generation: {e}")

    def set_output(
        self,
        output: Any,
        usage: Optional[dict[str, int]] = None,
    ) -> None:
        """Set the generation output and usage.
        
        Args:
            output: The LLM response
            usage: Token usage dict with "input" and "output" keys
        """
        self._output = output
        self._usage = usage

    def set_level(self, level: str) -> None:
        """Set the generation level."""
        self._level = level


class MockTracingClient(TracingClient):
    """Mock tracing client for testing without Langfuse.
    
    Records traces in memory for inspection.
    """

    def __init__(self):
        self._settings = TracingSettings(enabled=True, public_key="mock", secret_key="mock")
        self._langfuse = None
        self.traces: list[dict[str, Any]] = []
        self.spans: list[dict[str, Any]] = []
        self.generations: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        return True

    def _should_sample(self) -> bool:
        return True

    def start_trace(
        self,
        ctx: "RequestContext",
        name: str,
        agent_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TraceContext:
        trace_ctx = TraceContext.create(
            session_id=ctx.session_id,
            user_id=str(ctx.user.user_id),
            agent_id=agent_id,
            metadata=metadata or {},
        )
        self.traces.append({
            "trace_id": trace_ctx.trace_id,
            "name": name,
            "session_id": ctx.session_id,
            "user_id": str(ctx.user.user_id),
            "agent_id": agent_id,
            "metadata": metadata,
        })
        return trace_ctx

    def end_trace(
        self,
        trace_ctx: TraceContext,
        output: Optional[str] = None,
        level: str = "DEFAULT",
    ) -> None:
        trace_ctx.end()
        # Update the trace record
        for trace in self.traces:
            if trace["trace_id"] == trace_ctx.trace_id:
                trace["output"] = output
                trace["level"] = level
                trace["summary"] = trace_ctx.to_summary()
                break
        trace_ctx.clear()

    def log_decision(
        self,
        trace_ctx: TraceContext,
        decision_type: str,
        decision: str,
        reasoning: str,
        options: Optional[list[str]] = None,
    ) -> None:
        self.decisions.append({
            "trace_id": trace_ctx.trace_id,
            "decision_type": decision_type,
            "decision": decision,
            "reasoning": reasoning,
            "options": options,
        })

    def log_event(
        self,
        trace_ctx: TraceContext,
        name: str,
        metadata: Optional[dict[str, Any]] = None,
        level: str = "DEFAULT",
    ) -> None:
        self.events.append({
            "trace_id": trace_ctx.trace_id,
            "name": name,
            "metadata": metadata,
            "level": level,
        })

    def clear(self) -> None:
        """Clear all recorded data."""
        self.traces.clear()
        self.spans.clear()
        self.generations.clear()
        self.decisions.clear()
        self.events.clear()
