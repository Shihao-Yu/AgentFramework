"""Unit tests for core agent module."""

import pytest
from datetime import datetime, timezone

from agentcore.core.models import (
    AgentState,
    ExecutionPlan,
    PlanStep,
    StepStatus,
    SubAgentResult,
    ToolResult,
)
from agentcore.core.blackboard import Blackboard, Finding, VariableEntry
from agentcore.auth.models import EnrichedUser, Permission
from agentcore.auth.context import RequestContext


# Fixtures
@pytest.fixture
def user():
    return EnrichedUser(
        user_id=1,
        username="testuser",
        email="test@example.com",
        display_name="Test User",
        department="Engineering",
        title="Engineer",
        entity_id=1,
        entity_name="Test Entity",
        permissions=frozenset([Permission.BUYER]),
        token="test-token",
    )


@pytest.fixture
def request_ctx(user):
    return RequestContext.create(
        user=user,
        session_id="test-session",
        request_id="test-request",
    )


class TestPlanStep:
    """Tests for PlanStep model."""

    def test_create(self):
        step = PlanStep(
            id="step_1",
            description="Research the query",
            sub_agent="researcher",
            instruction="Find information about X",
        )
        
        assert step.id == "step_1"
        assert step.status == StepStatus.PENDING
        assert step.result is None
        assert step.error is None

    def test_start(self):
        step = PlanStep(
            id="step_1",
            description="Test",
            sub_agent="researcher",
            instruction="Test",
        )
        
        step.start()
        
        assert step.status == StepStatus.IN_PROGRESS
        assert step.started_at is not None

    def test_complete(self):
        step = PlanStep(
            id="step_1",
            description="Test",
            sub_agent="researcher",
            instruction="Test",
        )
        
        step.start()
        step.complete(result={"data": "test"})
        
        assert step.status == StepStatus.COMPLETED
        assert step.result == {"data": "test"}
        assert step.completed_at is not None

    def test_fail(self):
        step = PlanStep(
            id="step_1",
            description="Test",
            sub_agent="researcher",
            instruction="Test",
        )
        
        step.start()
        step.fail("Something went wrong")
        
        assert step.status == StepStatus.FAILED
        assert step.error == "Something went wrong"

    def test_skip(self):
        step = PlanStep(
            id="step_1",
            description="Test",
            sub_agent="researcher",
            instruction="Test",
        )
        
        step.skip("Not needed")
        
        assert step.status == StepStatus.SKIPPED
        assert step.error == "Not needed"

    def test_duration_ms(self):
        step = PlanStep(
            id="step_1",
            description="Test",
            sub_agent="researcher",
            instruction="Test",
        )
        
        assert step.duration_ms is None
        
        step.start()
        step.complete()
        
        assert step.duration_ms is not None
        assert step.duration_ms >= 0


