import pytest

from agentcore.prompts import PromptRegistry, get_prompt_registry
from agentcore.prompts.fallbacks import FALLBACK_PROMPTS
from agentcore.prompts.registry import _compile_template


class TestCompileTemplate:
    def test_simple_variable(self):
        template = "Hello {{name}}!"
        result = _compile_template(template, name="World")
        assert result == "Hello World!"

    def test_multiple_variables(self):
        template = "{{greeting}} {{name}}, welcome to {{place}}!"
        result = _compile_template(template, greeting="Hello", name="Alice", place="Wonderland")
        assert result == "Hello Alice, welcome to Wonderland!"

    def test_missing_variable_empty_string(self):
        template = "Hello {{name}}!"
        result = _compile_template(template, other="value")
        assert result == "Hello !"

    def test_conditional_block_truthy(self):
        template = "Start{{#show}} VISIBLE{{/show}} End"
        result = _compile_template(template, show=True)
        assert result == "Start VISIBLE End"

    def test_conditional_block_falsy(self):
        template = "Start{{#show}} VISIBLE{{/show}} End"
        result = _compile_template(template, show=False)
        assert result == "Start End"

    def test_conditional_block_with_string(self):
        template = "{{#context}}Context: {{context}}{{/context}}"
        result = _compile_template(template, context="Some context here")
        assert result == "Context: Some context here"

    def test_conditional_block_empty_string(self):
        template = "{{#context}}Context: {{context}}{{/context}}"
        result = _compile_template(template, context="")
        assert result == ""

    def test_inverted_block_falsy(self):
        template = "{{^found}}Not found{{/found}}"
        result = _compile_template(template, found=False)
        assert result == "Not found"

    def test_inverted_block_truthy(self):
        template = "{{^found}}Not found{{/found}}"
        result = _compile_template(template, found=True)
        assert result == ""

    def test_multiline_conditional(self):
        template = """Header
{{#details}}
Details:
{{details}}
{{/details}}
Footer"""
        result = _compile_template(template, details="Some details")
        assert "Details:" in result
        assert "Some details" in result
        assert "Header" in result
        assert "Footer" in result

    def test_nested_variables_in_conditional(self):
        template = "{{#show}}Hello {{name}}!{{/show}}"
        result = _compile_template(template, show=True, name="World")
        assert result == "Hello World!"


class TestPromptRegistry:
    def test_get_fallback_prompt(self):
        registry = PromptRegistry()
        result = registry.get("orchestrator-router", agent_descriptions="- agent1: Does stuff")
        assert "agent1: Does stuff" in result
        assert "query router" in result.lower()

    def test_get_planner_prompt(self):
        registry = PromptRegistry()
        result = registry.get(
            "agent-planner",
            query="Find PO 12345",
            knowledge_context="PO-12345 is a purchase order",
            blackboard_context="",
            replan_reason="",
        )
        assert "Find PO 12345" in result
        assert "PO-12345 is a purchase order" in result

    def test_get_planner_prompt_with_replan(self):
        registry = PromptRegistry()
        result = registry.get(
            "agent-planner",
            query="Find PO 12345",
            knowledge_context="",
            blackboard_context="",
            replan_reason="Tool execution failed",
        )
        assert "Tool execution failed" in result
        assert "revision" in result.lower() or "updated" in result.lower()

    def test_get_unknown_prompt_raises(self):
        registry = PromptRegistry()
        with pytest.raises(ValueError, match="not found"):
            registry.get("unknown-prompt")

    def test_get_template(self):
        registry = PromptRegistry()
        template = registry.get_template("orchestrator-router")
        assert "{{agent_descriptions}}" in template

    def test_singleton(self):
        r1 = get_prompt_registry()
        r2 = get_prompt_registry()
        assert r1 is r2


