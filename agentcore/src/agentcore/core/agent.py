"""Base agent with ReAct loop."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional
from uuid import uuid4

from agentcore.core.blackboard import Blackboard
from agentcore.core.models import (
    AgentState,
    ExecutionPlan,
    PlanStep,
    StepStatus,
    SubAgentResult,
)
from agentcore.inference import Message, MessageRole
from agentcore.prompts import get_prompt_registry
from agentcore.settings.agent import AgentSettings
from agentcore.tools.decorator import is_tool
from agentcore.tools.registry import ToolRegistry
from agentcore.tools.executor import ToolExecutor
from agentcore.tracing.decorators import trace_agent

if TYPE_CHECKING:
    from agentcore.auth.context import RequestContext
    from agentcore.inference.client import InferenceClient
    from agentcore.knowledge.client import KnowledgeClient
    from agentcore.knowledge.retriever import KnowledgeRetriever
    from agentcore.registry.models import AgentInfo
    from agentcore.tracing.client import TracingClient

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for domain agents.
    
    Provides:
    - ReAct loop for iterative planning and execution
    - Blackboard for state management
    - Integration with inference, knowledge, and tracing
    - Streaming response generation
    
    Subclasses must implement:
    - get_system_prompt(): Return the agent's system prompt
    - get_tools(): Return available tools (optional)
    
    Subclasses may override:
    - plan(): Custom planning logic
    - execute_step(): Custom step execution
    """

    # Agent identity (override in subclass)
    agent_id: str = "base"
    name: str = "Base Agent"
    description: str = "Base agent implementation"
    version: str = "1.0.0"
    team: str = "platform"

    # Capabilities for registration (override in subclass)
    capabilities: list[str] = []
    domains: list[str] = []
    example_queries: list[str] = []

    def __init__(
        self,
        inference: "InferenceClient",
        knowledge: "KnowledgeClient",
        tracing: Optional["TracingClient"] = None,
        settings: Optional[AgentSettings] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        """Initialize the agent.
        
        Args:
            inference: LLM inference client
            knowledge: Knowledge retrieval client
            tracing: Optional tracing client
            settings: Agent behavior settings
            tool_registry: Optional pre-configured tool registry. If not provided,
                creates a new registry and auto-registers @tool decorated methods.
        """
        self._inference = inference
        self._knowledge = knowledge
        self._tracing = tracing
        self._settings = settings or AgentSettings()
        
        # Initialize tool registry and executor
        self._tool_registry = tool_registry or ToolRegistry()
        self._tool_executor = ToolExecutor(
            registry=self._tool_registry,
            tracing=tracing,
        )
        
        # Auto-register @tool decorated methods from this agent
        if tool_registry is None:
            self._auto_register_tools()
        
        # Lazy-init retriever
        self._retriever: Optional["KnowledgeRetriever"] = None
    
    def _auto_register_tools(self) -> int:
        """Auto-register all @tool decorated methods from this agent.
        
        Returns:
            Number of tools registered
        """
        count = self._tool_registry.register_all(self)
        if count > 0:
            logger.info(f"Auto-registered {count} tools for agent '{self.agent_id}'")
        return count

    @property
    def retriever(self) -> "KnowledgeRetriever":
        """Get the knowledge retriever."""
        if self._retriever is None:
            from agentcore.knowledge.retriever import KnowledgeRetriever
            self._retriever = KnowledgeRetriever(self._knowledge)
        return self._retriever

    # =========================================================================
    # Abstract methods (must implement)
    # =========================================================================

    @abstractmethod
    def get_system_prompt(self, ctx: "RequestContext") -> str:
        """Get the system prompt for this agent.
        
        Args:
            ctx: Request context with user info
            
        Returns:
            System prompt string
        """
        pass

    def get_tools(self, ctx: Optional["RequestContext"] = None) -> list[dict[str, Any]]:
        """Get available tools in OpenAI format.
        
        Returns tools from the registry, filtered by user permissions if ctx provided.
        Subclasses can override to add additional tools or filtering.
        
        Args:
            ctx: Optional request context for permission filtering
            
        Returns:
            List of tool definitions in OpenAI format
        """
        return self._tool_registry.get_openai_tools(ctx=ctx)
    
    @property
    def tool_registry(self) -> ToolRegistry:
        """Get the tool registry."""
        return self._tool_registry
    
    @property
    def tool_executor(self) -> ToolExecutor:
        """Get the tool executor."""
        return self._tool_executor

    # =========================================================================
    # Main entry point
    # =========================================================================

    @trace_agent("handle_message")
    async def handle_message(
        self,
        ctx: "RequestContext",
        message: str,
        attachments: Optional[list[dict[str, Any]]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle a user message.
        
        Main entry point for agent execution. Runs the ReAct loop
        and yields streaming responses.
        
        Args:
            ctx: Request context
            message: User message
            attachments: Optional attachments
            
        Yields:
            Response chunks (progress, markdown, suggestions, etc.)
        """
        # Create blackboard
        blackboard = Blackboard.create(ctx=ctx, query=message)
        blackboard.add_message("user", message)

        # Start trace
        trace_ctx = None
        if self._tracing:
            trace_ctx = self._tracing.start_trace(
                ctx=ctx,
                name=f"{self.agent_id}:handle_message",
                agent_id=self.agent_id,
                metadata={"query": message},
            )

        try:
            # Yield initial progress
            yield self._progress("Thinking...")

            # Run ReAct loop
            async for chunk in self._react_loop(ctx, blackboard):
                yield chunk

        except Exception as e:
            logger.exception(f"Agent error: {e}")
            yield self._error(str(e))
            
            if trace_ctx and self._tracing:
                self._tracing.end_trace(trace_ctx, output=str(e), level="ERROR")
        else:
            if trace_ctx and self._tracing:
                self._tracing.end_trace(
                    trace_ctx,
                    output=blackboard.plan.final_result if blackboard.plan else None,
                )

    # =========================================================================
    # ReAct Loop
    # =========================================================================

    async def _react_loop(
        self,
        ctx: "RequestContext",
        blackboard: Blackboard,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the ReAct (Reason + Act) loop.
        
        1. Plan: Generate execution plan
        2. Execute: Run each step with appropriate sub-agent
        3. Replan: If needed, revise the plan
        4. Synthesize: Generate final response
        """
        iteration = 0
        replan_count = 0

        while iteration < self._settings.max_iterations:
            iteration += 1

            # Plan (or replan)
            if blackboard.plan is None or (
                self._settings.enable_replanning and 
                self._needs_replan(blackboard)
            ):
                yield self._progress("Planning...")
                blackboard.plan = await self._plan(ctx, blackboard)
                
                if self._tracing:
                    trace_ctx = self._tracing.__class__.current()
                    if trace_ctx:
                        self._tracing.log_decision(
                            trace_ctx,
                            decision_type="plan",
                            decision=f"Created plan with {len(blackboard.plan.steps)} steps",
                            reasoning=blackboard.plan.goal,
                        )

            # Get current step
            current_step = blackboard.plan.current_step
            if current_step is None:
                # All steps complete
                break

            # Execute current step
            yield self._progress(f"Working on: {current_step.description}")
            
            current_step.start()
            result = await self._execute_step(ctx, blackboard, current_step)

            if result.success:
                current_step.complete(result.output)
                
                # Check if replan needed
                if result.replan_needed:
                    replan_count += 1
                    if replan_count > self._settings.max_replans:
                        logger.warning("Max replans exceeded")
                        break
                    # Mark plan for replanning
                    blackboard.set("_needs_replan", True, source="react")
                    blackboard.set("_replan_reason", result.replan_reason, source="react")
            else:
                current_step.fail(result.error or "Unknown error")
                
                # Decide whether to continue or fail
                if self._should_abort(blackboard, current_step):
                    yield self._error(f"Failed: {result.error}")
                    return

            # Check for HIL
            if blackboard.has_pending_interactions():
                yield self._hil_request(blackboard.pending_interactions[-1])
                return  # Wait for human input

        # Synthesize final response
        yield self._progress("Generating response...")
        async for chunk in self._synthesize(ctx, blackboard):
            yield chunk

        # Mark plan complete
        if blackboard.plan:
            blackboard.plan.is_complete = True

    # =========================================================================
    # Planning
    # =========================================================================

    async def _plan(
        self,
        ctx: "RequestContext",
        blackboard: Blackboard,
    ) -> ExecutionPlan:
        """Generate an execution plan.
        
        Override for custom planning logic.
        """
        # Get knowledge context for planning
        knowledge_context = ""
        try:
            bundle = await self.retriever.retrieve_for_planning(ctx, blackboard.query)
            knowledge_context = bundle.get_for_planning()
        except Exception as e:
            logger.warning(f"Failed to retrieve knowledge for planning: {e}")

        system_prompt = self.get_system_prompt(ctx)
        replan_reason = blackboard.get("_replan_reason") if blackboard.get("_needs_replan") else None
        
        prompts = get_prompt_registry()
        planning_prompt = prompts.get(
            "agent-planner",
            query=blackboard.query,
            knowledge_context=knowledge_context,
            blackboard_context="",
            replan_reason=replan_reason or "",
        )

        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=planning_prompt),
        ]

        response = await self._inference.complete(messages)
        
        # Parse plan from response
        return self._parse_plan(blackboard.query, response.content)

    def _parse_plan(self, query: str, content: str) -> ExecutionPlan:
        """Parse LLM response into ExecutionPlan."""
        import json
        
        # Try to extract JSON from response
        try:
            # Find JSON in response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
            else:
                raise ValueError("No JSON found in response")
        except json.JSONDecodeError:
            # Fallback to simple plan
            logger.warning("Failed to parse plan JSON, using fallback")
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

    def _needs_replan(self, blackboard: Blackboard) -> bool:
        """Check if plan needs revision."""
        return blackboard.get("_needs_replan", False)

    # =========================================================================
    # Step Execution
    # =========================================================================

    async def _execute_step(
        self,
        ctx: "RequestContext",
        blackboard: Blackboard,
        step: PlanStep,
    ) -> SubAgentResult:
        """Execute a single plan step.
        
        Routes to appropriate sub-agent based on step.sub_agent.
        Override for custom execution logic.
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            if step.sub_agent == "researcher":
                result = await self._execute_researcher(ctx, blackboard, step)
            elif step.sub_agent == "analyzer":
                result = await self._execute_analyzer(ctx, blackboard, step)
            elif step.sub_agent == "executor":
                result = await self._execute_executor(ctx, blackboard, step)
            elif step.sub_agent == "synthesizer":
                result = await self._execute_synthesizer(ctx, blackboard, step)
            else:
                result = SubAgentResult.failure_result(f"Unknown sub-agent: {step.sub_agent}")
            
            # Add duration
            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            return SubAgentResult(
                success=result.success,
                output=result.output,
                error=result.error,
                tokens_used=result.tokens_used,
                duration_ms=duration,
                replan_needed=result.replan_needed,
                replan_reason=result.replan_reason,
            )
            
        except Exception as e:
            logger.exception(f"Step execution failed: {e}")
            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            return SubAgentResult.failure_result(str(e), duration_ms=duration)

    async def _execute_researcher(
        self,
        ctx: "RequestContext",
        blackboard: Blackboard,
        step: PlanStep,
    ) -> SubAgentResult:
        """Execute a research step.
        
        Gathers information using knowledge base and tools.
        """
        # Get knowledge context
        try:
            bundle = await self.retriever.retrieve_for_research(ctx, step.instruction)
            knowledge_context = bundle.get_for_research()
        except Exception as e:
            logger.warning(f"Knowledge retrieval failed: {e}")
            knowledge_context = ""

        # Build research prompt
        prompt = f"""Research Task: {step.instruction}

{f"Relevant Knowledge:{chr(10)}{knowledge_context}" if knowledge_context else ""}

Current Context:
{blackboard.get_context_for_llm(max_tokens=2000)}

Gather relevant information and report your findings."""

        messages = [
            Message(role=MessageRole.SYSTEM, content=self.get_system_prompt(ctx)),
            Message(role=MessageRole.USER, content=prompt),
        ]

        tools = self.get_tools(ctx)
        
        response = await self._inference.complete(
            messages,
            tools=tools if tools else None,
        )

        if response.tool_calls:
            tool_calls = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in response.tool_calls
            ]
            await self._tool_executor.execute_many(
                ctx=ctx,
                tool_calls=tool_calls,
                blackboard=blackboard,
                parallel=True,
            )

        if response.content:
            blackboard.add_finding(
                source="researcher",
                content=response.content,
            )

        return SubAgentResult.success_result(
            output=response.content,
            tokens_used=response.usage.total_tokens if response.usage else 0,
        )

    async def _execute_analyzer(
        self,
        ctx: "RequestContext",
        blackboard: Blackboard,
        step: PlanStep,
    ) -> SubAgentResult:
        """Execute an analysis step."""
        # Get relevant schemas
        try:
            bundle = await self.retriever.retrieve_for_analysis(ctx, step.instruction)
            schema_context = "\n\n".join(s.to_prompt_text() for s in bundle.schemas[:3])
        except Exception as e:
            logger.warning(f"Schema retrieval failed: {e}")
            schema_context = ""

        prompt = f"""Analysis Task: {step.instruction}

{f"Relevant Schemas:{chr(10)}{schema_context}" if schema_context else ""}

Current Context:
{blackboard.get_context_for_llm(max_tokens=2000)}

Findings so far:
{chr(10).join(f"- {f.content}" for f in blackboard.findings[-5:])}

Analyze the available information and provide insights."""

        messages = [
            Message(role=MessageRole.SYSTEM, content=self.get_system_prompt(ctx)),
            Message(role=MessageRole.USER, content=prompt),
        ]

        response = await self._inference.complete(messages)

        if response.content:
            blackboard.add_finding(
                source="analyzer",
                content=response.content,
            )

        return SubAgentResult.success_result(
            output=response.content,
            tokens_used=response.usage.total_tokens if response.usage else 0,
        )

    async def _execute_executor(
        self,
        ctx: "RequestContext",
        blackboard: Blackboard,
        step: PlanStep,
    ) -> SubAgentResult:
        """Execute an action step.
        
        Performs actions that modify state (create, update, delete).
        """
        prompt = f"""Action Task: {step.instruction}

Current Context:
{blackboard.get_context_for_llm(max_tokens=2000)}

Execute the required action using the available tools."""

        messages = [
            Message(role=MessageRole.SYSTEM, content=self.get_system_prompt(ctx)),
            Message(role=MessageRole.USER, content=prompt),
        ]

        tools = self.get_tools(ctx)
        
        response = await self._inference.complete(
            messages,
            tools=tools if tools else None,
        )

        if response.tool_calls:
            for tool_call in response.tool_calls:
                requires_hil, hil_prompt = self._tool_executor.check_hil_required(
                    tool_call.name, tool_call.arguments
                )
                if requires_hil:
                    interaction_id = blackboard.add_pending_interaction(
                        interaction_type="confirm",
                        prompt=hil_prompt or f"Confirm execution of {tool_call.name}?",
                        metadata={"tool_call_id": tool_call.id, "tool_name": tool_call.name},
                    )
                    blackboard.set(f"_pending_tool_{tool_call.id}", tool_call.arguments, source="executor")
                    continue
                
                await self._tool_executor.execute(
                    ctx=ctx,
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                    tool_call_id=tool_call.id,
                    blackboard=blackboard,
                )

        return SubAgentResult.success_result(
            output=response.content,
            tokens_used=response.usage.total_tokens if response.usage else 0,
        )

    async def _execute_synthesizer(
        self,
        ctx: "RequestContext",
        blackboard: Blackboard,
        step: PlanStep,
    ) -> SubAgentResult:
        """Execute a synthesis step.
        
        Generates the final user-facing response.
        """
        # Gather all findings
        findings_text = "\n".join(f"- {f.content}" for f in blackboard.findings)
        
        # Get tool results summary
        results_text = ""
        for result in blackboard.tool_results[-5:]:
            if result.success:
                results_text += f"\n- {result.tool_name}: {result.get_result_for_context()}"
            else:
                results_text += f"\n- {result.tool_name}: Failed - {result.error}"

        prompt = f"""Synthesis Task: {step.instruction}

Original Query: {blackboard.query}

Research Findings:
{findings_text if findings_text else "No specific findings recorded."}

{f"Tool Results:{results_text}" if results_text else ""}

Generate a comprehensive, helpful response for the user.
Format your response in Markdown for readability."""

        messages = [
            Message(role=MessageRole.SYSTEM, content=self.get_system_prompt(ctx)),
            Message(role=MessageRole.USER, content=prompt),
        ]

        response = await self._inference.complete(messages)

        # Store final result
        if blackboard.plan:
            blackboard.plan.final_result = response.content

        return SubAgentResult.success_result(
            output=response.content,
            tokens_used=response.usage.total_tokens if response.usage else 0,
        )

    def _should_abort(self, blackboard: Blackboard, failed_step: PlanStep) -> bool:
        """Determine if execution should abort after a failure."""
        # Abort if synthesizer fails (can't generate response)
        if failed_step.sub_agent == "synthesizer":
            return True
        
        # Check if too many failures
        if blackboard.plan:
            failed_count = len(blackboard.plan.failed_steps)
            if failed_count >= 3:
                return True
        
        return False

    # =========================================================================
    # Response Synthesis
    # =========================================================================

    async def _synthesize(
        self,
        ctx: "RequestContext",
        blackboard: Blackboard,
    ) -> AsyncIterator[dict[str, Any]]:
        """Generate final response.
        
        Called after ReAct loop completes.
        """
        # If we already have a final result from synthesizer step, use it
        if blackboard.plan and blackboard.plan.final_result:
            yield self._markdown(blackboard.plan.final_result)
        else:
            # Fallback synthesis
            findings_text = "\n".join(f"- {f.content}" for f in blackboard.findings)
            
            prompt = f"""Generate a helpful response for the user.

Original Query: {blackboard.query}

Findings:
{findings_text if findings_text else "No specific findings."}

Format in Markdown."""

            messages = [
                Message(role=MessageRole.SYSTEM, content=self.get_system_prompt(ctx)),
                Message(role=MessageRole.USER, content=prompt),
            ]

            response = await self._inference.complete(messages)
            yield self._markdown(response.content)

        # Generate suggestions
        suggestions = await self._generate_suggestions(ctx, blackboard)
        if suggestions:
            yield self._suggestions(suggestions)

    async def _generate_suggestions(
        self,
        ctx: "RequestContext",
        blackboard: Blackboard,
    ) -> list[str]:
        """Generate follow-up suggestions."""
        prompt = f"""Based on this conversation, suggest 2-3 follow-up questions or actions the user might want to take.

Original Query: {blackboard.query}

Response Summary: {(blackboard.plan.final_result or "")[:500] if blackboard.plan else ""}

Output as a JSON array of strings."""

        messages = [
            Message(role=MessageRole.SYSTEM, content="Generate helpful follow-up suggestions."),
            Message(role=MessageRole.USER, content=prompt),
        ]

        try:
            response = await self._inference.complete(messages)
            
            # Parse suggestions
            import json
            content = response.content
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except Exception as e:
            logger.warning(f"Failed to generate suggestions: {e}")
        
        return []

    # =========================================================================
    # Response Helpers
    # =========================================================================

    def _progress(self, status: str) -> dict[str, Any]:
        """Create a progress response chunk."""
        return {
            "type": "component",
            "payload": {
                "component": "progress",
                "data": {"status": status},
            },
        }

    def _markdown(self, content: str) -> dict[str, Any]:
        """Create a markdown response chunk."""
        return {
            "type": "markdown",
            "payload": content,
        }

    def _suggestions(self, options: list[str]) -> dict[str, Any]:
        """Create a suggestions response chunk."""
        return {
            "type": "suggestions",
            "payload": {"options": options},
        }

    def _error(self, message: str) -> dict[str, Any]:
        """Create an error response chunk."""
        return {
            "type": "error",
            "payload": {"message": message},
        }

    def _hil_request(self, interaction: dict[str, Any]) -> dict[str, Any]:
        """Create a human-in-the-loop request."""
        return {
            "type": "component",
            "payload": {
                "component": "form" if interaction.get("form_schema") else "confirm",
                "data": interaction,
            },
        }

    # =========================================================================
    # Registration Info
    # =========================================================================

    def get_registration_info(self, base_url: str) -> "AgentInfo":
        """Get registration info for this agent.
        
        Args:
            base_url: Agent's base URL
            
        Returns:
            AgentInfo for registry registration
        """
        from agentcore.registry.models import AgentInfo
        
        return AgentInfo(
            agent_id=self.agent_id,
            name=self.name,
            description=self.description,
            base_url=base_url,
            capabilities=self.capabilities,
            domains=self.domains,
            example_queries=self.example_queries,
            version=self.version,
            team=self.team,
        )

    # =========================================================================
    # Human-in-the-Loop
    # =========================================================================

    async def handle_human_input(
        self,
        ctx: "RequestContext",
        interaction_id: str,
        response: Any,
        blackboard: Blackboard,
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle human input for pending interaction.
        
        Called when user responds to a HIL prompt.
        
        Args:
            ctx: Request context
            interaction_id: ID of the interaction
            response: User's response
            blackboard: Current blackboard state
            
        Yields:
            Response chunks
        """
        # Resolve the interaction
        if not blackboard.resolve_interaction(interaction_id, response):
            yield self._error(f"Unknown interaction: {interaction_id}")
            return

        # Store response in blackboard
        blackboard.set(f"hil_{interaction_id}", response, source="user")

        # Continue the ReAct loop
        async for chunk in self._react_loop(ctx, blackboard):
            yield chunk
