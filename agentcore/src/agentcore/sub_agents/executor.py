"""Executor sub-agent for state-modifying actions."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Callable, Optional
from uuid import uuid4

from agentcore.core.models import InteractionStatus, PlanStep, SubAgentResult, ToolResult
from agentcore.sub_agents.base import SubAgentBase, SubAgentConfig
from agentcore.tracing.decorators import trace_agent

if TYPE_CHECKING:
    from agentcore.auth.context import RequestContext
    from agentcore.core.blackboard import Blackboard
    from agentcore.inference.client import InferenceClient
    from agentcore.knowledge.retriever import KnowledgeRetriever
    from agentcore.tracing.client import TracingClient

logger = logging.getLogger(__name__)


# Type alias for tool functions
ToolFunction = Callable[..., Any]


class ExecutorSubAgent(SubAgentBase):
    """Sub-agent that executes state-modifying actions.
    
    The Executor:
    - Executes tools that modify state (create, update, delete)
    - Supports Human-in-the-Loop (HIL) for approval workflows
    - Handles tool execution and error handling
    - Can request confirmation before high-impact actions
    """

    name: str = "executor"
    description: str = "Executes actions that modify state"

    def __init__(
        self,
        inference: "InferenceClient",
        retriever: Optional["KnowledgeRetriever"] = None,
        tracing: Optional["TracingClient"] = None,
        config: Optional[SubAgentConfig] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_functions: Optional[dict[str, ToolFunction]] = None,
    ):
        """Initialize the executor.
        
        Args:
            inference: LLM inference client
            retriever: Knowledge retriever
            tracing: Tracing client
            config: Sub-agent configuration
            tools: Tool definitions in OpenAI format
            tool_functions: Mapping of tool names to callable functions
        """
        super().__init__(inference, retriever, tracing, config)
        self._tools = tools or []
        self._tool_functions = tool_functions or {}
        
        # Executor-specific defaults
        if config is None:
            self._config = SubAgentConfig(
                temperature=0.2,  # Very low temp for consistent action selection
                max_tokens=1024,
            )

    def register_tool(
        self,
        name: str,
        function: ToolFunction,
        definition: dict[str, Any],
    ) -> None:
        """Register a tool with the executor.
        
        Args:
            name: Tool name
            function: Callable that implements the tool
            definition: OpenAI-format tool definition
        """
        self._tool_functions[name] = function
        self._tools.append(definition)

    def set_tools(
        self,
        tools: list[dict[str, Any]],
        functions: dict[str, ToolFunction],
    ) -> None:
        """Set available tools.
        
        Args:
            tools: Tool definitions in OpenAI format
            functions: Mapping of tool names to functions
        """
        self._tools = tools
        self._tool_functions = functions

    @trace_agent("executor_execute")
    async def execute(
        self,
        ctx: "RequestContext",
        blackboard: "Blackboard",
        step: PlanStep,
        system_prompt: str,
    ) -> SubAgentResult:
        """Execute the action task.
        
        Args:
            ctx: Request context
            blackboard: Shared state
            step: The plan step to execute
            system_prompt: Agent's system prompt
            
        Returns:
            SubAgentResult with action results
        """
        try:
            # Build execution prompt
            user_prompt = self._build_execution_prompt(
                instruction=step.instruction,
                query=blackboard.query,
                blackboard_context=self._get_blackboard_context(blackboard),
            )
            
            # Make LLM call to determine action
            content, tokens, tool_calls = await self._make_llm_call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tools=self._tools if self._tools else None,
            )
            
            # If no tool calls, return the content as guidance
            if not tool_calls:
                return SubAgentResult.success_result(
                    output=content,
                    tokens_used=tokens,
                )
            
            # Execute tool calls
            total_tokens = tokens
            results = []
            
            for tool_call in tool_calls:
                if self._requires_hil(tool_call.name, tool_call.arguments):
                    description = self._describe_action(tool_call.name, tool_call.arguments)
                    interaction_id = blackboard.add_pending_interaction(
                        interaction_type="confirm",
                        prompt=f"Approve action: {tool_call.name}?\n{description}",
                        options=["Approve", "Reject"],
                    )
                    
                    return SubAgentResult.success_result(
                        output={
                            "status": InteractionStatus.AWAITING_APPROVAL,
                            "interaction_id": interaction_id,
                            "tool_name": tool_call.name,
                        },
                        tokens_used=total_tokens,
                    )
                
                result = await self._execute_tool(
                    ctx=ctx,
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                    tool_call_id=tool_call.id,
                )
                
                if result.success:
                    blackboard.add_tool_result(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        result=result.result,
                    )
                else:
                    blackboard.add_tool_error(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        error=result.error or "Unknown error",
                    )
                
                results.append(result)
            
            # Summarize results
            summary = self._summarize_results(results)
            
            return SubAgentResult.success_result(
                output=summary,
                tokens_used=total_tokens,
            )
            
        except Exception as e:
            logger.exception(f"Executor failed: {e}")
            return SubAgentResult.failure_result(str(e))

    async def execute_approved_action(
        self,
        ctx: "RequestContext",
        blackboard: "Blackboard",
        interaction_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> SubAgentResult:
        """Execute an action that was approved via HIL.
        
        Args:
            ctx: Request context
            blackboard: Shared state
            interaction_id: ID of the approved interaction
            tool_name: Tool to execute
            arguments: Tool arguments
            
        Returns:
            SubAgentResult with action result
        """
        # Resolve the interaction
        blackboard.resolve_interaction(interaction_id, {"approved": True})
        
        # Generate a tool call ID
        tool_call_id = f"hil_{interaction_id}"
        
        # Execute the tool
        result = await self._execute_tool(
            ctx=ctx,
            tool_name=tool_name,
            arguments=arguments,
            tool_call_id=tool_call_id,
        )
        
        if result.success:
            blackboard.add_tool_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                result=result.result,
            )
        else:
            blackboard.add_tool_error(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error=result.error or "Unknown error",
            )
        
        if result.success:
            return SubAgentResult.success_result(output=result.result)
        else:
            return SubAgentResult.failure_result(result.error or "Tool execution failed")

    def _build_execution_prompt(
        self,
        instruction: str,
        query: str,
        blackboard_context: str,
    ) -> str:
        """Build the execution prompt."""
        tools_desc = ""
        if self._tools:
            tools_desc = "Available tools:\n" + "\n".join(
                f"- {t['function']['name']}: {t['function'].get('description', 'No description')}"
                for t in self._tools
            )
        
        return f"""Action Task: {instruction}

