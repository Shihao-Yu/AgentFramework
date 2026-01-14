"""Synthesizer sub-agent for generating final responses."""

from __future__ import annotations

import json
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


class SynthesizerSubAgent(SubAgentBase):
    """Sub-agent that generates final user-facing responses.
    
    The Synthesizer:
    - Synthesizes findings, analysis, and action results
    - Generates clear, helpful responses for the user
    - Formats output appropriately (markdown, structured data, etc.)
    - Can generate follow-up suggestions
    """

    name: str = "synthesizer"
    description: str = "Generates final user-facing responses"

    def __init__(
        self,
        inference: "InferenceClient",
        retriever: Optional["KnowledgeRetriever"] = None,
        tracing: Optional["TracingClient"] = None,
        config: Optional[SubAgentConfig] = None,
    ):
        super().__init__(inference, retriever, tracing, config)
        
        # Synthesizer-specific defaults
        if config is None:
            self._config = SubAgentConfig(
                temperature=0.7,  # Slightly higher for natural responses
                max_tokens=4096,  # Longer for comprehensive responses
            )

    @trace_agent("synthesizer_execute")
    async def execute(
        self,
        ctx: "RequestContext",
        blackboard: "Blackboard",
        step: PlanStep,
        system_prompt: str,
    ) -> SubAgentResult:
        """Execute the synthesis task.
        
        Args:
            ctx: Request context
            blackboard: Shared state with all findings
            step: The plan step to execute
            system_prompt: Agent's system prompt
            
        Returns:
            SubAgentResult with the final response
        """
        try:
            # Build synthesis prompt
            user_prompt = self._build_synthesis_prompt(
                instruction=step.instruction,
                query=blackboard.query,
                findings=blackboard.findings,
                tool_results=blackboard.tool_results,
                blackboard_context=self._get_blackboard_context(blackboard),
            )
            
            # Make LLM call
            content, tokens, _ = await self._make_llm_call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            
            # Store in plan's final result
            if blackboard.plan:
                blackboard.plan.final_result = content
            
            return SubAgentResult.success_result(
                output=content,
                tokens_used=tokens,
            )
            
        except Exception as e:
            logger.exception(f"Synthesizer failed: {e}")
            return SubAgentResult.failure_result(str(e))

    async def synthesize(
        self,
        ctx: "RequestContext",
        query: str,
        findings: list[Any],
        system_prompt: str,
        format_type: str = "markdown",
    ) -> str:
        """Synthesize a response from findings.
        
        Convenience method for synthesis outside the normal sub-agent flow.
        
        Args:
            ctx: Request context
            query: Original user query
            findings: List of findings to synthesize
            system_prompt: Agent's system prompt
            format_type: Output format (markdown, json, plain)
            
        Returns:
            Synthesized response
        """
        # Format findings
        findings_text = "\n".join(
            f"- [{f.source if hasattr(f, 'source') else 'unknown'}] {f.content if hasattr(f, 'content') else str(f)}"
            for f in findings
        )
        
        format_instructions = self._get_format_instructions(format_type)
        
        user_prompt = f"""Generate a response for the user.

Original Query: {query}

Findings:
{findings_text}

{format_instructions}

Generate a comprehensive, helpful response."""

        content, _, _ = await self._make_llm_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        return content

    async def generate_suggestions(
        self,
        ctx: "RequestContext",
        query: str,
        response: str,
        system_prompt: str,
        num_suggestions: int = 3,
    ) -> list[str]:
        """Generate follow-up suggestions.
        
        Args:
            ctx: Request context
            query: Original user query
            response: The response that was generated
            system_prompt: Agent's system prompt
            num_suggestions: Number of suggestions to generate
            
        Returns:
            List of follow-up suggestions
        """
        user_prompt = f"""Based on this conversation, suggest {num_suggestions} follow-up questions or actions the user might want to take.

Original Query: {query}

Response Summary: {response[:500] if len(response) > 500 else response}

Output as a JSON array of strings, e.g.:
["suggestion 1", "suggestion 2", "suggestion 3"]

Keep suggestions:
- Specific and actionable
- Related to the original query
- Helpful for the user's next steps"""

        content, _, _ = await self._make_llm_call(
            system_prompt="Generate helpful follow-up suggestions.",
            user_prompt=user_prompt,
        )
        
        # Parse suggestions from response
        try:
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
        
        return []

    async def summarize(
        self,
        ctx: "RequestContext",
        content: str,
        max_length: int = 200,
        system_prompt: str = "You are a helpful assistant.",
    ) -> str:
        """Summarize content to a specified length.
        
        Args:
            ctx: Request context
            content: Content to summarize
            max_length: Maximum length in characters
            system_prompt: System prompt
            
        Returns:
            Summarized content
        """
        user_prompt = f"""Summarize the following content in {max_length} characters or less:

{content}

Provide a concise summary that captures the key points."""

        summary, _, _ = await self._make_llm_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        # Ensure length constraint
        if len(summary) > max_length:
            summary = summary[:max_length - 3] + "..."
        
        return summary

    def _build_synthesis_prompt(
        self,
        instruction: str,
        query: str,
        findings: list[Any],
        tool_results: list[Any],
        blackboard_context: str,
    ) -> str:
        """Build the synthesis prompt using the prompt registry."""
        # Format findings
        findings_text = ""
        if findings:
            findings_text = "\n".join(
                f"- [{f.source}] {f.content}"
                for f in findings[-15:]  # Last 15 findings
            )
        
        # Format tool results
        results_text = ""
        if tool_results:
            for r in tool_results[-10:]:  # Last 10 results
                if r.success:
                    results_text += f"\n- {r.tool_name}: {str(r.get_result_for_context())[:300]}"
                else:
                    results_text += f"\n- {r.tool_name}: FAILED - {r.error}"
        
        prompts = get_prompt_registry()
        return prompts.get(
            "agent-synthesizer",
            instruction=instruction,
            query=query,
            findings=findings_text if findings_text else "No specific findings recorded.",
            tool_results=results_text,
            blackboard_context=blackboard_context,
        )

    def _get_format_instructions(self, format_type: str) -> str:
        """Get formatting instructions based on format type."""
        instructions = {
            "markdown": """Format your response in Markdown:
- Use headers (##) for sections
- Use bullet points for lists
- Use **bold** for emphasis
- Use code blocks for technical content""",
            
            "json": """Format your response as JSON:
{
    "summary": "brief summary",
    "details": ["detail 1", "detail 2"],
    "recommendations": ["recommendation 1"]
}""",
            
            "plain": "Format your response as plain text without special formatting.",
            
            "structured": """Format your response with clear sections:
SUMMARY:
[Brief summary]

DETAILS:
[Detailed information]

RECOMMENDATIONS:
[Any recommendations or next steps]""",
        }
        
        return instructions.get(format_type, instructions["markdown"])

    async def format_response(
        self,
        content: str,
        format_type: str,
        system_prompt: str = "You are a helpful assistant.",
    ) -> str:
        """Reformat a response to a specific format.
        
        Args:
            content: Content to reformat
            format_type: Target format (markdown, json, plain, structured)
            system_prompt: System prompt
            
        Returns:
            Reformatted content
        """
        format_instructions = self._get_format_instructions(format_type)
        
        user_prompt = f"""Reformat the following content:

{content}

{format_instructions}"""

        formatted, _, _ = await self._make_llm_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        return formatted
