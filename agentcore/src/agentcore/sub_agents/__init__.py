"""Sub-agents for specialized task execution.

Sub-agents are specialized components that handle specific types of tasks
within the BaseAgent's ReAct loop:

- PlannerSubAgent: Decomposes user requests into execution plans
- ResearcherSubAgent: Gathers information from knowledge base and tools
- AnalyzerSubAgent: Analyzes data and makes comparisons
- ExecutorSubAgent: Executes actions that modify state (with HIL support)
- SynthesizerSubAgent: Generates final user-facing responses
"""

from agentcore.sub_agents.base import SubAgentBase, SubAgentConfig
from agentcore.sub_agents.planner import PlannerSubAgent
from agentcore.sub_agents.researcher import ResearcherSubAgent
from agentcore.sub_agents.analyzer import AnalyzerSubAgent
from agentcore.sub_agents.executor import ExecutorSubAgent
from agentcore.sub_agents.synthesizer import SynthesizerSubAgent

__all__ = [
    # Base
    "SubAgentBase",
    "SubAgentConfig",
    # Implementations
    "PlannerSubAgent",
    "ResearcherSubAgent",
    "AnalyzerSubAgent",
    "ExecutorSubAgent",
    "SynthesizerSubAgent",
]
