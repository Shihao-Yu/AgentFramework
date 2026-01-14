"""Analyzer sub-agent for data analysis and reasoning."""

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


class AnalyzerSubAgent(SubAgentBase):
    """Sub-agent that analyzes data and makes decisions.
    
    The Analyzer:
    - Analyzes data gathered by the Researcher
    - Makes comparisons and draws conclusions
    - Identifies patterns and anomalies
    - Provides structured analysis results
    - Can signal when replanning is needed
    """

    name: str = "analyzer"
    description: str = "Analyzes data and makes comparisons"

    def __init__(
        self,
        inference: "InferenceClient",
        retriever: Optional["KnowledgeRetriever"] = None,
        tracing: Optional["TracingClient"] = None,
        config: Optional[SubAgentConfig] = None,
    ):
        super().__init__(inference, retriever, tracing, config)
        
        # Analyzer-specific defaults
        if config is None:
            self._config = SubAgentConfig(
                temperature=0.3,  # Lower temp for consistent analysis
                max_tokens=2048,
            )

    @trace_agent("analyzer_execute")
    async def execute(
        self,
        ctx: "RequestContext",
        blackboard: "Blackboard",
        step: PlanStep,
        system_prompt: str,
    ) -> SubAgentResult:
        """Execute the analysis task.
        
        Args:
            ctx: Request context
            blackboard: Shared state with findings and data
            step: The plan step to execute
            system_prompt: Agent's system prompt
            
        Returns:
            SubAgentResult with analysis
        """
        try:
            # Get schema context for analysis
            schema_context = await self._get_schema_context(ctx, step.instruction)
            
            # Build analysis prompt
            user_prompt = self._build_analysis_prompt(
                instruction=step.instruction,
                query=blackboard.query,
                schema_context=schema_context,
                blackboard_context=self._get_blackboard_context(blackboard),
                findings=blackboard.findings,
            )
            
            # Make LLM call
            content, tokens, _ = await self._make_llm_call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            
            # Check if analysis suggests replanning
            replan_needed, replan_reason = self._check_for_replan(content)
            
            # Add analysis to blackboard
            if content:
                blackboard.add_finding(
                    source="analyzer",
                    content=content,
                )
            
            if replan_needed:
                return SubAgentResult.replan_result(
                    reason=replan_reason or "Analysis indicates plan revision needed",
                    output=content,
                )
            
            return SubAgentResult.success_result(
                output=content,
                tokens_used=tokens,
            )
            
        except Exception as e:
            logger.exception(f"Analyzer failed: {e}")
            return SubAgentResult.failure_result(str(e))

    async def _get_schema_context(self, ctx: "RequestContext", query: str) -> str:
        """Get schema context for analysis."""
        if self._retriever is None:
            return ""
        
        try:
            bundle = await self._retriever.retrieve_for_analysis(ctx, query)
            # Format schemas for context
            if bundle.schemas:
                return "\n\n".join(s.to_prompt_text() for s in bundle.schemas[:5])
            return ""
        except Exception as e:
            logger.warning(f"Failed to retrieve schemas for analysis: {e}")
            return ""

    def _build_analysis_prompt(
        self,
        instruction: str,
        query: str,
        schema_context: str,
        blackboard_context: str,
        findings: list[Any],
    ) -> str:
        """Build the analysis prompt using the prompt registry."""
        # Format findings
        findings_text = ""
        if findings:
            findings_text = "\n".join(
                f"- [{f.source}] {f.content}"
                for f in findings[-10:]  # Last 10 findings
            )
        
        prompts = get_prompt_registry()
        return prompts.get(
            "agent-analyzer",
            instruction=instruction,
            query=query,
            schema_context=schema_context,
            blackboard_context=blackboard_context,
            findings=findings_text if findings_text else "No findings yet.",
        )

    def _check_for_replan(self, content: str) -> tuple[bool, Optional[str]]:
        """Check if the analysis suggests replanning.
        
        Args:
            content: Analysis content
            
        Returns:
            Tuple of (replan_needed, replan_reason)
        """
        if "REPLAN_NEEDED:" in content:
            # Extract the reason
            try:
                start = content.index("REPLAN_NEEDED:") + len("REPLAN_NEEDED:")
                # Find end of line or end of content
                end = content.find("\n", start)
                if end == -1:
                    end = len(content)
                reason = content[start:end].strip()
                return True, reason
            except (ValueError, IndexError):
                return True, "Analysis indicates plan revision needed"
        
        return False, None

    async def analyze(
        self,
        ctx: "RequestContext",
        query: str,
        data: Any,
        system_prompt: str,
    ) -> dict[str, Any]:
        """Perform standalone analysis on data.
        
        Convenience method for analysis outside the normal sub-agent flow.
        
        Args:
            ctx: Request context
            query: Analysis query
            data: Data to analyze
            system_prompt: Agent's system prompt
            
        Returns:
            Analysis results as dict
        """
        user_prompt = f"""Analyze the following data:

Query: {query}

Data:
{json.dumps(data, indent=2, default=str) if isinstance(data, (dict, list)) else str(data)}

Provide your analysis in JSON format:
{{
    "observations": ["key observation 1", "key observation 2"],
    "analysis": "detailed analysis text",
    "conclusions": ["conclusion 1", "conclusion 2"],
    "confidence": "high|medium|low",
    "recommendations": ["recommendation 1"]
}}"""

        content, _, _ = await self._make_llm_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        # Try to parse as JSON
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
        
        # Return as plain text if JSON parsing fails
        return {
            "analysis": content,
            "confidence": "medium",
        }

    async def compare(
        self,
        ctx: "RequestContext",
        items: list[Any],
        criteria: list[str],
        system_prompt: str,
    ) -> dict[str, Any]:
        """Compare multiple items against criteria.
        
        Args:
            ctx: Request context
            items: Items to compare
            criteria: Comparison criteria
            system_prompt: Agent's system prompt
            
        Returns:
            Comparison results as dict
        """
        items_text = "\n".join(
            f"Item {i+1}: {json.dumps(item, default=str) if isinstance(item, (dict, list)) else str(item)}"
            for i, item in enumerate(items)
        )
        
        criteria_text = "\n".join(f"- {c}" for c in criteria)
        
        user_prompt = f"""Compare the following items:

{items_text}

Criteria for comparison:
{criteria_text}

Provide your comparison in JSON format:
{{
    "comparison_matrix": {{
        "criterion_1": {{"item_1": "value", "item_2": "value"}},
        "criterion_2": {{"item_1": "value", "item_2": "value"}}
    }},
    "summary": "overall comparison summary",
    "recommendation": "which item is preferred and why",
    "confidence": "high|medium|low"
}}"""

        content, _, _ = await self._make_llm_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        # Try to parse as JSON
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
        
        return {
            "comparison": content,
            "confidence": "medium",
        }