class TestFallbackPrompts:
    def test_all_fallbacks_exist(self):
        assert "orchestrator-router" in FALLBACK_PROMPTS
        assert "agent-planner" in FALLBACK_PROMPTS
        assert "agent-researcher" in FALLBACK_PROMPTS
        assert "agent-analyzer" in FALLBACK_PROMPTS
        assert "agent-synthesizer" in FALLBACK_PROMPTS

    def test_orchestrator_router_has_variable(self):
        assert "{{agent_descriptions}}" in FALLBACK_PROMPTS["orchestrator-router"]

    def test_agent_planner_has_variables(self):
        planner = FALLBACK_PROMPTS["agent-planner"]
        assert "{{query}}" in planner
        assert "{{knowledge_context}}" in planner
        assert "{{blackboard_context}}" in planner
        assert "{{replan_reason}}" in planner

    def test_agent_researcher_has_variables(self):
        researcher = FALLBACK_PROMPTS["agent-researcher"]
        assert "{{instruction}}" in researcher
        assert "{{query}}" in researcher
        assert "{{knowledge_context}}" in researcher
        assert "{{blackboard_context}}" in researcher

    def test_agent_analyzer_has_variables(self):
        analyzer = FALLBACK_PROMPTS["agent-analyzer"]
        assert "{{instruction}}" in analyzer
        assert "{{query}}" in analyzer
        assert "{{schema_context}}" in analyzer
        assert "{{blackboard_context}}" in analyzer
        assert "{{findings}}" in analyzer

    def test_agent_synthesizer_has_variables(self):
        synthesizer = FALLBACK_PROMPTS["agent-synthesizer"]
        assert "{{instruction}}" in synthesizer
        assert "{{query}}" in synthesizer
        assert "{{findings}}" in synthesizer
        assert "{{tool_results}}" in synthesizer
        assert "{{blackboard_context}}" in synthesizer


class TestSubAgentPrompts:

    def test_researcher_prompt_compilation(self):
        registry = PromptRegistry()
        result = registry.get(
            "agent-researcher",
            instruction="Find information about purchase orders",
            query="What is PO 12345?",
            knowledge_context="PO knowledge here",
            blackboard_context="Current state",
        )
        assert "Find information about purchase orders" in result
        assert "What is PO 12345?" in result
        assert "PO knowledge here" in result
        assert "Current state" in result

    def test_researcher_prompt_without_knowledge_hides_section(self):
        registry = PromptRegistry()
        result = registry.get(
            "agent-researcher",
            instruction="Research task",
            query="Some query",
            knowledge_context="",
            blackboard_context="",
        )
        assert "Research task" in result
        assert "Some query" in result
        assert "Relevant Knowledge:" not in result

    def test_analyzer_prompt_compilation(self):
        registry = PromptRegistry()
        result = registry.get(
            "agent-analyzer",
            instruction="Analyze the data",
            query="Compare PO with invoice",
            schema_context="PurchaseOrder schema",
            blackboard_context="Context here",
            findings="- [researcher] Found PO details",
        )
        assert "Analyze the data" in result
        assert "Compare PO with invoice" in result
        assert "PurchaseOrder schema" in result
        assert "Found PO details" in result

    def test_analyzer_prompt_contains_replan_marker(self):
        registry = PromptRegistry()
        result = registry.get(
            "agent-analyzer",
            instruction="Analyze",
            query="Query",
            schema_context="",
            blackboard_context="",
            findings="",
        )
        assert "REPLAN_NEEDED" in result

    def test_synthesizer_prompt_compilation(self):
        registry = PromptRegistry()
        result = registry.get(
            "agent-synthesizer",
            instruction="Generate response",
            query="What is the status of PO 12345?",
            findings="- [researcher] PO found\n- [analyzer] Analysis complete",
            tool_results="- search_po: {id: 12345, status: approved}",
            blackboard_context="Additional context",
        )
        assert "Generate response" in result
        assert "What is the status of PO 12345?" in result
        assert "PO found" in result
        assert "Analysis complete" in result
        assert "search_po" in result

    def test_synthesizer_prompt_without_tool_results_hides_section(self):
        registry = PromptRegistry()
        result = registry.get(
            "agent-synthesizer",
            instruction="Generate response",
            query="Simple query",
            findings="Some findings",
            tool_results="",
            blackboard_context="",
        )
        assert "Generate response" in result
        assert "Tool Results:" not in result
