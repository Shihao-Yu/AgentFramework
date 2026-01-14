"""Blackboard for shared state between agent and sub-agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from agentcore.core.models import ExecutionPlan, ToolResult
from agentcore.auth.context import RequestContext


class VariableEntry(BaseModel):
    """A single variable stored on the blackboard."""

    model_config = ConfigDict(frozen=True)

    key: str
    value: Any
    source: str = Field(description="Which component set this (planner, researcher, etc.)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Finding(BaseModel):
    """A finding/insight recorded during execution."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(description="Which sub-agent found this")
    content: str = Field(description="The finding content")
    evidence: Optional[str] = Field(default=None, description="Supporting evidence")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Blackboard(BaseModel):
    """Shared state between agent and sub-agents.
    
    The blackboard is the central communication hub in the hub-and-spoke
    architecture. Sub-agents read from and write to the blackboard rather
    than communicating directly with each other.
    
    Contents:
    - Request context (user, session, etc.)
    - Current execution plan
    - Variables (key-value store with history)
    - Tool results (with dual-form for context management)
    - Findings (insights gathered during execution)
    - Pending interactions (HIL prompts)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Request context
    ctx: RequestContext = Field(description="Request context")
    
    # Original query
    query: str = Field(description="Original user query")
    
    # Execution plan
    plan: Optional[ExecutionPlan] = Field(default=None)
    
    # Variable storage (private attributes)
    _variables: dict[str, VariableEntry] = PrivateAttr(default_factory=dict)
    _variable_history: list[VariableEntry] = PrivateAttr(default_factory=list)
    
    # Tool results
    tool_results: list[ToolResult] = Field(default_factory=list)
    
    # Findings
    findings: list[Finding] = Field(default_factory=list)
    
    # Human-in-the-loop
    pending_interactions: list[dict[str, Any]] = Field(default_factory=list)
    
    # Conversation history for context
    message_history: list[dict[str, str]] = Field(default_factory=list)

    @classmethod
    def create(cls, ctx: RequestContext, query: str) -> "Blackboard":
        """Create a new blackboard for a request."""
        return cls(ctx=ctx, query=query)

    # Variable operations
    def set(self, key: str, value: Any, source: str = "agent") -> None:
        """Set a variable on the blackboard.
        
        Args:
            key: Variable name
            value: Variable value
            source: Component that set this value
        """
        entry = VariableEntry(key=key, value=value, source=source)
        self._variables[key] = entry
        self._variable_history.append(entry)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a variable from the blackboard.
        
        Args:
            key: Variable name
            default: Default if not found
            
        Returns:
            Variable value or default
        """
        entry = self._variables.get(key)
        return entry.value if entry else default

    def has(self, key: str) -> bool:
        """Check if a variable exists."""
        return key in self._variables

    def get_all_variables(self) -> dict[str, Any]:
        """Get all current variables as a dict."""
        return {k: v.value for k, v in self._variables.items()}

    def get_variable_history(self, key: Optional[str] = None) -> list[VariableEntry]:
        """Get variable history, optionally filtered by key."""
        if key is None:
            return list(self._variable_history)
        return [e for e in self._variable_history if e.key == key]

    # Tool result operations
    def add_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: Any,
        compact_result: Optional[Any] = None,
        duration_ms: float = 0.0,
    ) -> None:
        """Add a tool execution result.
        
        Args:
            tool_call_id: ID of the tool call
            tool_name: Name of the tool
            result: Full result
            compact_result: Optional compacted result for context
            duration_ms: Execution duration
        """
        self.tool_results.append(
            ToolResult.success_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                result=result,
                compact_result=compact_result,
                duration_ms=duration_ms,
            )
        )

    def add_tool_error(
        self,
        tool_call_id: str,
        tool_name: str,
        error: str,
        duration_ms: float = 0.0,
    ) -> None:
        """Add a tool execution error."""
        self.tool_results.append(
            ToolResult.failure_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error=error,
                duration_ms=duration_ms,
            )
        )

    def get_tool_result(self, tool_call_id: str) -> Optional[ToolResult]:
        """Get a specific tool result by call ID."""
        for result in self.tool_results:
            if result.tool_call_id == tool_call_id:
                return result
        return None

    # Finding operations
    def add_finding(
        self,
        source: str,
        content: str,
        evidence: Optional[str] = None,
        confidence: float = 1.0,
    ) -> None:
        """Add a finding/insight.
        
        Args:
            source: Which component found this
            content: The finding content
            evidence: Optional supporting evidence
            confidence: Confidence level (0-1)
        """
        self.findings.append(
            Finding(
                source=source,
                content=content,
                evidence=evidence,
                confidence=confidence,
            )
        )

    def get_findings_by_source(self, source: str) -> list[Finding]:
        """Get findings from a specific source."""
        return [f for f in self.findings if f.source == source]

    # HIL operations
    def add_pending_interaction(
        self,
        interaction_type: str,
        prompt: str,
        options: Optional[list[str]] = None,
        form_schema: Optional[dict[str, Any]] = None,
        timeout: float = 300.0,
    ) -> str:
        """Add a pending human interaction.
        
        Args:
            interaction_type: Type of interaction (confirm, input, form)
            prompt: Prompt to show user
            options: Options for selection
            form_schema: Schema for form input
            timeout: Timeout in seconds
            
        Returns:
            Interaction ID
        """
        from uuid import uuid4
        interaction_id = str(uuid4())
        
        self.pending_interactions.append({
            "id": interaction_id,
            "type": interaction_type,
            "prompt": prompt,
            "options": options,
            "form_schema": form_schema,
            "timeout": timeout,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        
        return interaction_id

    def resolve_interaction(self, interaction_id: str, response: Any) -> bool:
        """Resolve a pending interaction with user response.
        
        Args:
            interaction_id: ID of the interaction
            response: User's response
            
        Returns:
            True if interaction was found and resolved
        """
        for i, interaction in enumerate(self.pending_interactions):
            if interaction["id"] == interaction_id:
                interaction["response"] = response
                interaction["resolved_at"] = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def has_pending_interactions(self) -> bool:
        """Check if there are unresolved interactions."""
        return any(
            "response" not in i
            for i in self.pending_interactions
        )

    # Message history
    def add_message(self, role: str, content: str) -> None:
        """Add a message to history."""
        self.message_history.append({"role": role, "content": content})

    # Context generation for LLM
    def get_context_for_llm(self, max_tokens: int = 8000) -> str:
        """Generate context summary for LLM prompts.
        
        Args:
            max_tokens: Approximate max tokens (uses char estimate)
            
        Returns:
            Formatted context string
        """
        max_chars = max_tokens * 4  # Rough estimate
        parts = []
        total_chars = 0

        # Add variables
        if self._variables:
            var_section = ["## Current Variables"]
            for key, entry in self._variables.items():
                var_str = f"- {key}: {entry.value}"
                if len(var_str) > 200:
                    var_str = var_str[:200] + "..."
                var_section.append(var_str)
            parts.append("\n".join(var_section))
            total_chars += sum(len(s) for s in var_section)

        # Add findings
        if self.findings:
            findings_section = ["## Findings"]
            for finding in self.findings[-10:]:  # Last 10
                finding_str = f"- [{finding.source}] {finding.content}"
                if len(finding_str) > 300:
                    finding_str = finding_str[:300] + "..."
                findings_section.append(finding_str)
            parts.append("\n".join(findings_section))
            total_chars += sum(len(s) for s in findings_section)

        # Add recent tool results (compact form)
        if self.tool_results:
            results_section = ["## Recent Tool Results"]
            for result in self.tool_results[-5:]:  # Last 5
                result_data = result.get_result_for_context()
                result_str = f"- {result.tool_name}: "
                if result.success:
                    data_str = str(result_data)
                    if len(data_str) > 500:
                        data_str = data_str[:500] + "..."
                    result_str += data_str
                else:
                    result_str += f"ERROR: {result.error}"
                results_section.append(result_str)
            parts.append("\n".join(results_section))

        # Check total length
        context = "\n\n".join(parts)
        if len(context) > max_chars:
            context = context[:max_chars] + "\n\n[Context truncated]"

        return context

    def to_summary(self) -> dict[str, Any]:
        """Get blackboard summary for logging."""
        return {
            "query": self.query,
            "has_plan": self.plan is not None,
            "plan_progress": self.plan.progress_percent if self.plan else 0,
            "variables_count": len(self._variables),
            "tool_results_count": len(self.tool_results),
            "findings_count": len(self.findings),
            "pending_interactions": len([i for i in self.pending_interactions if "response" not in i]),
        }
