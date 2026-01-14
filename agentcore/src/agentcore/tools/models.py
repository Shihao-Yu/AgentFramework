"""Tool models for AgentCore."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ParameterType(str, Enum):
    """JSON Schema parameter types."""

    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class RetentionStrategy(BaseModel):
    """Strategy for retaining tool results in context.
    
    Controls how tool results are stored and compacted to manage
    context window usage.
    """

    model_config = ConfigDict(frozen=True)

    max_items: Optional[int] = Field(
        default=None,
        description="Maximum number of items to retain (for arrays)",
    )
    max_chars: Optional[int] = Field(
        default=None,
        description="Maximum characters to retain",
    )
    compact_fields: list[str] = Field(
        default_factory=list,
        description="Fields to include in compact representation",
    )
    summary_prompt: Optional[str] = Field(
        default=None,
        description="Prompt for LLM-based summarization if needed",
    )

    def should_compact(self, result: Any) -> bool:
        """Check if result should be compacted.
        
        Args:
            result: Tool result to check
            
        Returns:
            True if compaction is needed
        """
        if self.max_chars is not None:
            import json
            try:
                result_str = json.dumps(result)
                return len(result_str) > self.max_chars
            except (TypeError, ValueError):
                return len(str(result)) > self.max_chars
        
        if self.max_items is not None and isinstance(result, list):
            return len(result) > self.max_items
        
        return False

    def compact(self, result: Any) -> Any:
        """Compact a result according to this strategy.
        
        Args:
            result: Tool result to compact
            
        Returns:
            Compacted result
        """
        if isinstance(result, list) and self.max_items is not None:
            # Truncate list
            truncated = result[:self.max_items]
            if len(result) > self.max_items:
                return {
                    "items": truncated,
                    "total_count": len(result),
                    "truncated": True,
                }
            return truncated
        
        if isinstance(result, dict) and self.compact_fields:
            # Keep only specified fields
            return {k: v for k, v in result.items() if k in self.compact_fields}
        
        if self.max_chars is not None:
            import json
            try:
                result_str = json.dumps(result)
            except (TypeError, ValueError):
                result_str = str(result)
            
            if len(result_str) > self.max_chars:
                return {
                    "summary": result_str[:self.max_chars] + "...",
                    "truncated": True,
                    "original_length": len(result_str),
                }
        
        return result


class HILConfig(BaseModel):
    """Human-in-the-Loop configuration for a tool.
    
    Controls when and how human confirmation is requested
    before executing a tool.
    """

    model_config = ConfigDict(frozen=True)

    requires_confirmation: bool = Field(
        default=False,
        description="Whether this tool always requires confirmation",
    )
    confirmation_prompt: Optional[str] = Field(
        default=None,
        description="Custom prompt for confirmation dialog",
    )
    form_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for additional input form",
    )
    timeout: float = Field(
        default=300.0,
        description="Timeout in seconds for user response",
    )
    high_value_threshold: Optional[float] = Field(
        default=None,
        description="Amount threshold requiring confirmation (for value-based HIL)",
    )
    high_value_field: Optional[str] = Field(
        default="amount",
        description="Field name containing the value to check against threshold",
    )

    def requires_confirmation_for(self, arguments: dict[str, Any]) -> bool:
        """Check if confirmation is required for given arguments.
        
        Args:
            arguments: Tool call arguments
            
        Returns:
            True if confirmation is required
        """
        if self.requires_confirmation:
            return True
        
        # Check high-value threshold
        if self.high_value_threshold is not None and self.high_value_field:
            value = arguments.get(self.high_value_field)
            if value is not None:
                try:
                    if float(value) > self.high_value_threshold:
                        return True
                except (ValueError, TypeError):
                    pass
        
        return False


class ToolParameter(BaseModel):
    """A single parameter for a tool."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Parameter name")
    type: ParameterType = Field(description="Parameter type")
    description: str = Field(default="", description="Parameter description")
    required: bool = Field(default=True, description="Whether parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value")
    enum: Optional[list[Any]] = Field(default=None, description="Allowed values")
    items_type: Optional[ParameterType] = Field(
        default=None, 
        description="Type of array items (if type is array)",
    )

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema format.
        
        Returns:
            JSON Schema dict for this parameter
        """
        schema: dict[str, Any] = {"type": self.type.value}
        
        if self.description:
            schema["description"] = self.description
        
        if self.enum is not None:
            schema["enum"] = self.enum
        
        if self.default is not None:
            schema["default"] = self.default
        
        if self.type == ParameterType.ARRAY and self.items_type:
            schema["items"] = {"type": self.items_type.value}
        
        return schema


class ToolSpec(BaseModel):
    """Specification for a tool.
    
    Contains all metadata needed to:
    - Generate OpenAI function calling format
    - Execute the tool
    - Handle HIL and permissions
    - Manage context retention
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Unique tool identifier")
    name: str = Field(description="Tool name (function name)")
    description: str = Field(description="Tool description for LLM")
    parameters: list[ToolParameter] = Field(
        default_factory=list,
        description="Tool parameters",
    )
    
    # Execution
    timeout: float = Field(default=30.0, description="Execution timeout in seconds")
    is_async: bool = Field(default=True, description="Whether tool is async")
    
    # Permissions
    requires_permissions: list[str] = Field(
        default_factory=list,
        description="Permissions required to use this tool",
    )
    
    # Context management
    retention: Optional[RetentionStrategy] = Field(
        default=None,
        description="How to retain results in context",
    )
    
    # HIL
    hil: Optional[HILConfig] = Field(
        default=None,
        description="Human-in-the-loop configuration",
    )
    
    # Metadata
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for tool categorization",
    )
    version: str = Field(default="1.0.0", description="Tool version")

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format.
        
        Returns:
            Dict in OpenAI tools format
        """
        # Build JSON Schema for parameters
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)
        
        parameters_schema = {
            "type": "object",
            "properties": properties,
        }
        
        if required:
            parameters_schema["required"] = required
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters_schema,
            },
        }

    def get_parameter(self, name: str) -> Optional[ToolParameter]:
        """Get a parameter by name.
        
        Args:
            name: Parameter name
            
        Returns:
            ToolParameter or None
        """
        for param in self.parameters:
            if param.name == name:
                return param
        return None

    def requires_hil_for(self, arguments: dict[str, Any]) -> bool:
        """Check if HIL is required for given arguments.
        
        Args:
            arguments: Tool call arguments
            
        Returns:
            True if HIL confirmation is required
        """
        if self.hil is None:
            return False
        return self.hil.requires_confirmation_for(arguments)

    def compact_result(self, result: Any) -> Any:
        """Compact a tool result for context management.
        
        Args:
            result: Tool execution result
            
        Returns:
            Compacted result or original if no retention strategy
        """
        if self.retention is None:
            return result
        
        if self.retention.should_compact(result):
            return self.retention.compact(result)
        
        return result