class TestExecutionPlan:
    """Tests for ExecutionPlan model."""

    def test_create(self):
        plan = ExecutionPlan(
            query="Test query",
            goal="Answer the query",
            steps=[
                PlanStep(id="s1", description="Step 1", sub_agent="researcher", instruction="Do X"),
                PlanStep(id="s2", description="Step 2", sub_agent="synthesizer", instruction="Do Y", depends_on=["s1"]),
            ],
        )
        
        assert plan.query == "Test query"
        assert len(plan.steps) == 2
        assert plan.version == 1
        assert not plan.is_complete

    def test_current_step(self):
        plan = ExecutionPlan(
            query="Test",
            goal="Test",
            steps=[
                PlanStep(id="s1", description="Step 1", sub_agent="researcher", instruction="X"),
                PlanStep(id="s2", description="Step 2", sub_agent="synthesizer", instruction="Y", depends_on=["s1"]),
            ],
        )
        
        # First step should be current
        assert plan.current_step.id == "s1"
        
        # Complete first step
        plan.steps[0].complete()
        
        # Second step should now be current
        assert plan.current_step.id == "s2"

    def test_current_step_with_dependencies(self):
        plan = ExecutionPlan(
            query="Test",
            goal="Test",
            steps=[
                PlanStep(id="s1", description="Step 1", sub_agent="researcher", instruction="X"),
                PlanStep(id="s2", description="Step 2", sub_agent="analyzer", instruction="Y", depends_on=["s1"]),
            ],
        )
        
        # s2 depends on s1, so s1 should be current even though s2 is pending
        assert plan.current_step.id == "s1"

    def test_progress_percent(self):
        plan = ExecutionPlan(
            query="Test",
            goal="Test",
            steps=[
                PlanStep(id="s1", description="Step 1", sub_agent="researcher", instruction="X"),
                PlanStep(id="s2", description="Step 2", sub_agent="synthesizer", instruction="Y"),
            ],
        )
        
        assert plan.progress_percent == 0.0
        
        plan.steps[0].complete()
        assert plan.progress_percent == 50.0
        
        plan.steps[1].complete()
        assert plan.progress_percent == 100.0

    def test_completed_steps(self):
        plan = ExecutionPlan(
            query="Test",
            goal="Test",
            steps=[
                PlanStep(id="s1", description="Step 1", sub_agent="researcher", instruction="X"),
                PlanStep(id="s2", description="Step 2", sub_agent="synthesizer", instruction="Y"),
            ],
        )
        
        assert len(plan.completed_steps) == 0
        
        plan.steps[0].complete()
        
        assert len(plan.completed_steps) == 1

    def test_failed_steps(self):
        plan = ExecutionPlan(
            query="Test",
            goal="Test",
            steps=[
                PlanStep(id="s1", description="Step 1", sub_agent="researcher", instruction="X"),
            ],
        )
        
        assert len(plan.failed_steps) == 0
        
        plan.steps[0].fail("Error")
        
        assert len(plan.failed_steps) == 1

    def test_get_step(self):
        plan = ExecutionPlan(
            query="Test",
            goal="Test",
            steps=[
                PlanStep(id="s1", description="Step 1", sub_agent="researcher", instruction="X"),
            ],
        )
        
        step = plan.get_step("s1")
        assert step is not None
        assert step.id == "s1"
        
        assert plan.get_step("nonexistent") is None

    def test_replan(self):
        plan = ExecutionPlan(
            query="Test",
            goal="Test",
            steps=[
                PlanStep(id="s1", description="Step 1", sub_agent="researcher", instruction="X"),
                PlanStep(id="s2", description="Step 2", sub_agent="synthesizer", instruction="Y"),
            ],
        )
        
        plan.steps[0].complete()
        
        new_steps = [
            PlanStep(id="s3", description="New step", sub_agent="analyzer", instruction="Z"),
        ]
        
        plan.replan(new_steps)
        
        assert plan.version == 2
        assert len(plan.steps) == 2  # Completed s1 + new s3
        assert plan.steps[0].id == "s1"
        assert plan.steps[1].id == "s3"


class TestSubAgentResult:
    """Tests for SubAgentResult model."""

    def test_success_result(self):
        result = SubAgentResult.success_result(
            output="Test output",
            tokens_used=100,
            duration_ms=50.0,
        )
        
        assert result.success
        assert result.output == "Test output"
        assert result.tokens_used == 100
        assert result.error is None

    def test_failure_result(self):
        result = SubAgentResult.failure_result(
            error="Something failed",
            duration_ms=10.0,
        )
        
        assert not result.success
        assert result.output is None
        assert result.error == "Something failed"

    def test_replan_result(self):
        result = SubAgentResult.replan_result(
            reason="Need more information",
            output="Partial data",
        )
        
        assert result.success
        assert result.replan_needed
        assert result.replan_reason == "Need more information"


class TestToolResult:
    """Tests for ToolResult model."""

    def test_success_result(self):
        result = ToolResult.success_result(
            tool_call_id="call_123",
            tool_name="search_po",
            result={"items": []},
            compact_result={"count": 0},
            duration_ms=100.0,
        )
        
        assert result.success
        assert result.tool_call_id == "call_123"
        assert result.tool_name == "search_po"
        assert result.result == {"items": []}
        assert result.compact_result == {"count": 0}

    def test_failure_result(self):
        result = ToolResult.failure_result(
            tool_call_id="call_123",
            tool_name="search_po",
            error="API error",
        )
        
        assert not result.success
        assert result.error == "API error"

    def test_get_result_for_context(self):
        # With compact result
        result1 = ToolResult.success_result(
            tool_call_id="1",
            tool_name="test",
            result={"full": "data"},
            compact_result={"compact": "data"},
        )
        assert result1.get_result_for_context() == {"compact": "data"}
        
        # Without compact result
        result2 = ToolResult.success_result(
            tool_call_id="2",
            tool_name="test",
            result={"full": "data"},
        )
        assert result2.get_result_for_context() == {"full": "data"}