Original User Query: {query}

{tools_desc}

Current Context:
{blackboard_context}

Instructions:
1. Determine which action(s) to take based on the task
2. Use the appropriate tool(s) to execute the action
3. Handle any errors gracefully
4. Report the results

Select and call the appropriate tool(s) to complete this action."""

    def _requires_hil(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Check if a tool call requires human-in-the-loop approval.
        
        Override this method to implement custom HIL logic.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            True if HIL required
        """
        # Default: require HIL for destructive operations
        destructive_keywords = ["delete", "remove", "cancel", "terminate", "destroy"]
        
        if any(kw in tool_name.lower() for kw in destructive_keywords):
            return True
        
        # Check arguments for high-value thresholds
        if "amount" in arguments:
            try:
                amount = float(arguments["amount"])
                if amount > 10000:  # Example threshold
                    return True
            except (ValueError, TypeError):
                pass
        
        return False

    def _describe_action(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Generate a human-readable description of an action.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            Human-readable description
        """
        args_str = ", ".join(f"{k}={v}" for k, v in arguments.items())
        return f"Execute {tool_name}({args_str})"

    async def _execute_tool(
        self,
        ctx: "RequestContext",
        tool_name: str,
        arguments: dict[str, Any],
        tool_call_id: str,
    ) -> ToolResult:
        """Execute a tool function.
        
        Args:
            ctx: Request context
            tool_name: Name of the tool
            arguments: Tool arguments
            tool_call_id: ID of the tool call
            
        Returns:
            ToolResult
        """
        from datetime import datetime, timezone
        
        start_time = datetime.now(timezone.utc)
        
        # Get the tool function
        func = self._tool_functions.get(tool_name)
        
        if func is None:
            return ToolResult.failure_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' not found",
            )
        
        try:
            # Check if function is async
            import asyncio
            if asyncio.iscoroutinefunction(func):
                result = await func(ctx=ctx, **arguments)
            else:
                result = func(ctx=ctx, **arguments)
            
            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            return ToolResult.success_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                result=result,
                duration_ms=duration,
            )
            
        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            return ToolResult.failure_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error=str(e),
                duration_ms=duration,
            )

    def _summarize_results(self, results: list[ToolResult]) -> dict[str, Any]:
        """Summarize tool execution results.
        
        Args:
            results: List of tool results
            
        Returns:
            Summary dict
        """
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        summary = {
            "total_actions": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "results": [],
        }
        
        for r in results:
            summary["results"].append({
                "tool": r.tool_name,
                "success": r.success,
                "result": r.get_result_for_context() if r.success else None,
                "error": r.error if not r.success else None,
            })
        
        return summary
