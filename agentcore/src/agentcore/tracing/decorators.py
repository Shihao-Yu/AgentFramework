"""Tracing decorators for automatic instrumentation."""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, Optional, TypeVar, cast

from agentcore.tracing.context import TraceContext

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def trace_agent(name: Optional[str] = None) -> Callable[[F], F]:
    """Decorator to trace agent methods.
    
    Usage:
        @trace_agent("handle_message")
        async def handle_message(self, ctx: RequestContext, message: str):
            ...
            
    Or without name (uses method name):
        @trace_agent()
        async def process(self, ctx: RequestContext):
            ...
    """
    def decorator(func: F) -> F:
        span_name = name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            trace_ctx = TraceContext.current()
            if trace_ctx is None:
                return await func(*args, **kwargs)

            # Get input for logging
            input_data = _extract_input(func, args, kwargs)

            # Import here to avoid circular imports
            from agentcore.tracing.client import TracingClient
            client = TracingClient()

            with client.span(trace_ctx, f"agent:{span_name}", input_data=input_data):
                result = await func(*args, **kwargs)
                return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            trace_ctx = TraceContext.current()
            if trace_ctx is None:
                return func(*args, **kwargs)

            input_data = _extract_input(func, args, kwargs)
            from agentcore.tracing.client import TracingClient
            client = TracingClient()

            with client.span(trace_ctx, f"agent:{span_name}", input_data=input_data):
                result = func(*args, **kwargs)
                return result

        if inspect.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def trace_tool(tool_id: Optional[str] = None) -> Callable[[F], F]:
    """Decorator to trace tool executions.
    
    Usage:
        @trace_tool("search_po")
        async def search_po(self, ctx: RequestContext, query: str) -> list[dict]:
            ...
    """
    def decorator(func: F) -> F:
        tool_name = tool_id or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            trace_ctx = TraceContext.current()
            if trace_ctx is None:
                return await func(*args, **kwargs)

            trace_ctx.record_tool_call()
            input_data = _extract_input(func, args, kwargs)

            from agentcore.tracing.client import TracingClient
            client = TracingClient()

            # Check if tool tracing is enabled
            if not client._settings.trace_tools:
                return await func(*args, **kwargs)

            with client.span(
                trace_ctx,
                f"tool:{tool_name}",
                input_data=input_data,
                metadata={"tool_id": tool_name},
            ) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_output(result)
                    return result
                except Exception as e:
                    span.set_level("ERROR")
                    span.add_metadata("error", str(e))
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            trace_ctx = TraceContext.current()
            if trace_ctx is None:
                return func(*args, **kwargs)

            trace_ctx.record_tool_call()
            input_data = _extract_input(func, args, kwargs)

            from agentcore.tracing.client import TracingClient
            client = TracingClient()

            if not client._settings.trace_tools:
                return func(*args, **kwargs)

            with client.span(
                trace_ctx,
                f"tool:{tool_name}",
                input_data=input_data,
                metadata={"tool_id": tool_name},
            ) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_output(result)
                    return result
                except Exception as e:
                    span.set_level("ERROR")
                    span.add_metadata("error", str(e))
                    raise

        if inspect.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def trace_inference(func: F) -> F:
    """Decorator to trace LLM inference calls.
    
    Expects the function to return a response with usage info.
    
    Usage:
        @trace_inference
        async def complete(self, messages: list[Message], ...) -> InferenceResponse:
            ...
    """
    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        trace_ctx = TraceContext.current()
        if trace_ctx is None:
            return await func(*args, **kwargs)

        from agentcore.tracing.client import TracingClient
        client = TracingClient()

        if not client._settings.trace_inference:
            return await func(*args, **kwargs)

        # Extract messages and model from args/kwargs
        messages = _get_messages_from_args(func, args, kwargs)
        model = kwargs.get("model") or _get_default_model(args)
        config = kwargs.get("config")

        with client.generation(
            trace_ctx,
            name="inference",
            model=model or "unknown",
            input_messages=[m if isinstance(m, dict) else {"role": str(getattr(m, "role", "unknown")), "content": getattr(m, "content", "")} for m in messages] if messages else [],
            model_parameters=config.model_dump() if config and hasattr(config, "model_dump") else None,
        ) as gen:
            result = await func(*args, **kwargs)
            
            # Extract usage from result
            usage = None
            if hasattr(result, "usage") and result.usage:
                usage = {
                    "input": getattr(result.usage, "prompt_tokens", 0) or getattr(result.usage, "input_tokens", 0),
                    "output": getattr(result.usage, "completion_tokens", 0) or getattr(result.usage, "output_tokens", 0),
                }
            
            # Extract output content
            output = None
            if hasattr(result, "content"):
                output = result.content
            elif hasattr(result, "message") and hasattr(result.message, "content"):
                output = result.message.content
                
            gen.set_output(output, usage=usage)
            return result

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        # Inference is typically async, but support sync for completeness
        trace_ctx = TraceContext.current()
        if trace_ctx is None:
            return func(*args, **kwargs)

        trace_ctx.record_inference()
        return func(*args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return cast(F, async_wrapper)
    return cast(F, sync_wrapper)


def trace_knowledge(func: F) -> F:
    """Decorator to trace knowledge/RAG retrieval calls.
    
    Usage:
        @trace_knowledge
        async def search(self, ctx: RequestContext, query: str) -> SearchResult:
            ...
    """
    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        trace_ctx = TraceContext.current()
        if trace_ctx is None:
            return await func(*args, **kwargs)

        from agentcore.tracing.client import TracingClient
        client = TracingClient()

        if not client._settings.trace_knowledge:
            return await func(*args, **kwargs)

        trace_ctx.record_knowledge_retrieval()
        
        # Extract query from args
        query = kwargs.get("query") or _get_query_from_args(func, args, kwargs)

        with client.span(
            trace_ctx,
            f"knowledge:{func.__name__}",
            input_data=query,
            metadata={"function": func.__name__},
        ) as span:
            try:
                result = await func(*args, **kwargs)
                
                # Try to extract result count for logging
                if hasattr(result, "results"):
                    span.add_metadata("result_count", len(result.results))
                elif isinstance(result, list):
                    span.add_metadata("result_count", len(result))
                    
                span.set_output(result)
                return result
            except Exception as e:
                span.set_level("ERROR")
                span.add_metadata("error", str(e))
                raise

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        trace_ctx = TraceContext.current()
        if trace_ctx is None:
            return func(*args, **kwargs)

        trace_ctx.record_knowledge_retrieval()
        return func(*args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return cast(F, async_wrapper)
    return cast(F, sync_wrapper)


def _extract_input(func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Extract meaningful input parameters from function call."""
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    
    result: dict[str, Any] = {}
    
    # Map positional args
    for i, arg in enumerate(args):
        if i < len(params):
            param_name = params[i]
            # Skip self, ctx, and other common params
            if param_name not in ("self", "cls", "ctx", "context", "request_context"):
                # Don't include large objects
                if isinstance(arg, (str, int, float, bool, type(None))):
                    result[param_name] = arg
                elif isinstance(arg, (list, dict)) and len(str(arg)) < 500:
                    result[param_name] = arg
    
    # Add kwargs (excluding common ones)
    for key, value in kwargs.items():
        if key not in ("self", "cls", "ctx", "context", "request_context"):
            if isinstance(value, (str, int, float, bool, type(None))):
                result[key] = value
            elif isinstance(value, (list, dict)) and len(str(value)) < 500:
                result[key] = value
    
    return result


def _get_messages_from_args(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Optional[list[Any]]:
    """Extract messages parameter from function call."""
    if "messages" in kwargs:
        return kwargs["messages"]
    
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    
    for i, param_name in enumerate(params):
        if param_name == "messages" and i < len(args):
            return args[i]
    
    return None


def _get_default_model(args: tuple[Any, ...]) -> Optional[str]:
    """Try to get default model from self._settings."""
    if args and hasattr(args[0], "_settings"):
        settings = args[0]._settings
        if hasattr(settings, "default_model"):
            return settings.default_model
    return None


def _get_query_from_args(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Optional[str]:
    """Extract query parameter from function call."""
    if "query" in kwargs:
        return kwargs["query"]
    
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    
    for i, param_name in enumerate(params):
        if param_name == "query" and i < len(args):
            return args[i]
    
    return None
