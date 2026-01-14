"""Planner sub-agent for task decomposition."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Optional

from agentcore.core.models import ExecutionPlan, PlanStep, SubAgentResult
from agentcore.prompts import get_prompt_registry
from agentcore.sub_agents.base import SubAgentBase, SubAgentConfig
from agentcore.tracing.decorators import trace_agent

if TYPE_CHECKING:
    from agentcore.auth.context import RequestContext
    from agentcore.core.blackboard import Blackboard
    from agentcore.inference.client import InferenceClient
    from agentcore.knowledge.retriever import KnowledgeRetriever
    from agentcore.tracing.client import TracingClient

logger = logging.getLogger(__name__)


class PlannerSubAgent(SubAgentBase):
    """Sub-agent that decomposes user requests into execution plans.
    
    The Planner:
    - Analyzes the user query and available knowledge
    - Creates a step-by-step execution plan
    - Assigns appropriate sub-agents to each step
    - Handles replanning when execution results require plan changes
    """

    name: str = "planner"
    description: str = "Decomposes user requests into execution plans"

    def __init__(
        self,
        inference: "InferenceClient",
        retriever: Optional["KnowledgeRetriever"] = None,
        tracing: Optional["TracingClient"] = None,
        config: Optional[SubAgentConfig] = None,
    ):
        super().__init__(inference, retriever, tracing, config)
        
        # Planner-specific defaults
        if config is None:
            self._config = SubAgentConfig(
                temperature=0.3,  # Lower temp for more consistent planning
                max_tokens=2048,
            )

    @trace_agent("planner_execute")
    async def execute(
        self,
        ctx: "RequestContext",
        blackboard: "Blackboard",
        step: PlanStep,
        system_prompt: str,
    ) -> SubAgentResult:
        """Execute the planning task.
        
        Note: For the Planner, the 'step' parameter is a meta-step
        that triggers plan creation. The actual output is an ExecutionPlan.
        """
        try:
            # Get knowledge context for planning
            knowledge_context = await self._get_knowledge_context(ctx, blackboard.query)
            
            # Check if this is a replan
            replan_reason = blackboard.get("_replan_reason")
            
            # Build planning prompt
            user_prompt = self._build_planning_prompt(
                query=blackboard.query,
                knowledge_context=knowledge_context,
                blackboard_context=self._get_blackboard_context(blackboard),
                replan_reason=replan_reason,
            )
            
            # Make LLM call
            content, tokens, _ = await self._make_llm_call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            
            # Parse the plan
            plan = self._parse_plan(blackboard.query, content)
            
            # Store plan in output
            return SubAgentResult.success_result(
                output=plan,
                tokens_used=tokens,
            )
            
        except Exception as e:
            logger.exception(f"Planner failed: {e}")
            return SubAgentResult.failure_result(str(e))

    async def create_plan(
        self,
        ctx: "RequestContext",
        query: str,
        system_prompt: str,
        blackboard: Optional["Blackboard"] = None,
    ) -> ExecutionPlan:
        """Create an execution plan for a query.
        
        Convenience method for creating plans outside the normal
        sub-agent execution flow.
        
        Args:
            ctx: Request context
            query: User query
            system_prompt: Agent's system prompt
            blackboard: Optional blackboard for context
            
        Returns:
            ExecutionPlan
        """
        # Get knowledge context
        knowledge_context = await self._get_knowledge_context(ctx, query)
        
        # Get blackboard context if available
        blackboard_context = ""
        if blackboard:
            blackboard_context = self._get_blackboard_context(blackboard)
        
        # Build prompt
        user_prompt = self._build_planning_prompt(
            query=query,
            knowledge_context=knowledge_context,
            blackboard_context=blackboard_context,
        )
        
        # Make LLM call
        content, _, _ = await self._make_llm_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        return self._parse_plan(query, content)

    async def replan(
        self,
        ctx: "RequestContext",
        current_plan: ExecutionPlan,
        reason: str,
        system_prompt: str,
        blackboard: "Blackboard",
    ) -> ExecutionPlan:
        """Create a revised plan based on execution results.
        
        Args:
            ctx: Request context
            current_plan: The current plan being executed
            reason: Why replanning is needed
            system_prompt: Agent's system prompt
            blackboard: Current blackboard state
            
        Returns:
            Updated ExecutionPlan
        """
        knowledge_context = await self._get_knowledge_context(ctx, current_plan.query)
        
        # Include current plan state in prompt
        completed_steps = "\n".join(
            f"- {s.id}: {s.description} [COMPLETED] -> {s.result}"
            for s in current_plan.completed_steps
        )
        
        failed_steps = "\n".join(
            f"- {s.id}: {s.description} [FAILED] -> {s.error}"
            for s in current_plan.failed_steps
        )
        
        user_prompt = f"""You need to revise the execution plan.

