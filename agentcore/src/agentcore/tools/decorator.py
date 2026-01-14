"""Tool decorator for AgentCore.

The @tool decorator extracts parameter information from type hints
and docstrings to create ToolSpec instances automatically.
"""

from __future__ import annotations

import functools
import inspect
import re
from typing import Any, Callable, Optional, TypeVar, Union, get_type_hints, get_origin, get_args

from agentcore.tools.models import (
    HILConfig,
    ParameterType,
    RetentionStrategy,
    ToolParameter,
    ToolSpec,
)

F = TypeVar("F", bound=Callable[..., Any])


# Mapping of Python types to JSON Schema types
_TYPE_MAP: dict[type, ParameterType] = {
    str: ParameterType.STRING,
    int: ParameterType.INTEGER,
    float: ParameterType.NUMBER,
    bool: ParameterType.BOOLEAN,
    list: ParameterType.ARRAY,
    dict: ParameterType.OBJECT,
}


def _get_parameter_type(python_type: type) -> ParameterType:
    """Get the JSON Schema parameter type for a Python type.
    
    Args:
        python_type: Python type annotation
        
    Returns:
        Corresponding ParameterType
    """
    # Handle Optional types
    origin = get_origin(python_type)
    if origin is Union:
        args = get_args(python_type)
        # Optional[X] is Union[X, None]
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _get_parameter_type(non_none[0])
    
    # Handle list types
    if origin is list:
        return ParameterType.ARRAY
    
    # Handle dict types
    if origin is dict:
        return ParameterType.OBJECT
    
    # Direct mapping
    return _TYPE_MAP.get(python_type, ParameterType.STRING)


def _get_array_items_type(python_type: type) -> Optional[ParameterType]:
    """Get the items type for array parameters.
    
    Args:
        python_type: Python type annotation
        
    Returns:
        ParameterType for array items or None
    """
    origin = get_origin(python_type)
    
    # Handle Optional[list[X]]
    if origin is Union:
        args = get_args(python_type)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _get_array_items_type(non_none[0])
    
    if origin is list:
        args = get_args(python_type)
        if args:
            return _get_parameter_type(args[0])
    
    return None


