"""Tool registry for AgentCore."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

from agentcore.tools.decorator import get_tool_spec, is_tool
from agentcore.tools.models import ToolSpec

if TYPE_CHECKING:
    from agentcore.auth.context import RequestContext
    from agentcore.auth.models import Permission

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for agent tools.
    
    The ToolRegistry:
    - Stores tool specifications and callable implementations
    - Provides discovery by name, tags, or permissions
    - Generates OpenAI-format tool lists for LLM calls
    - Validates tool calls against permissions
    
    Example:
        ```python
        registry = ToolRegistry()
        
        # Register decorated functions
        registry.register(create_purchase_order)
        registry.register(search_vendors)
        
        # Or register manually
        registry.register_spec(spec, callable_fn)
        
        # Get tools for LLM
        tools = registry.get_openai_tools(tags=["purchasing"])
        
        # Execute a tool
        result = await registry.execute("create_purchase_order", {"vendor_id": "V123"}, ctx)
        ```
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._tools: dict[str, ToolSpec] = {}
        self._functions: dict[str, Callable[..., Any]] = {}

    def register(self, func: Callable[..., Any]) -> None:
        """Register a @tool-decorated function.
        
        Args:
            func: Function decorated with @tool
            
        Raises:
            ValueError: If function is not decorated with @tool
        """
        spec = get_tool_spec(func)
        if spec is None:
            raise ValueError(
                f"Function {func.__name__} is not decorated with @tool. "
                "Use register_spec() for manual registration."
            )
        
        self._tools[spec.name] = spec
        self._functions[spec.name] = func
        logger.debug(f"Registered tool: {spec.name}")

    def register_spec(
        self,
        spec: ToolSpec,
        func: Callable[..., Any],
    ) -> None:
        """Register a tool with explicit spec.
        
        Args:
            spec: Tool specification
            func: Callable implementation
        """
        self._tools[spec.name] = spec
        self._functions[spec.name] = func
        logger.debug(f"Registered tool spec: {spec.name}")

    def register_all(self, obj: Any) -> int:
        """Register all @tool-decorated methods from an object.
        
        Args:
            obj: Object (instance or class) with @tool methods
            
        Returns:
            Number of tools registered
        """
        count = 0
        for name in dir(obj):
            if name.startswith("_"):
                continue
            
            attr = getattr(obj, name, None)
            if callable(attr) and is_tool(attr):
                self.register(attr)
                count += 1
        
        return count

    def unregister(self, name: str) -> bool:
        """Unregister a tool.
        
        Args:
            name: Tool name
            
        Returns:
            True if tool was removed, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            del self._functions[name]
            logger.debug(f"Unregistered tool: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[ToolSpec]:
        """Get a tool spec by name.
        
        Args:
            name: Tool name
            
        Returns:
            ToolSpec or None
        """
        return self._tools.get(name)

    def get_function(self, name: str) -> Optional[Callable[..., Any]]:
        """Get a tool's callable implementation.
        
        Args:
            name: Tool name
            
        Returns:
            Callable or None
        """
        return self._functions.get(name)

    def list_tools(
        self,
        tags: Optional[list[str]] = None,
        permissions: Optional[list[str]] = None,
    ) -> list[ToolSpec]:
        """List tools, optionally filtered.
        
        Args:
            tags: Filter by tags (any match)
            permissions: Filter to tools requiring these permissions
            
        Returns:
            List of matching ToolSpecs
        """
        tools = list(self._tools.values())
        
        if tags:
            tools = [t for t in tools if any(tag in t.tags for tag in tags)]
        
        if permissions:
            tools = [
                t for t in tools
                if any(p in t.requires_permissions for p in permissions)
            ]
        
        return tools

    def get_tools_for_context(
        self,
        ctx: Optional["RequestContext"] = None,
        tags: Optional[list[str]] = None,
    ) -> list[ToolSpec]:
        """Get tools available for a given context.
        
        Filters based on user permissions in the context.
        
        Args:
            ctx: Request context with user permissions
            tags: Additional tag filter
            
        Returns:
            List of available ToolSpecs
        """
        tools = list(self._tools.values())
        
        if tags:
            tools = [t for t in tools if any(tag in t.tags for tag in tags)]
        
        # Filter by permissions if context provided
        if ctx is not None:
            user_permissions = set(str(p.value) for p in ctx.user.permissions)
            tools = [
                t for t in tools
                if not t.requires_permissions or 
                any(p in user_permissions for p in t.requires_permissions)
            ]
        
        return tools

    def get_openai_tools(
        self,
        ctx: Optional["RequestContext"] = None,
        tags: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Get tools in OpenAI function calling format.
        
        Args:
            ctx: Request context for permission filtering
            tags: Tag filter
            
        Returns:
            List of tool definitions in OpenAI format
        """
        tools = self.get_tools_for_context(ctx=ctx, tags=tags)
        return [t.to_openai_format() for t in tools]

    def validate_permission(
        self,
        tool_name: str,
        ctx: "RequestContext",
    ) -> tuple[bool, Optional[str]]:
        """Validate that user has permission to use a tool.
        
        Args:
            tool_name: Name of the tool
            ctx: Request context with user
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        spec = self.get(tool_name)
        if spec is None:
            return False, f"Tool '{tool_name}' not found"
        
        if not spec.requires_permissions:
            return True, None
        
        user_permissions = set(str(p.value) for p in ctx.user.permissions)
        
        if not any(p in user_permissions for p in spec.requires_permissions):
            return False, (
                f"Permission denied for tool '{tool_name}'. "
                f"Required: {spec.requires_permissions}"
            )
        
        return True, None

    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())

    @property
    def tool_count(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def __len__(self) -> int:
        """Get number of tools."""
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={self.tool_names})"
