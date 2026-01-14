"""Base class for sub-agents."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from agentcore.core.models import PlanStep, SubAgentResult
from agentcore.inference import Message, MessageRole
from agentcore.tracing.decorators import trace_agent

if TYPE_CHECKING:
    from agentcore.auth.context import RequestContext
    from agentcore.core.blackboard import Blackboard
    from agentcore.inference.client import InferenceClient
    from agentcore.knowledge.retriever import KnowledgeRetriever
    from agentcore.tracing.client import TracingClient

logger = logging.getLogger(__name__)


class SubAgentConfig(BaseModel):
    """Configuration for sub-agent execution."""

    model_config = ConfigDict(frozen=True)

    # LLM settings
    temperature: float = Field(default=0.7, description="LLM temperature")
    max_tokens: int = Field(default=2048, description="Max tokens for response")
    
    # Context settings
    max_context_chars: int = Field(default=4000, description="Max chars for context in prompt")
    max_findings_in_context: int = Field(default=10, description="Max findings to include")
    max_tool_results_in_context: int = Field(default=5, description="Max tool results to include")
    
    # Behavior
    retry_on_failure: bool = Field(default=True, description="Retry on transient failures")
    max_retries: int = Field(default=2, description="Max retry attempts")


class SubAgentBase(ABC):
    """Base class for all sub-agents.
    
    Sub-agents handle specific types of tasks within the ReAct loop:
    - Planner: Decomposes tasks into execution plans
    - Researcher: Gathers information from knowledge base and tools
    - Analyzer: Analyzes data and makes decisions
    - Executor: Executes actions that modify state
    - Synthesizer: Generates final user-facing responses
    
    Each sub-agent:
    - Receives a step from the execution plan
    - Has access to the blackboard (shared state)
    - Can make LLM calls via inference client
    - Can retrieve knowledge via knowledge retriever
    - Returns a SubAgentResult
    """

    # Sub-agent identity (override in subclass)
    name: str = "base"
    description: str = "Base sub-agent"

    def __init__(
        self,
        inference: "InferenceClient",
        retriever: Optional["KnowledgeRetriever"] = None,
        tracing: Optional["TracingClient"] = None,
        config: Optional[SubAgentConfig] = None,
    ):
        """Initialize the sub-agent.
        
        Args:
            inference: LLM inference client
            retriever: Knowledge retriever (optional)
            tracing: Tracing client (optional)
            config: Sub-agent configuration
        """
        self._inference = inference
        self._retriever = retriever
        self._tracing = tracing
        self._config = config or SubAgentConfig()

    @abstractmethod
    async def execute(
        self,
        ctx: "RequestContext",
        blackboard: "Blackboard",
        step: PlanStep,
        system_prompt: str,
    ) -> SubAgentResult:
        """Execute the sub-agent's task.
        
        Args:
            ctx: Request context with user info
            blackboard: Shared state (variables, findings, tool results)
            step: The plan step to execute
            system_prompt: Agent's system prompt
            
        Returns:
            SubAgentResult with output or error
        """
        pass

    async def _execute_with_retry(
        self,
        ctx: "RequestContext",
        blackboard: "Blackboard",
        step: PlanStep,
        system_prompt: str,
    ) -> SubAgentResult:
        """Execute with retry on transient failures."""
        last_error: Optional[str] = None
        attempts = 0
        
        while attempts <= self._config.max_retries:
            attempts += 1
            try:
                result = await self.execute(ctx, blackboard, step, system_prompt)
                if result.success or not self._config.retry_on_failure:
                    return result
                last_error = result.error
            except Exception as e:
                logger.warning(f"{self.name} attempt {attempts} failed: {e}")
                last_error = str(e)
                if not self._config.retry_on_failure or attempts > self._config.max_retries:
                    return SubAgentResult.failure_result(last_error)
        
        return SubAgentResult.failure_result(last_error or "Unknown error after retries")

    async def _make_llm_call(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[str, int, Optional[list[Any]]]:
        """Make an LLM call.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            tools: Optional tool definitions
            
        Returns:
            Tuple of (content, tokens_used, tool_calls)
        """
        from agentcore.inference import InferenceConfig
        
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_prompt),
        ]
        
        config = InferenceConfig(
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        
        response = await self._inference.complete(
            messages,
            tools=tools,
            config=config,
        )
        
        tokens = response.total_tokens
        return response.content or "", tokens, response.tool_calls

    def _get_blackboard_context(self, blackboard: "Blackboard") -> str:
        """Get formatted blackboard context for prompts.
        
        Args:
            blackboard: The blackboard
            
        Returns:
            Formatted context string
        """
        parts = []
        
        # Variables
        variables = blackboard.get_all_variables()
        if variables:
            var_text = "\n".join(f"- {k}: {v}" for k, v in list(variables.items())[:10])
            parts.append(f"Variables:\n{var_text}")
        
        # Recent findings
        findings = blackboard.findings[-self._config.max_findings_in_context:]
        if findings:
            findings_text = "\n".join(f"- [{f.source}] {f.content[:200]}" for f in findings)
            parts.append(f"Findings:\n{findings_text}")
        
        # Recent tool results
        tool_results = blackboard.tool_results[-self._config.max_tool_results_in_context:]
        if tool_results:
            results_text = []
            for r in tool_results:
                if r.success:
                    results_text.append(f"- {r.tool_name}: {str(r.get_result_for_context())[:200]}")
                else:
                    results_text.append(f"- {r.tool_name}: FAILED - {r.error}")
            parts.append(f"Tool Results:\n" + "\n".join(results_text))
        
        return "\n\n".join(parts) if parts else "No context available."

    def _truncate(self, text: str, max_chars: int) -> str:
        """Truncate text to max characters."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 3] + "..."
