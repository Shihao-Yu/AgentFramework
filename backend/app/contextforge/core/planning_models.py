"""
Data models for Multi-Step Agentic Query Planning.

This module defines all dataclasses used for the planning pipeline:
- QueryPlan: Main container for a multi-step query plan
- QueryPlanStep: Individual step in a multi-step plan
- DisambiguationQuestion: Q&A for user clarification
- PlanVersion: Version history entry
- PlanExecutionState: Runtime state during execution
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    """Plan lifecycle status."""

    DRAFT = "draft"  # Initial creation, awaiting user input
    AWAITING_DISAMBIGUATION = "awaiting_disambiguation"  # Waiting for user answers
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # Plan ready for review
    CONFIRMED = "confirmed"  # Locked, ready for execution
    EXECUTING = "executing"  # Currently running
    COMPLETED = "completed"  # All steps finished
    FAILED = "failed"  # Execution failed
    CANCELLED = "cancelled"  # User cancelled


class StepStatus(str, Enum):
    """Individual step status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DisambiguationCategory(str, Enum):
    """Categories for disambiguation questions."""

    TIME = "time"  # Time period, date range
    SCOPE = "scope"  # Data scope, filtering
    FILTER = "filter"  # Specific filter conditions
    AGGREGATION = "aggregation"  # How to aggregate data
    METRIC = "metric"  # Which metric to use
    ENTITY = "entity"  # Which entity/table to query
    GENERAL = "general"  # Other


class DisambiguationOption(BaseModel):
    """An option for a disambiguation question."""

    value: str = Field(..., description="Machine-readable option value")
    label: str = Field(..., description="Human-readable display label")
    description: str = Field(
        default="", description="Explanation of what this option means"
    )
    is_default: bool = Field(default=False, description="Whether this is the suggested default")


class DisambiguationQuestion(BaseModel):
    """
    A disambiguation question presented to the user.

    Example:
        question: "What time period should we consider for 'recent orders'?"
        category: "time"
        options: [
            {"value": "7_days", "label": "Last 7 days", "description": "Most common usage"},
            {"value": "30_days", "label": "Last 30 days", "description": "Standard reporting"},
        ]
    """

    question_id: str = Field(
        default_factory=lambda: f"q_{uuid.uuid4().hex[:8]}",
        description="Unique question identifier",
    )
    question: str = Field(..., description="The question text")
    category: DisambiguationCategory = Field(
        default=DisambiguationCategory.GENERAL,
        description="Question category",
    )
    options: List[DisambiguationOption] = Field(
        default_factory=list,
        description="List of available options",
    )
    allows_custom: bool = Field(
        default=False, description="Allow custom user input beyond options"
    )
    user_answer: Optional[str] = Field(
        default=None, description="User's selected answer value"
    )
    user_custom_input: Optional[str] = Field(
        default=None, description="Custom input if allows_custom=True"
    )
    required: bool = Field(
        default=True, description="Must be answered before proceeding"
    )

    def is_answered(self) -> bool:
        """Check if this question has been answered."""
        return self.user_answer is not None or (
            self.allows_custom and self.user_custom_input is not None
        )

    def get_answer_value(self) -> Optional[str]:
        """Get the answer value (custom input takes priority)."""
        if self.user_custom_input:
            return self.user_custom_input
        return self.user_answer


