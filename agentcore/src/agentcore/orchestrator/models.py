"""Orchestrator models."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RoutingStrategy(str, Enum):
    """Routing strategy for multi-agent queries."""

    SINGLE = "single"  # One agent handles entirely
    PARALLEL = "parallel"  # Multiple agents, independent work
    SEQUENTIAL = "sequential"  # Multiple agents, dependent


class RoutingDecision(BaseModel):
    """Decision on how to route a query to agents."""

    strategy: RoutingStrategy
    agents: list[str] = Field(..., description="Ordered list of agent IDs")
    reasoning: str = Field(default="", description="LLM's reasoning for tracing")

    # For SEQUENTIAL strategy
    dependencies: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Agent dependencies, e.g. {'agent_b': ['agent_a']}",
    )


class AgentInvocationResult(BaseModel):
    """Result from invoking a single agent."""

    agent_id: str
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
