"""Tools module for AgentCore.

This module provides:
- @tool decorator for defining agent tools
- ToolSpec model for tool definitions
- ToolRegistry for tool registration and discovery
- ToolExecutor for executing tools with tracing
"""

from agentcore.tools.models import (
    RetentionStrategy,
    HILConfig,
    ToolSpec,
    ToolParameter,
)
from agentcore.tools.decorator import tool
from agentcore.tools.registry import ToolRegistry
from agentcore.tools.executor import ToolExecutor

__all__ = [
    # Models
    "RetentionStrategy",
    "HILConfig",
    "ToolSpec",
    "ToolParameter",
    # Decorator
    "tool",
    # Registry
    "ToolRegistry",
    # Executor
    "ToolExecutor",
]