Original Query: {current_plan.query}
Original Goal: {current_plan.goal}

Reason for Replanning: {reason}

Completed Steps:
{completed_steps if completed_steps else "None"}

Failed Steps:
{failed_steps if failed_steps else "None"}

{f"Relevant Knowledge:{chr(10)}{knowledge_context}" if knowledge_context else ""}

Current Context:
{self._get_blackboard_context(blackboard)}

Create a revised plan with the remaining steps needed to complete the goal.
Keep completed step results and build on them.

Output as JSON:
{{
    "goal": "Updated goal if needed",
    "steps": [
        {{
            "id": "step_N",
            "description": "Brief description",
            "sub_agent": "researcher|analyzer|executor|synthesizer",
            "instruction": "Detailed instructions",
            "depends_on": []
        }}
    ]
}}"""

        content, _, _ = await self._make_llm_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        # Parse new steps
        new_plan = self._parse_plan(current_plan.query, content)
        
        # Merge with current plan (keep completed steps)
        current_plan.replan(new_plan.steps)
        if new_plan.goal != current_plan.goal:
            current_plan.goal = new_plan.goal
        
        return current_plan

    async def _get_knowledge_context(self, ctx: "RequestContext", query: str) -> str:
        """Get knowledge context for planning."""
        if self._retriever is None:
            return ""
        
        try:
            bundle = await self._retriever.retrieve_for_planning(ctx, query)
            return bundle.get_for_planning()
        except Exception as e:
            logger.warning(f"Failed to retrieve knowledge for planning: {e}")
            return ""

    def _build_planning_prompt(
        self,
        query: str,
        knowledge_context: str,
        blackboard_context: str,
        replan_reason: Optional[str] = None,
    ) -> str:
        prompts = get_prompt_registry()
        return prompts.get(
            "agent-planner",
            query=query,
            knowledge_context=knowledge_context,
            blackboard_context=blackboard_context,
            replan_reason=replan_reason or "",
        )

    def _parse_plan(self, query: str, content: str) -> ExecutionPlan:
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
            else:
                logger.warning("No JSON found in plan response, using fallback")
                return self._fallback_plan(query)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse plan JSON: {e}")
            return self._fallback_plan(query)

        # Build plan from parsed data
        steps = []
        for step_data in data.get("steps", []):
            steps.append(PlanStep(
                id=step_data.get("id", f"step_{len(steps)+1}"),
                description=step_data.get("description", ""),
                sub_agent=step_data.get("sub_agent", "researcher"),
                instruction=step_data.get("instruction", ""),
                depends_on=step_data.get("depends_on", []),
            ))

        return ExecutionPlan(
            query=query,
            goal=data.get("goal", "Complete the user's request"),
            steps=steps,
        )

    def _fallback_plan(self, query: str) -> ExecutionPlan:
        """Create a fallback plan when parsing fails."""
        return ExecutionPlan(
            query=query,
            goal="Answer the user's query",
            steps=[
                PlanStep(
                    id="step_1",
                    description="Research the query",
                    sub_agent="researcher",
                    instruction=f"Find information relevant to: {query}",
                ),
                PlanStep(
                    id="step_2",
                    description="Generate response",
                    sub_agent="synthesizer",
                    instruction="Generate a helpful response based on the research.",
                    depends_on=["step_1"],
                ),
            ],
        )
