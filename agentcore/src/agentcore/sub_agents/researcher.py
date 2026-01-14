"""Researcher sub-agent for information gathering."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from agentcore.core.models import PlanStep, SubAgentResult
from agentcore.prompts.registry import get_prompt_registry
from agentcore.sub_agents.base import SubAgentBase, SubAgentConfig
from agentcore.tracing.decorators import trace_agent

if TYPE_CHECKING:
    from agentcore.auth.context import RequestContext
    from agentcore.core.blackboard import Blackboard
    from agentcore.inference.client import InferenceClient
    from agentcore.knowledge.retriever import KnowledgeRetriever
    from agentcore.tracing.client import TracingClient

logger = logging.getLogger(__name__)


class ResearcherSubAgent(SubAgentBase):
    """Sub-agent that gathers information from knowledge base and tools.
    
    The Researcher:
    - Retrieves relevant knowledge from the knowledge base
    - Can invoke tools to gather additional information
    - Synthesizes findings into a structured output
    - Adds findings to the blackboard for other sub-agents
    """

    name: str = "researcher"
    description: str = "Gathers information from knowledge base and tools"

    def __init__(
        self,
        inference: "InferenceClient",
        retriever: Optional["KnowledgeRetriever"] = None,
        tracing: Optional["TracingClient"] = None,
        config: Optional[SubAgentConfig] = None,
        tools: Optional[list[dict[str, Any]]] = None,
    ):
        """Initialize the researcher.
        
        Args:
            inference: LLM inference client
            retriever: Knowledge retriever
            tracing: Tracing client
            config: Sub-agent configuration
            tools: Available tool definitions in OpenAI format
        """
        super().__init__(inference, retriever, tracing, config)
        self._tools = tools or []
        
        # Researcher-specific defaults
        if config is None:
            self._config = SubAgentConfig(
                temperature=0.5,  # Balanced for research
                max_tokens=2048,
            )

    def set_tools(self, tools: list[dict[str, Any]]) -> None:
        """Set available tools.
        
        Args:
            tools: Tool definitions in OpenAI format
        """
        self._tools = tools

    @trace_agent("researcher_execute")
    async def execute(
        self,
        ctx: "RequestContext",
        blackboard: "Blackboard",
        step: PlanStep,
        system_prompt: str,
    ) -> SubAgentResult:
        """Execute the research task.
        
        Args:
            ctx: Request context
            blackboard: Shared state
            step: The plan step to execute
            system_prompt: Agent's system prompt
            
        Returns:
            SubAgentResult with research findings
        """
        try:
            # Get knowledge context for research
            knowledge_context = await self._get_knowledge_context(ctx, step.instruction)
            
            # Build research prompt
            user_prompt = self._build_research_prompt(
                instruction=step.instruction,
                query=blackboard.query,
                knowledge_context=knowledge_context,
                blackboard_context=self._get_blackboard_context(blackboard),
            )
            
            # Make LLM call (with tools if available)
            content, tokens, tool_calls = await self._make_llm_call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tools=self._tools if self._tools else None,
            )
            
            # Handle tool calls if any
            total_tokens = tokens
            if tool_calls:
                tool_results = await self._handle_tool_calls(blackboard, tool_calls)
                
                # Make follow-up call with tool results
                follow_up_content, follow_up_tokens = await self._follow_up_with_results(
                    system_prompt=system_prompt,
                    original_prompt=user_prompt,
                    tool_results=tool_results,
                )
                content = follow_up_content
                total_tokens += follow_up_tokens
            
            # Add findings to blackboard
            if content:
                blackboard.add_finding(
                    source="researcher",
                    content=content,
                )
            
            return SubAgentResult.success_result(
                output=content,
                tokens_used=total_tokens,
            )
            
        except Exception as e:
            logger.exception(f"Researcher failed: {e}")
            return SubAgentResult.failure_result(str(e))

    async def _get_knowledge_context(self, ctx: "RequestContext", query: str) -> str:
        """Get knowledge context for research."""
        if self._retriever is None:
            return ""
        
        try:
            bundle = await self._retriever.retrieve_for_research(ctx, query)
            return bundle.get_for_research()
        except Exception as e:
            logger.warning(f"Failed to retrieve knowledge for research: {e}")
            return ""

    def _build_research_prompt(
        self,
        instruction: str,
        query: str,
        knowledge_context: str,
        blackboard_context: str,
    ) -> str:
        """Build the research prompt using the prompt registry."""
        prompts = get_prompt_registry()
        return prompts.get(
            "agent-researcher",
            instruction=instruction,
            query=query,
            knowledge_context=knowledge_context,
            blackboard_context=blackboard_context,
        )

    async def _handle_tool_calls(
        self,
        blackboard: "Blackboard",
        tool_calls: list[Any],
    ) -> list[dict[str, Any]]:
        """Handle tool calls from the LLM.
        
        Note: Actual tool execution is deferred to the Tools module.
        For now, we store the calls in the blackboard and return placeholders.
        
        Args:
            blackboard: The blackboard
            tool_calls: Tool calls from LLM response
            
        Returns:
            List of tool result dicts
        """
        results = []
        
        for tool_call in tool_calls:
            # Store tool call in blackboard (actual execution deferred)
            # The Tools module will handle actual execution
            result = {
                "tool_call_id": tool_call.id,
                "tool_name": tool_call.name,
                "arguments": tool_call.arguments,
                "result": {"status": "pending", "message": "Tool execution deferred to Tools module"},
            }
            
            # Add to blackboard
            blackboard.add_tool_result(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                result=result["result"],
            )
            
            results.append(result)
        
        return results

    async def _follow_up_with_results(
        self,
        system_prompt: str,
        original_prompt: str,
        tool_results: list[dict[str, Any]],
    ) -> tuple[str, int]:
        """Make a follow-up call with tool results.
        
        Args:
            system_prompt: System prompt
            original_prompt: Original research prompt
            tool_results: Results from tool calls
            
        Returns:
            Tuple of (content, tokens_used)
        """
        from agentcore.inference import InferenceConfig, Message, MessageRole
        
        # Format tool results
        results_text = "\n".join(
            f"- {r['tool_name']}: {r['result']}"
            for r in tool_results
        )
        
        follow_up_prompt = f"""{original_prompt}

Tool Results:
{results_text}

Based on these tool results, provide your research findings."""

        content, tokens, _ = await self._make_llm_call(
            system_prompt=system_prompt,
            user_prompt=follow_up_prompt,
        )
        
        return content, tokens

    async def research(
        self,
        ctx: "RequestContext",
        query: str,
        system_prompt: str,
        blackboard: Optional["Blackboard"] = None,
    ) -> str:
        """Perform standalone research on a query.
        
        Convenience method for research outside the normal sub-agent flow.
        
        Args:
            ctx: Request context
            query: Research query
            system_prompt: Agent's system prompt
            blackboard: Optional blackboard for context
            
        Returns:
            Research findings as string
        """
        knowledge_context = await self._get_knowledge_context(ctx, query)
        blackboard_context = ""
        if blackboard:
            blackboard_context = self._get_blackboard_context(blackboard)
        
        user_prompt = self._build_research_prompt(
            instruction=query,
            query=query,
            knowledge_context=knowledge_context,
            blackboard_context=blackboard_context,
        )
        
        content, _, _ = await self._make_llm_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        return content
