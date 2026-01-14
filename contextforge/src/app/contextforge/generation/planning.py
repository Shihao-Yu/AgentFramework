"""
Query Planning Pipeline for Multi-Step Agentic Query Generation.

This module provides a "planned" interface that separates:
1. Question analysis and disambiguation
2. Plan generation and user confirmation
3. Step-by-step execution with context chaining

NOTE: This is a simplified version adapted for ContextForge.
The full version with plan storage will be implemented in Phase 8+.
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from ..core.planning_models import (
    DisambiguationCategory,
    DisambiguationOption,
    DisambiguationQuestion,
    PlanStatus,
    QueryPlan,
    QueryPlanStep,
    StepStatus,
)
from ..core.models import QueryType
from ..retrieval.context import RetrievalContext
from .pipeline import QueryGenerationPipeline, calculate_confidence
from .prompt_templates import get_plan_analysis_prompt

if TYPE_CHECKING:
    from ..storage.plan_storage import PlanStorage

logger = logging.getLogger(__name__)


class QueryPlanningPipeline:
    """
    Multi-step agentic query planning with disambiguation support.

    This pipeline provides a "planned" interface for query generation that:
    1. Analyzes questions to identify ambiguities
    2. Generates disambiguation questions for user clarification
    3. Creates multi-step query plans with chained execution

    Example:
        >>> planner = QueryPlanningPipeline(llm_client=llm_client)
        >>> plan = await planner.create_plan("acme", "orders", "Show recent orders")
        >>> # User answers disambiguation questions...
        >>> result = await planner.execute_plan(plan, run_query_func=execute_sql)
    """

    def __init__(
        self,
        llm_client: Any,
        retriever: Optional[Any] = None,
        prompt_manager: Optional[Any] = None,
        generation_pipeline: Optional[QueryGenerationPipeline] = None,
        plan_storage: Optional["PlanStorage"] = None,
    ):
        """
        Initialize planning pipeline.

        Args:
            llm_client: LLM client with submit_prompt method
            retriever: Context retriever for fields and examples
            prompt_manager: PromptManager for Langfuse integration (optional)
            generation_pipeline: Existing generation pipeline to reuse (optional)
            plan_storage: PlanStorage for persisting plans (optional)
        """
        self.llm_client = llm_client
        self.retriever = retriever
        self.prompt_manager = prompt_manager
        self.plan_storage = plan_storage

        # Lazy-loaded generation pipeline
        self._generation_pipeline = generation_pipeline

        logger.info("Initialized QueryPlanningPipeline")

    @property
    def generation_pipeline(self) -> QueryGenerationPipeline:
        """Lazy-load generation pipeline."""
        if self._generation_pipeline is None:
            self._generation_pipeline = QueryGenerationPipeline(
                llm_client=self.llm_client,
                retriever=self.retriever,
                prompt_manager=self.prompt_manager,
            )
        return self._generation_pipeline

    # =========================================================================
    # PHASE 1: Plan Creation
    # =========================================================================

    async def create_plan(
        self,
        tenant_id: str,
        document_name: str,
        question: str,
        query_type: QueryType = QueryType.POSTGRES,
        context_hints: Optional[Dict[str, Any]] = None,
    ) -> QueryPlan:
        """
        Analyze question and create initial plan with disambiguation questions.

        Process:
        1. Retrieve schema context
        2. LLM analysis: identify ambiguities, suggest approach
        3. Generate disambiguation questions
        4. Generate initial plan steps
        5. Return plan (optionally save to storage)

        Args:
            tenant_id: Tenant identifier
            document_name: Document name (dataset)
            question: User's natural language question
            query_type: Target query type
            context_hints: Optional hints to guide analysis

        Returns:
            QueryPlan with status AWAITING_DISAMBIGUATION or AWAITING_CONFIRMATION
        """
        plan_id = str(uuid.uuid4())

        logger.info(
            f"Creating plan for {tenant_id}/{document_name}: {question[:50]}..."
        )

        # Step 1: Retrieve context (if retriever available)
        if self.retriever:
            retrieval_context = self.retriever.retrieve(
                question=question,
                tenant_id=tenant_id,
                document_name=document_name,
            )
        else:
            retrieval_context = RetrievalContext(
                fields=[],
                expanded_fields=[],
                examples=[],
                documentation=[],
                field_adjacency={},
                expansion_stats={},
            )

        # Step 2: LLM analysis for ambiguities and plan
        analysis_result = await self._analyze_question(
            question=question,
            context=retrieval_context,
            context_hints=context_hints,
        )

        # Step 3: Generate disambiguation questions
        disambiguation_questions = self._build_disambiguation_questions(
            analysis_result.get("clarification_needs", [])
        )

        # Step 4: Generate initial plan steps
        steps = self._build_initial_steps(
            question=question,
            analysis=analysis_result,
        )

        # Step 5: Create plan
        status = (
            PlanStatus.AWAITING_DISAMBIGUATION
            if disambiguation_questions
            else PlanStatus.AWAITING_CONFIRMATION
        )

        plan = QueryPlan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            document_name=document_name,
            original_question=question,
            status=status,
            disambiguation_questions=disambiguation_questions,
            disambiguation_complete=(len(disambiguation_questions) == 0),
            steps=steps,
            analysis_summary=analysis_result.get("summary", ""),
            identified_ambiguities=analysis_result.get("ambiguities", []),
            suggested_approach=analysis_result.get("approach", ""),
        )

        # Save to storage if available
        if self.plan_storage:
            self.plan_storage.save_plan(
                plan,
                create_version=True,
                change_type="creation",
                change_description="Initial plan creation",
            )

        logger.info(
            f"Created plan {plan_id} with {len(steps)} steps, "
            f"{len(disambiguation_questions)} disambiguation questions"
        )

        return plan

    async def _analyze_question(
        self,
        question: str,
        context: RetrievalContext,
        context_hints: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        LLM analysis to identify ambiguities and plan approach.

        Returns:
            {
                "summary": str,
                "ambiguities": List[str],
                "clarification_needs": List[Dict],
                "approach": str,
                "suggested_steps": List[Dict],
                "requires_multi_step": bool,
            }
        """
        prompt = self._build_analysis_prompt(question, context, context_hints)

        response = self.llm_client.submit_prompt(
            [
                self.llm_client.system_message(
                    "You are an expert query planner. Analyze questions to identify "
                    "ambiguities, suggest clarifications, and plan multi-step query execution. "
                    "Always respond with valid JSON."
                ),
                self.llm_client.user_message(prompt),
            ]
        )

        return self._parse_analysis_response(response)

    def _build_analysis_prompt(
        self,
        question: str,
        context: RetrievalContext,
        hints: Optional[Dict],
    ) -> str:
        """Build the analysis prompt for question decomposition."""
        # Format schema fields
        fields_text = []
        for f in context.all_fields[:20]:
            qualified = f.qualified_name or f.name
            fields_text.append(f"- {qualified} ({f.type}): {f.description or ''}")

        # Format examples
        examples_text = []
        for ex in context.examples[:5]:
            if hasattr(ex, "title") and hasattr(ex, "content"):
                examples_text.append(
                    f"Q: {ex.title}\nQuery: {ex.content.query if ex.content else ''}"
                )
            elif hasattr(ex, "question"):
                examples_text.append(f"Q: {ex.question}\nQuery: {getattr(ex, 'query', '')}")

        prompt = get_plan_analysis_prompt().format(
            question=question,
            schema_fields="\n".join(fields_text) if fields_text else "No relevant fields found",
            examples="\n".join(examples_text) if examples_text else "No examples available",
        )

        return prompt

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM analysis response into structured format."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find bare JSON object
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # Return default structure if parsing fails
        logger.warning("Failed to parse LLM analysis response, using defaults")
        return {
            "summary": "Analysis failed - using direct query generation",
            "ambiguities": [],
            "clarification_needs": [],
            "approach": "Direct query generation",
            "requires_multi_step": False,
            "suggested_steps": [
                {
                    "description": "Execute query",
                    "question": response[:500] if response else "Original question",
                }
            ],
        }

    def _build_disambiguation_questions(
        self,
        clarification_needs: List[Dict],
    ) -> List[DisambiguationQuestion]:
        """Convert identified clarification needs into user-facing questions."""
        questions = []

        for i, need in enumerate(clarification_needs):
            # Parse category
            category_str = need.get("category", "general").lower()
            try:
                category = DisambiguationCategory(category_str)
            except ValueError:
                category = DisambiguationCategory.GENERAL

            # Build options
            options = []
            for opt in need.get("options", []):
                options.append(
                    DisambiguationOption(
                        value=opt.get("value", f"option_{len(options)}"),
                        label=opt.get("label", opt.get("value", "")),
                        description=opt.get("description", ""),
                        is_default=opt.get("is_default", False),
                    )
                )

            q = DisambiguationQuestion(
                question_id=f"q_{i + 1}",
                question=need.get("question", ""),
                category=category,
                options=options,
                allows_custom=need.get("allows_custom", True),
                required=need.get("required", True),
            )
            questions.append(q)

        return questions

    def _build_initial_steps(
        self,
        question: str,
        analysis: Dict[str, Any],
    ) -> List[QueryPlanStep]:
        """Build initial plan steps from analysis."""
        suggested_steps = analysis.get("suggested_steps", [])

        if not suggested_steps:
            # Single-step plan
            return [
                QueryPlanStep(
                    step_id="step_1",
                    step_number=1,
                    description="Execute query",
                    user_question=question,
                )
            ]

        steps = []
        for i, step_info in enumerate(suggested_steps):
            step = QueryPlanStep(
                step_id=f"step_{i + 1}",
                step_number=i + 1,
                description=step_info.get("description", f"Step {i + 1}"),
                user_question=step_info.get("question", question),
                depends_on=step_info.get("depends_on", []),
                context_from_previous=step_info.get("context_from_previous", {}),
            )
            steps.append(step)

        return steps

    # =========================================================================
    # PHASE 2: Plan Update and Confirmation
    # =========================================================================

    async def update_plan(
        self,
        plan: QueryPlan,
        disambiguation_answers: Optional[Dict[str, str]] = None,
    ) -> QueryPlan:
        """
        Update plan based on user input.

        Args:
            plan: Plan to update
            disambiguation_answers: Map of question_id -> answer value

        Returns:
            Updated QueryPlan
        """
        # Apply disambiguation answers
        if disambiguation_answers:
            for q in plan.disambiguation_questions:
                if q.question_id in disambiguation_answers:
                    q.user_answer = disambiguation_answers[q.question_id]

            # Check if all required questions answered
            all_answered = all(
                q.is_answered() for q in plan.disambiguation_questions if q.required
            )
            if all_answered:
                plan.disambiguation_complete = True
                plan.status = PlanStatus.AWAITING_CONFIRMATION

        plan.updated_at = datetime.now()
        plan.current_version += 1

        # Save to storage if available
        if self.plan_storage:
            self.plan_storage.save_plan(
                plan,
                create_version=True,
                change_type="update",
                change_description="User answered disambiguation questions",
            )

        return plan

    async def confirm_plan(self, plan: QueryPlan) -> QueryPlan:
        """
        Confirm plan for execution.

        Args:
            plan: Plan to confirm

        Returns:
            Confirmed QueryPlan (status = CONFIRMED)
        """
        # Validate plan is ready
        unanswered = plan.get_unanswered_required_questions()
        if unanswered:
            raise ValueError(
                f"Unanswered required questions: {[q.question_id for q in unanswered]}"
            )

        if not plan.steps:
            raise ValueError("Plan has no steps")

        # Lock plan
        plan.status = PlanStatus.CONFIRMED
        plan.confirmed_at = datetime.now()
        plan.updated_at = datetime.now()
        plan.current_version += 1

        # Save to storage if available
        if self.plan_storage:
            self.plan_storage.save_plan(
                plan,
                create_version=True,
                change_type="confirmation",
                change_description="Plan confirmed for execution",
            )

        logger.info(f"Plan {plan.plan_id} confirmed with {len(plan.steps)} steps")

        return plan

    # =========================================================================
    # PHASE 3: Execution
    # =========================================================================

    async def execute_plan(
        self,
        plan: QueryPlan,
        query_type: QueryType = QueryType.POSTGRES,
        run_query_func: Optional[Callable] = None,
        stop_on_error: bool = True,
    ) -> QueryPlan:
        """
        Execute confirmed plan step by step.

        Args:
            plan: Plan to execute
            query_type: Target query type
            run_query_func: Function to execute queries
            stop_on_error: Stop execution if a step fails

        Returns:
            Executed QueryPlan with results
        """
        if plan.status != PlanStatus.CONFIRMED:
            raise ValueError(
                f"Plan must be confirmed before execution. Current: {plan.status}"
            )

        plan.status = PlanStatus.EXECUTING
        plan.execution_started_at = datetime.now()
        plan.current_step = 1

        logger.info(f"Starting execution of plan {plan.plan_id}")

        step_results: Dict[str, Any] = {}

        try:
            # Execute steps in order
            for step in sorted(plan.steps, key=lambda s: s.step_number):
                plan.current_step = step.step_number

                try:
                    await self._execute_step(
                        plan=plan,
                        step=step,
                        step_results=step_results,
                        query_type=query_type,
                        run_query_func=run_query_func,
                    )
                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.error_message = str(e)
                    step.completed_at = datetime.now()
                    logger.error(f"Step {step.step_id} failed: {e}")

                    if stop_on_error:
                        plan.status = PlanStatus.FAILED
                        break

            # Check final status
            all_completed = all(s.status == StepStatus.COMPLETED for s in plan.steps)
            if all_completed:
                plan.status = PlanStatus.COMPLETED
                plan.final_result = {
                    "steps_completed": len(plan.steps),
                    "step_results": {
                        s.step_id: s.execution_result for s in plan.steps if s.execution_result
                    },
                }

        finally:
            plan.execution_completed_at = datetime.now()
            plan.updated_at = datetime.now()
            plan.current_version += 1

            if self.plan_storage:
                self.plan_storage.save_plan(
                    plan,
                    create_version=True,
                    change_type="execution",
                    change_description=f"Execution {plan.status.value}",
                )

        logger.info(f"Plan {plan.plan_id} execution complete: {plan.status}")

        return plan

    async def _execute_step(
        self,
        plan: QueryPlan,
        step: QueryPlanStep,
        step_results: Dict[str, Any],
        query_type: QueryType,
        run_query_func: Optional[Callable],
    ) -> None:
        """Execute a single step."""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now()

        logger.info(f"Executing step {step.step_id}: {step.description}")

        # Build context from previous steps
        augmented_question = self._build_step_context(
            step=step,
            step_results=step_results,
            plan=plan,
        )

        # Generate query using pipeline
        result = await self.generation_pipeline.generate_query(
            tenant_id=plan.tenant_id,
            document_name=plan.document_name,
            user_question=augmented_question,
            query_type=query_type,
            run_query_func=run_query_func,
        )

        step.generated_query = result.query
        step_results[step.step_id] = result.query

        # Execute if function provided
        if run_query_func:
            try:
                df = run_query_func(result.query)
                step.execution_result = {
                    "row_count": len(df) if hasattr(df, "__len__") else 0,
                    "columns": list(df.columns) if hasattr(df, "columns") else [],
                    "preview": (
                        df.head(10).to_dict()
                        if hasattr(df, "head") and len(df) > 0
                        else {}
                    ),
                }
            except Exception as e:
                step.error_message = f"Execution error: {e}"
                raise
        else:
            step.execution_result = {
                "row_count": 0,
                "columns": [],
                "note": "Query generated but not executed",
            }

        step.status = StepStatus.COMPLETED
        step.completed_at = datetime.now()

    def _build_step_context(
        self,
        step: QueryPlanStep,
        step_results: Dict[str, Any],
        plan: QueryPlan,
    ) -> str:
        """Build augmented question with context from previous steps."""
        question = step.user_question

        # Inject previous step results via placeholders
        for placeholder, source_step_id in step.context_from_previous.items():
            result_value = step_results.get(source_step_id, "")
            if result_value:
                question = question.replace(f"{{{placeholder}}}", str(result_value))

        # Add disambiguation context if available
        if plan.disambiguation_questions:
            answer_context = []
            for q in plan.disambiguation_questions:
                if q.is_answered():
                    answer_label = q.user_answer
                    for opt in q.options:
                        if opt.value == q.user_answer:
                            answer_label = opt.label
                            break
                    answer_context.append(f"{q.category.value}: {answer_label}")

            if answer_context:
                question = f"{question}\n\nContext: {', '.join(answer_context)}"

        return question

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_plan(self, plan_id: str, tenant_id: str, document_name: str) -> Optional[QueryPlan]:
        """Get a plan by ID (requires plan_storage)."""
        if not self.plan_storage:
            raise ValueError("Plan storage not configured")
        return self.plan_storage.get_plan(tenant_id, document_name, plan_id)

    def cancel_plan(self, plan: QueryPlan) -> QueryPlan:
        """Cancel a plan."""
        plan.status = PlanStatus.CANCELLED
        plan.updated_at = datetime.now()
        plan.current_version += 1

        if self.plan_storage:
            self.plan_storage.save_plan(
                plan,
                create_version=True,
                change_type="cancellation",
                change_description="Plan cancelled by user",
            )

        return plan