def _parse_docstring(docstring: Optional[str]) -> tuple[str, dict[str, str]]:
    """Parse a docstring to extract description and parameter descriptions.
    
    Supports Google-style docstrings:
    
    ```
    Short description.
    
    Longer description if needed.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    ```
    
    Args:
        docstring: Function docstring
        
    Returns:
        Tuple of (description, {param_name: param_description})
    """
    if not docstring:
        return "", {}
    
    lines = docstring.strip().split("\n")
    
    description_lines = []
    param_descriptions: dict[str, str] = {}
    
    in_description = True
    in_args = False
    current_param: Optional[str] = None
    current_desc_lines: list[str] = []
    
    for line in lines:
        stripped = line.strip()
        
        if stripped.lower().startswith("args:"):
            in_description = False
            in_args = True
            continue
        
        if stripped.lower().startswith(("returns:", "raises:", "yields:", "examples:", "example:")):
            if current_param and current_desc_lines:
                param_descriptions[current_param] = " ".join(current_desc_lines).strip()
            in_description = False
            in_args = False
            current_param = None
            current_desc_lines = []
            continue
        
        if in_args:
            match = re.match(r"^\s*(\w+)\s*(?:\([^)]*\))?\s*:\s*(.*)$", line)
            if match:
                if current_param and current_desc_lines:
                    param_descriptions[current_param] = " ".join(current_desc_lines).strip()
                
                current_param = match.group(1)
                desc = match.group(2).strip()
                current_desc_lines = [desc] if desc else []
            elif current_param and stripped:
                current_desc_lines.append(stripped)
        elif in_description:
            description_lines.append(stripped)
    
    if current_param and current_desc_lines:
        param_descriptions[current_param] = " ".join(current_desc_lines).strip()
    
    description = " ".join(line for line in description_lines if line).strip()
    
    return description, param_descriptions


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    *,
    tags: Optional[list[str]] = None,
    requires_permissions: Optional[list[str]] = None,
    timeout: float = 30.0,
    retention: Optional[RetentionStrategy] = None,
    hil: Optional[HILConfig] = None,
    version: str = "1.0.0",
) -> Callable[[F], F]:
    """Decorator to mark a function as an agent tool.
    
    The decorator extracts parameter information from type hints and
    docstrings to create a ToolSpec automatically.
    
    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to docstring)
        tags: Tags for categorization
        requires_permissions: Required permissions
        timeout: Execution timeout in seconds
        retention: Context retention strategy
        hil: Human-in-the-loop configuration
        version: Tool version
        
    Returns:
        Decorated function with _tool_spec attribute
        
    Example:
        ```python
        @tool(tags=["purchasing"], requires_permissions=["POCreate"])
        async def create_purchase_order(
            vendor_id: str,
            items: list[dict],
            amount: float,
        ) -> dict:
            \"\"\"Create a new purchase order.
            
            Args:
                vendor_id: ID of the vendor
                items: Line items for the PO
                amount: Total amount
                
            Returns:
                Created purchase order
            \"\"\"
            ...
        ```
    """
    def decorator(func: F) -> F:
        # Get function signature and type hints
        sig = inspect.signature(func)
        try:
            hints = get_type_hints(func)
        except Exception:
            hints = {}
        
        # Parse docstring
        doc_description, param_descriptions = _parse_docstring(func.__doc__)
        
        # Determine tool name and description
        tool_name = name or func.__name__
        tool_description = description or doc_description or f"Execute {tool_name}"
        
        # Build parameters from signature
        parameters: list[ToolParameter] = []
        
        for param_name, param in sig.parameters.items():
            # Skip self, cls, ctx, and *args/**kwargs
            if param_name in ("self", "cls", "ctx", "context", "request_context"):
                continue
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue
            
            # Get type
            python_type = hints.get(param_name, str)
            param_type = _get_parameter_type(python_type)
            items_type = _get_array_items_type(python_type) if param_type == ParameterType.ARRAY else None
            
            # Determine if required
            has_default = param.default is not inspect.Parameter.empty
            is_optional = get_origin(python_type) is Union and type(None) in get_args(python_type)
            required = not has_default and not is_optional
            
            # Get description from docstring
            param_desc = param_descriptions.get(param_name, "")
            
            # Get default value
            default = param.default if has_default else None
            
            parameters.append(
                ToolParameter(
                    name=param_name,
                    type=param_type,
                    description=param_desc,
                    required=required,
                    default=default,
                    items_type=items_type,
                )
            )
        
        # Create tool spec
        tool_spec = ToolSpec(
            id=f"{tool_name}_{version}".replace(".", "_"),
            name=tool_name,
            description=tool_description,
            parameters=parameters,
            timeout=timeout,
            is_async=inspect.iscoroutinefunction(func),
            requires_permissions=requires_permissions or [],
            retention=retention,
            hil=hil,
            tags=tags or [],
            version=version,
        )
        
        # Attach spec to function
        func._tool_spec = tool_spec  # type: ignore[attr-defined]
        
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            async_wrapper._tool_spec = tool_spec  # type: ignore[attr-defined]
            return async_wrapper  # type: ignore[return-value]
        else:
            wrapper._tool_spec = tool_spec  # type: ignore[attr-defined]
            return wrapper  # type: ignore[return-value]
    
    return decorator


def get_tool_spec(func: Callable[..., Any]) -> Optional[ToolSpec]:
    """Get the ToolSpec from a decorated function.
    
    Args:
        func: A function potentially decorated with @tool
        
    Returns:
        ToolSpec if function is decorated, None otherwise
    """
    return getattr(func, "_tool_spec", None)


def is_tool(func: Callable[..., Any]) -> bool:
    """Check if a function is decorated as a tool.
    
    Args:
        func: Function to check
        
    Returns:
        True if function has @tool decorator
    """
    return hasattr(func, "_tool_spec")