class QueryPlanStep(BaseModel):
    """
    Individual step in a multi-step query plan.

    Steps can reference results from previous steps via placeholders:
    - context_from_previous maps placeholder names to source step IDs
    - user_question can contain {placeholder} that get replaced with previous results
    """

    step_id: str = Field(
        default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}",
        description="Unique step identifier",
    )
    step_number: int = Field(..., description="Execution order (1-based)")
    description: str = Field(..., description="Human-readable step description")

    # Query specification
    user_question: str = Field(
        ..., description="Natural language question for this step"
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="Step IDs this step depends on",
    )
    context_from_previous: Dict[str, str] = Field(
        default_factory=dict,
        description="Map placeholder names to source step IDs: {placeholder: step_id}",
    )

    # Execution state
    status: StepStatus = Field(default=StepStatus.PENDING)
    generated_query: Optional[str] = Field(
        default=None, description="Generated query (populated after execution)"
    )
    execution_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Query execution result: {row_count, columns, preview}",
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if step failed"
    )

    # Timing
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    def duration_ms(self) -> Optional[float]:
        """Calculate step execution duration in milliseconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None


class PlanVersion(BaseModel):
    """
    Version history entry for a query plan.

    Stores full plan state snapshot for easy rollback.
    """

    version_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique version identifier",
    )
    version_number: int = Field(..., description="Version number (1-based)")
    plan_id: str = Field(..., description="Parent plan ID")

    # Snapshot
    plan_snapshot: Dict[str, Any] = Field(
        ..., description="Full plan state at this version"
    )

    # Change tracking
    change_type: str = Field(
        ...,
        description="Type: creation, disambiguation_answer, step_modification, confirmation, rollback",
    )
    change_description: str = Field(
        default="", description="Human-readable change description"
    )
    changes_diff: Dict[str, Any] = Field(
        default_factory=dict,
        description="Diff from previous version (optional)",
    )

    # Metadata
    created_by: str = Field(
        default="user", description="Who made this change: user, system, llm"
    )
    created_at: datetime = Field(default_factory=datetime.now)


class QueryPlan(BaseModel):
    """
    Main container for a multi-step query plan.

    Lifecycle:
    1. DRAFT/AWAITING_DISAMBIGUATION: Plan created, waiting for user input
    2. AWAITING_CONFIRMATION: All questions answered, waiting for confirmation
    3. CONFIRMED: Locked for execution
    4. EXECUTING: Currently running
    5. COMPLETED/FAILED/CANCELLED: Terminal states
    """

    plan_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique plan identifier",
    )
    tenant_id: str = Field(..., description="Tenant identifier")
    document_name: str = Field(..., description="Document name")

    # Original request
    original_question: str = Field(
        ..., description="User's original natural language question"
    )

    # Status
    status: PlanStatus = Field(default=PlanStatus.DRAFT)
    current_version: int = Field(default=1)

    # Disambiguation
    disambiguation_questions: List[DisambiguationQuestion] = Field(
        default_factory=list,
        description="Questions for user clarification",
    )
    disambiguation_complete: bool = Field(default=False)

    # Plan steps
    steps: List[QueryPlanStep] = Field(default_factory=list)

    # Analysis results from LLM
    analysis_summary: str = Field(
        default="", description="LLM analysis of the question"
    )
    identified_ambiguities: List[str] = Field(
        default_factory=list,
        description="List of identified ambiguities",
    )
    suggested_approach: str = Field(
        default="", description="Recommended query strategy"
    )

    # Execution tracking
    current_step: Optional[int] = Field(
        default=None, description="Currently executing step number"
    )
    execution_started_at: Optional[datetime] = Field(default=None)
    execution_completed_at: Optional[datetime] = Field(default=None)

    # Results
    final_result: Optional[Dict[str, Any]] = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    confirmed_at: Optional[datetime] = Field(default=None)

    # Soft delete
    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(default=None)

    # Metadata for routing and additional context
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (e.g., routing info, custom data)",
    )

    def get_unanswered_required_questions(self) -> List[DisambiguationQuestion]:
        """Get list of required questions that haven't been answered."""
        return [
            q
            for q in self.disambiguation_questions
            if q.required and not q.is_answered()
        ]

    def is_ready_for_confirmation(self) -> bool:
        """Check if plan is ready to be confirmed."""
        return (
            len(self.get_unanswered_required_questions()) == 0
            and len(self.steps) > 0
            and self.status
            in [PlanStatus.AWAITING_DISAMBIGUATION, PlanStatus.AWAITING_CONFIRMATION]
        )

    def get_step_by_id(self, step_id: str) -> Optional[QueryPlanStep]:
        """Get a step by its ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_step_by_number(self, step_number: int) -> Optional[QueryPlanStep]:
        """Get a step by its number."""
        for step in self.steps:
            if step.step_number == step_number:
                return step
        return None

    def get_pending_steps(self) -> List[QueryPlanStep]:
        """Get steps that haven't been executed yet."""
        return [s for s in self.steps if s.status == StepStatus.PENDING]

    def get_completed_steps(self) -> List[QueryPlanStep]:
        """Get completed steps."""
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]

    def execution_duration_ms(self) -> Optional[float]:
        """Calculate total execution duration in milliseconds."""
        if self.execution_started_at and self.execution_completed_at:
            return (
                self.execution_completed_at - self.execution_started_at
            ).total_seconds() * 1000
        return None


