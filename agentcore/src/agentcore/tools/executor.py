"""Tool executor for AgentCore."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from agentcore.core.models import ToolResult
from agentcore.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from agentcore.auth.context import RequestContext
    from agentcore.core.blackboard import Blackboard
    from agentcore.tracing.client import TracingClient

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Error during tool execution."""

    def __init__(
        self,
        message: str,
        tool_name: str,
        tool_call_id: str,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.tool_name = tool_name
        self.tool_call_id = tool_call_id
        self.cause = cause


class ToolExecutor:
    """Executor for registered tools.
    
    The ToolExecutor:
    - Executes tools from a ToolRegistry
    - Handles permission validation
    - Applies timeout constraints
    - Manages context retention/compaction
    - Integrates with tracing
    - Supports both sync and async tools
    
    Example:
        ```python
        registry = ToolRegistry()
        registry.register(create_purchase_order)
        
        executor = ToolExecutor(registry=registry, tracing=tracing_client)
        
        result = await executor.execute(
            ctx=request_context,
            tool_name="create_purchase_order",
            arguments={"vendor_id": "V123", "amount": 5000},
            tool_call_id="call_123",
        )
        ```
    """

    def __init__(
        self,
        registry: ToolRegistry,
        tracing: Optional["TracingClient"] = None,
    ) -> None:
        """Initialize the executor.
        
        Args:
            registry: Tool registry
            tracing: Optional tracing client
        """
        self._registry = registry
        self._tracing = tracing

    async def execute(
        self,
        ctx: "RequestContext",
        tool_name: str,
        arguments: dict[str, Any],
        tool_call_id: str,
        blackboard: Optional["Blackboard"] = None,
    ) -> ToolResult:
        """Execute a tool.
        
        Args:
            ctx: Request context
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            tool_call_id: ID of the tool call
            blackboard: Optional blackboard to record results
            
        Returns:
            ToolResult with execution outcome
        """
        start_time = datetime.now(timezone.utc)
        
        # Get tool spec
        spec = self._registry.get(tool_name)
        if spec is None:
            logger.warning(f"Tool not found: {tool_name}")
            return ToolResult.failure_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' not found",
            )
        
        # Validate permissions
        is_valid, error_msg = self._registry.validate_permission(tool_name, ctx)
        if not is_valid:
            logger.warning(f"Permission denied for tool {tool_name}: {error_msg}")
            return ToolResult.failure_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error=error_msg or "Permission denied",
            )
        
        # Get function
        func = self._registry.get_function(tool_name)
        if func is None:
            return ToolResult.failure_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error=f"Tool function '{tool_name}' not found",
            )
        
        # Execute with timeout
        try:
            result = await self._execute_with_timeout(
                func=func,
                ctx=ctx,
                arguments=arguments,
                timeout=spec.timeout,
            )
            
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            # Apply retention/compaction
            compact_result = spec.compact_result(result)
            
            # Record to blackboard if provided
            if blackboard is not None:
                blackboard.add_tool_result(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    result=result,
                    compact_result=compact_result if compact_result != result else None,
                )
            
            logger.debug(f"Tool {tool_name} executed successfully in {duration_ms:.1f}ms")
            
            return ToolResult.success_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                result=result,
                compact_result=compact_result if compact_result != result else None,
                duration_ms=duration_ms,
            )
            
        except asyncio.TimeoutError:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            error_msg = f"Tool '{tool_name}' timed out after {spec.timeout}s"
            logger.error(error_msg)
            
            if blackboard is not None:
                blackboard.add_tool_error(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    error=error_msg,
                )
            
            return ToolResult.failure_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error=error_msg,
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            error_msg = f"Tool '{tool_name}' failed: {str(e)}"
            logger.exception(error_msg)
            
            if blackboard is not None:
                blackboard.add_tool_error(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    error=error_msg,
                )
            
            return ToolResult.failure_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error=error_msg,
                duration_ms=duration_ms,
            )

    async def execute_many(
        self,
        ctx: "RequestContext",
        tool_calls: list[dict[str, Any]],
        blackboard: Optional["Blackboard"] = None,
        parallel: bool = True,
    ) -> list[ToolResult]:
        """Execute multiple tool calls.
        
        Args:
            ctx: Request context
            tool_calls: List of tool calls with id, name, arguments
            blackboard: Optional blackboard to record results
            parallel: Whether to execute in parallel (default True)
            
        Returns:
            List of ToolResults in same order as input
        """
        if parallel:
            tasks = [
                self.execute(
                    ctx=ctx,
                    tool_name=call["name"],
                    arguments=call.get("arguments", {}),
                    tool_call_id=call["id"],
                    blackboard=blackboard,
                )
                for call in tool_calls
            ]
            return await asyncio.gather(*tasks)
        else:
            results = []
            for call in tool_calls:
                result = await self.execute(
                    ctx=ctx,
                    tool_name=call["name"],
                    arguments=call.get("arguments", {}),
                    tool_call_id=call["id"],
                    blackboard=blackboard,
                )
                results.append(result)
            return results

    async def _execute_with_timeout(
        self,
        func: Any,
        ctx: "RequestContext",
        arguments: dict[str, Any],
        timeout: float,
    ) -> Any:
        """Execute a function with timeout.
        
        Args:
            func: Function to execute
            ctx: Request context
            arguments: Function arguments
            timeout: Timeout in seconds
            
        Returns:
            Function result
            
        Raises:
            asyncio.TimeoutError: If execution times out
            Exception: Any exception from the function
        """
        import inspect
        
        sig = inspect.signature(func)
        accepts_ctx = any(
            p in sig.parameters 
            for p in ("ctx", "context", "request_context")
        )
        
        call_kwargs = dict(arguments)
        if accepts_ctx:
            call_kwargs["ctx"] = ctx
        
        if asyncio.iscoroutinefunction(func):
            coro = func(**call_kwargs)
            return await asyncio.wait_for(coro, timeout=timeout)
        else:
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, lambda: func(**call_kwargs)),
                timeout=timeout,
            )

    def check_hil_required(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """Check if HIL confirmation is required for a tool call.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            Tuple of (requires_hil, confirmation_prompt)
        """
        spec = self._registry.get(tool_name)
        if spec is None:
            return False, None
        
        if spec.requires_hil_for(arguments):
            prompt = None
            if spec.hil and spec.hil.confirmation_prompt:
                prompt = spec.hil.confirmation_prompt
            else:
                prompt = f"Confirm execution of {tool_name}?"
            return True, prompt
        
        return False, None

    @property
    def registry(self) -> ToolRegistry:
        """Get the tool registry."""
        return self._registry