class TestBlackboard:
    """Tests for Blackboard."""

    def test_create(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test query")
        
        assert bb.ctx == request_ctx
        assert bb.query == "Test query"
        assert bb.plan is None
        assert len(bb.tool_results) == 0
        assert len(bb.findings) == 0

    def test_set_and_get_variable(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test")
        
        bb.set("key1", "value1", source="test")
        
        assert bb.get("key1") == "value1"
        assert bb.get("nonexistent") is None
        assert bb.get("nonexistent", "default") == "default"
        assert bb.has("key1")
        assert not bb.has("nonexistent")

    def test_get_all_variables(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test")
        
        bb.set("key1", "value1", source="test")
        bb.set("key2", "value2", source="test")
        
        all_vars = bb.get_all_variables()
        
        assert all_vars == {"key1": "value1", "key2": "value2"}

    def test_variable_history(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test")
        
        bb.set("key1", "v1", source="s1")
        bb.set("key1", "v2", source="s2")
        
        history = bb.get_variable_history("key1")
        
        assert len(history) == 2
        assert history[0].value == "v1"
        assert history[1].value == "v2"

    def test_add_tool_result(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test")
        
        bb.add_tool_result(
            tool_call_id="call_1",
            tool_name="search",
            result={"data": "test"},
        )
        
        assert len(bb.tool_results) == 1
        assert bb.tool_results[0].tool_name == "search"
        assert bb.tool_results[0].success

    def test_add_tool_error(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test")
        
        bb.add_tool_error(
            tool_call_id="call_1",
            tool_name="search",
            error="API error",
        )
        
        assert len(bb.tool_results) == 1
        assert not bb.tool_results[0].success
        assert bb.tool_results[0].error == "API error"

    def test_get_tool_result(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test")
        
        bb.add_tool_result("call_1", "search", {"data": "test"})
        
        result = bb.get_tool_result("call_1")
        assert result is not None
        assert result.tool_call_id == "call_1"
        
        assert bb.get_tool_result("nonexistent") is None

    def test_add_finding(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test")
        
        bb.add_finding(
            source="researcher",
            content="Found relevant data",
            evidence="From API response",
            confidence=0.9,
        )
        
        assert len(bb.findings) == 1
        assert bb.findings[0].source == "researcher"
        assert bb.findings[0].confidence == 0.9

    def test_get_findings_by_source(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test")
        
        bb.add_finding(source="researcher", content="Finding 1")
        bb.add_finding(source="analyzer", content="Finding 2")
        bb.add_finding(source="researcher", content="Finding 3")
        
        researcher_findings = bb.get_findings_by_source("researcher")
        
        assert len(researcher_findings) == 2

    def test_pending_interactions(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test")
        
        assert not bb.has_pending_interactions()
        
        interaction_id = bb.add_pending_interaction(
            interaction_type="confirm",
            prompt="Are you sure?",
            options=["Yes", "No"],
        )
        
        assert bb.has_pending_interactions()
        assert len(bb.pending_interactions) == 1
        
        # Resolve interaction
        bb.resolve_interaction(interaction_id, "Yes")
        
        assert not bb.has_pending_interactions()

    def test_message_history(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test")
        
        bb.add_message("user", "Hello")
        bb.add_message("assistant", "Hi there!")
        
        assert len(bb.message_history) == 2
        assert bb.message_history[0]["role"] == "user"
        assert bb.message_history[1]["content"] == "Hi there!"

    def test_get_context_for_llm(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test")
        
        bb.set("key1", "value1", source="test")
        bb.add_finding(source="researcher", content="Found something")
        bb.add_tool_result("call_1", "search", {"data": "test"})
        
        context = bb.get_context_for_llm()
        
        assert "key1" in context
        assert "Found something" in context
        assert "search" in context

    def test_to_summary(self, request_ctx):
        bb = Blackboard.create(ctx=request_ctx, query="Test query")
        
        bb.set("key1", "value1", source="test")
        bb.add_finding(source="researcher", content="Finding")
        
        summary = bb.to_summary()
        
        assert summary["query"] == "Test query"
        assert summary["variables_count"] == 1
        assert summary["findings_count"] == 1


class TestAgentState:
    """Tests for AgentState enum."""

    def test_states(self):
        assert AgentState.IDLE.value == "idle"
        assert AgentState.PLANNING.value == "planning"
        assert AgentState.RESEARCHING.value == "researching"
        assert AgentState.ANALYZING.value == "analyzing"
        assert AgentState.EXECUTING.value == "executing"
        assert AgentState.SYNTHESIZING.value == "synthesizing"
        assert AgentState.WAITING_FOR_INPUT.value == "waiting_for_input"
        assert AgentState.COMPLETED.value == "completed"
        assert AgentState.FAILED.value == "failed"


class TestBaseAgentToolIntegration:
    """Tests for BaseAgent tool integration."""

    def test_auto_register_tools(self, user):
        from agentcore.core.agent import BaseAgent
        from agentcore.tools.decorator import tool
        from agentcore.inference import InferenceClient
        from agentcore.knowledge.client import MockKnowledgeClient
        from unittest.mock import MagicMock

        class TestAgent(BaseAgent):
            agent_id = "test"
            name = "Test Agent"
            description = "Test agent"
            
            def get_system_prompt(self, ctx):
                return "System prompt"
            
            @tool(tags=["test"])
            async def search_data(self, query: str) -> dict:
                """Search for data.
                
                Args:
                    query: Search query
                """
                return {"results": []}
            
            @tool(tags=["test"])
            def get_info(self, item_id: str) -> dict:
                """Get item info.
                
                Args:
                    item_id: Item ID
                """
                return {"id": item_id}

        mock_inference = MagicMock(spec=InferenceClient)
        mock_knowledge = MockKnowledgeClient()
        
        agent = TestAgent(inference=mock_inference, knowledge=mock_knowledge)
        
        assert agent.tool_registry.tool_count == 2
        assert "search_data" in agent.tool_registry
        assert "get_info" in agent.tool_registry

    def test_get_tools_returns_openai_format(self, user):
        from agentcore.core.agent import BaseAgent
        from agentcore.tools.decorator import tool
        from agentcore.inference import InferenceClient
        from agentcore.knowledge.client import MockKnowledgeClient
        from unittest.mock import MagicMock

        class TestAgent(BaseAgent):
            agent_id = "test"
            name = "Test Agent"
            description = "Test agent"
            
            def get_system_prompt(self, ctx):
                return "System prompt"
            
            @tool(tags=["test"])
            async def my_tool(self, value: str) -> str:
                """A test tool.
                
                Args:
                    value: Input value
                """
                return value

        mock_inference = MagicMock(spec=InferenceClient)
        mock_knowledge = MockKnowledgeClient()
        
        agent = TestAgent(inference=mock_inference, knowledge=mock_knowledge)
        tools = agent.get_tools()
        
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "my_tool"
        assert "value" in tools[0]["function"]["parameters"]["properties"]

    def test_tool_executor_accessible(self, user):
        from agentcore.core.agent import BaseAgent
        from agentcore.inference import InferenceClient
        from agentcore.knowledge.client import MockKnowledgeClient
        from agentcore.tools.executor import ToolExecutor
        from unittest.mock import MagicMock

        class TestAgent(BaseAgent):
            agent_id = "test"
            name = "Test Agent"
            description = "Test agent"
            
            def get_system_prompt(self, ctx):
                return "System prompt"

        mock_inference = MagicMock(spec=InferenceClient)
        mock_knowledge = MockKnowledgeClient()
        
        agent = TestAgent(inference=mock_inference, knowledge=mock_knowledge)
        
        assert isinstance(agent.tool_executor, ToolExecutor)
        assert agent.tool_executor.registry is agent.tool_registry

    def test_custom_tool_registry(self, user):
        from agentcore.core.agent import BaseAgent
        from agentcore.tools.registry import ToolRegistry
        from agentcore.tools.decorator import tool
        from agentcore.inference import InferenceClient
        from agentcore.knowledge.client import MockKnowledgeClient
        from unittest.mock import MagicMock

        @tool()
        def external_tool(x: int) -> int:
            """External tool."""
            return x * 2

        custom_registry = ToolRegistry()
        custom_registry.register(external_tool)

        class TestAgent(BaseAgent):
            agent_id = "test"
            name = "Test Agent"
            description = "Test agent"
            
            def get_system_prompt(self, ctx):
                return "System prompt"

        mock_inference = MagicMock(spec=InferenceClient)
        mock_knowledge = MockKnowledgeClient()
        
        agent = TestAgent(
            inference=mock_inference,
            knowledge=mock_knowledge,
            tool_registry=custom_registry,
        )
        
        assert agent.tool_registry is custom_registry
        assert "external_tool" in agent.tool_registry
        assert agent.tool_registry.tool_count == 1