class PlanExecutionState(BaseModel):
    """
    Runtime state during plan execution.

    Tracks intermediate results for step chaining.
    Not persisted - only used during execution.
    """

    plan_id: str = Field(..., description="Plan being executed")
    step_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Results by step_id for reference in subsequent steps",
    )
    step_queries: Dict[str, str] = Field(
        default_factory=dict,
        description="Generated queries by step_id",
    )
    context_accumulator: Dict[str, Any] = Field(
        default_factory=dict,
        description="Accumulated context from all steps",
    )
    execution_log: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Execution history for debugging",
    )

    def add_step_result(self, step_id: str, result: Any, query: str) -> None:
        """Record a step's result."""
        self.step_results[step_id] = result
        self.step_queries[step_id] = query
        self.execution_log.append(
            {
                "step_id": step_id,
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "status": "completed",
            }
        )

    def add_step_error(self, step_id: str, error: str) -> None:
        """Record a step's error."""
        self.execution_log.append(
            {
                "step_id": step_id,
                "timestamp": datetime.now().isoformat(),
                "error": error,
                "status": "failed",
            }
        )

    def get_result_for_placeholder(
        self, step_id: str, column_name: Optional[str] = None
    ) -> Optional[Any]:
        """
        Get result from a previous step for use as placeholder value.

        Args:
            step_id: Source step ID
            column_name: Optional column to extract (defaults to first column)

        Returns:
            Formatted value for injection into query
        """
        result = self.step_results.get(step_id)
        if result is None:
            return None

        # If result is a DataFrame-like object with values
        if hasattr(result, "iloc") and hasattr(result, "columns"):
            if column_name and column_name in result.columns:
                values = result[column_name].tolist()
            else:
                # Default to first column
                values = result.iloc[:, 0].tolist()

            # Limit to prevent query explosion
            values = values[:100]
            return ", ".join(str(v) for v in values)

        # If result is already a list
        if isinstance(result, list):
            return ", ".join(str(v) for v in result[:100])

        return str(result)


# Dataclass versions for compatibility with existing codebase patterns


@dataclass
class QueryPlanSummary:
    """Lightweight summary of a query plan for listing."""

    plan_id: str
    tenant_id: str
    document_name: str
    original_question: str
    status: PlanStatus
    step_count: int
    unanswered_questions: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_plan(cls, plan: QueryPlan) -> "QueryPlanSummary":
        """Create summary from full plan."""
        return cls(
            plan_id=plan.plan_id,
            tenant_id=plan.tenant_id,
            document_name=plan.document_name,
            original_question=plan.original_question,
            status=plan.status,
            step_count=len(plan.steps),
            unanswered_questions=len(plan.get_unanswered_required_questions()),
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )


@dataclass
class PlanExecutionResult:
    """Result from plan execution."""

    plan_id: str
    status: PlanStatus
    steps_completed: int
    total_steps: int
    execution_duration_ms: Optional[float]
    step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @classmethod
    def from_plan(cls, plan: QueryPlan) -> "PlanExecutionResult":
        """Create result from executed plan."""
        return cls(
            plan_id=plan.plan_id,
            status=plan.status,
            steps_completed=len(plan.get_completed_steps()),
            total_steps=len(plan.steps),
            execution_duration_ms=plan.execution_duration_ms(),
            step_results={
                s.step_id: s.execution_result
                for s in plan.steps
                if s.execution_result
            },
            errors=[s.error_message for s in plan.steps if s.error_message],
        )
