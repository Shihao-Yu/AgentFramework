"""Unit tests for sub_agents module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from agentcore.sub_agents.base import SubAgentBase, SubAgentConfig
from agentcore.sub_agents.planner import PlannerSubAgent
from agentcore.sub_agents.researcher import ResearcherSubAgent
from agentcore.sub_agents.analyzer import AnalyzerSubAgent
from agentcore.sub_agents.executor import ExecutorSubAgent
from agentcore.sub_agents.synthesizer import SynthesizerSubAgent
from agentcore.core.models import InteractionStatus, PlanStep, ExecutionPlan, SubAgentResult, StepStatus
from agentcore.core.blackboard import Blackboard
from agentcore.inference import InferenceResponse, ToolCall
from agentcore.auth.models import EnrichedUser, Permission
from agentcore.auth.context import RequestContext


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


@pytest.fixture
def blackboard(request_ctx):
    return Blackboard.create(ctx=request_ctx, query="Find PO 12345")


@pytest.fixture
def mock_inference():
    mock = AsyncMock()
    mock.complete = AsyncMock(return_value=InferenceResponse(
        content="Test response",
        tool_calls=None,
        finish_reason="stop",
        model="gpt-4",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    ))
    return mock


@pytest.fixture
def mock_retriever():
    from agentcore.knowledge.models import KnowledgeBundle
    mock = AsyncMock()
    mock.retrieve_for_planning = AsyncMock(return_value=KnowledgeBundle(query="test"))
    mock.retrieve_for_research = AsyncMock(return_value=KnowledgeBundle(query="test"))
    mock.retrieve_for_analysis = AsyncMock(return_value=KnowledgeBundle(query="test"))
    return mock


class TestSubAgentConfig:

    def test_default_config(self):
        config = SubAgentConfig()
        
        assert config.temperature == 0.7
        assert config.max_tokens == 2048
        assert config.max_context_chars == 4000
        assert config.retry_on_failure
        assert config.max_retries == 2

    def test_custom_config(self):
        config = SubAgentConfig(
            temperature=0.3,
            max_tokens=1024,
            retry_on_failure=False,
        )
        
        assert config.temperature == 0.3
        assert config.max_tokens == 1024
        assert not config.retry_on_failure


class TestSubAgentBase:

    def test_get_blackboard_context(self, mock_inference, blackboard):
        class ConcreteSubAgent(SubAgentBase):
            async def execute(self, ctx, blackboard, step, system_prompt):
                return SubAgentResult.success_result(output="test")
        
        agent = ConcreteSubAgent(inference=mock_inference)
        
        blackboard.set("key1", "value1", source="test")
        blackboard.add_finding(source="researcher", content="Finding 1")
        blackboard.add_tool_result("call_1", "search_po", {"items": []})
        
        context = agent._get_blackboard_context(blackboard)
        
        assert "key1" in context
        assert "value1" in context
        assert "Finding 1" in context
        assert "search_po" in context

    def test_truncate(self, mock_inference):
        class ConcreteSubAgent(SubAgentBase):
            async def execute(self, ctx, blackboard, step, system_prompt):
                return SubAgentResult.success_result(output="test")
        
        agent = ConcreteSubAgent(inference=mock_inference)
        
        short_text = "Short text"
        assert agent._truncate(short_text, 100) == short_text
        
        long_text = "A" * 100
        truncated = agent._truncate(long_text, 50)
        assert len(truncated) == 50
        assert truncated.endswith("...")


class TestPlannerSubAgent:

    @pytest.mark.asyncio
    async def test_execute_creates_plan(self, request_ctx, blackboard, mock_inference, mock_retriever):
        mock_inference.complete = AsyncMock(return_value=InferenceResponse(
            content='''```json
{
    "goal": "Find PO 12345",
    "steps": [
        {"id": "step_1", "description": "Search for PO", "sub_agent": "researcher", "instruction": "Search for PO 12345", "depends_on": []},
        {"id": "step_2", "description": "Return results", "sub_agent": "synthesizer", "instruction": "Format response", "depends_on": ["step_1"]}
    ]
}
```''',
            tool_calls=None,
            finish_reason="stop",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ))
        
        planner = PlannerSubAgent(
            inference=mock_inference,
            retriever=mock_retriever,
        )
        
        step = PlanStep(
            id="plan_step",
            description="Create execution plan",
            sub_agent="planner",
            instruction="Plan how to handle the query",
        )
        
        result = await planner.execute(request_ctx, blackboard, step, "You are a helpful assistant.")
        
        assert result.success
        assert isinstance(result.output, ExecutionPlan)
        assert len(result.output.steps) == 2

    @pytest.mark.asyncio
    async def test_create_plan(self, request_ctx, mock_inference, mock_retriever):
        mock_inference.complete = AsyncMock(return_value=InferenceResponse(
            content='{"goal": "Test goal", "steps": [{"id": "s1", "description": "Step 1", "sub_agent": "researcher", "instruction": "Do X"}]}',
            tool_calls=None,
            finish_reason="stop",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ))
        
        planner = PlannerSubAgent(inference=mock_inference, retriever=mock_retriever)
        
        plan = await planner.create_plan(
            ctx=request_ctx,
            query="Test query",
            system_prompt="You are helpful",
        )
        
        assert plan.goal == "Test goal"
        assert len(plan.steps) == 1

    def test_parse_plan_valid_json(self, mock_inference):
        planner = PlannerSubAgent(inference=mock_inference)
        
        content = '''{"goal": "Test", "steps": [{"id": "s1", "description": "Do X", "sub_agent": "researcher", "instruction": "Find Y"}]}'''
        
        plan = planner._parse_plan("Test query", content)
        
        assert plan.goal == "Test"
        assert len(plan.steps) == 1
        assert plan.steps[0].sub_agent == "researcher"

    def test_parse_plan_invalid_json_fallback(self, mock_inference):
        planner = PlannerSubAgent(inference=mock_inference)
        
        content = "This is not JSON"
        
        plan = planner._parse_plan("Test query", content)
        
        assert plan.goal == "Answer the user's query"
        assert len(plan.steps) == 2
        assert plan.steps[0].sub_agent == "researcher"
        assert plan.steps[1].sub_agent == "synthesizer"

    def test_fallback_plan(self, mock_inference):
        planner = PlannerSubAgent(inference=mock_inference)
        
        plan = planner._fallback_plan("Test query")
        
        assert plan.query == "Test query"
        assert len(plan.steps) == 2


class TestResearcherSubAgent:

    @pytest.mark.asyncio
    async def test_execute_adds_finding(self, request_ctx, blackboard, mock_inference, mock_retriever):
        mock_inference.complete = AsyncMock(return_value=InferenceResponse(
            content="Found PO 12345: Status is APPROVED, amount $5000",
            tool_calls=None,
            finish_reason="stop",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ))
        
        researcher = ResearcherSubAgent(
            inference=mock_inference,
            retriever=mock_retriever,
        )
        
        step = PlanStep(
            id="research_step",
            description="Research PO",
            sub_agent="researcher",
            instruction="Find PO 12345",
        )
        
        result = await researcher.execute(request_ctx, blackboard, step, "You are helpful")
        
        assert result.success
        assert "Found PO" in result.output
        assert len(blackboard.findings) == 1

    @pytest.mark.asyncio
    async def test_execute_with_tools(self, request_ctx, blackboard, mock_inference, mock_retriever):
        tool_call = ToolCall(
            id="call_123",
            name="search_po",
            arguments={"po_number": "12345"},
        )
        mock_inference.complete = AsyncMock(side_effect=[
            InferenceResponse(
                content="Let me search for that PO",
                tool_calls=[tool_call],
                finish_reason="tool_calls",
                model="gpt-4",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            ),
            InferenceResponse(
                content="Found the PO: approved",
                tool_calls=None,
                finish_reason="stop",
                model="gpt-4",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            ),
        ])
        
        tools = [{
            "type": "function",
            "function": {
                "name": "search_po",
                "description": "Search for PO",
                "parameters": {"type": "object", "properties": {}},
            },
        }]
        
        researcher = ResearcherSubAgent(
            inference=mock_inference,
            retriever=mock_retriever,
            tools=tools,
        )
        
        step = PlanStep(
            id="research_step",
            description="Research PO",
            sub_agent="researcher",
            instruction="Find PO 12345",
        )
        
        result = await researcher.execute(request_ctx, blackboard, step, "You are helpful")
        
        assert result.success
        assert len(blackboard.tool_results) == 1

    def test_set_tools(self, mock_inference):
        researcher = ResearcherSubAgent(inference=mock_inference)
        
        tools = [{"type": "function", "function": {"name": "test"}}]
        researcher.set_tools(tools)
        
        assert researcher._tools == tools


class TestAnalyzerSubAgent:

    @pytest.mark.asyncio
    async def test_execute_adds_finding(self, request_ctx, blackboard, mock_inference, mock_retriever):
        mock_inference.complete = AsyncMock(return_value=InferenceResponse(
            content="Analysis: The PO appears to be valid. Confidence: high",
            tool_calls=None,
            finish_reason="stop",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ))
        
        analyzer = AnalyzerSubAgent(
            inference=mock_inference,
            retriever=mock_retriever,
        )
        
        blackboard.add_finding(source="researcher", content="PO 12345 found")
        
        step = PlanStep(
            id="analyze_step",
            description="Analyze findings",
            sub_agent="analyzer",
            instruction="Analyze the PO data",
        )
        
        result = await analyzer.execute(request_ctx, blackboard, step, "You are helpful")
        
        assert result.success
        assert "Analysis" in result.output
        assert len(blackboard.findings) == 2

    @pytest.mark.asyncio
    async def test_execute_triggers_replan(self, request_ctx, blackboard, mock_inference, mock_retriever):
        mock_inference.complete = AsyncMock(return_value=InferenceResponse(
            content="Analysis: Insufficient data.\nREPLAN_NEEDED: Need to fetch additional vendor information",
            tool_calls=None,
            finish_reason="stop",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ))
        
        analyzer = AnalyzerSubAgent(
            inference=mock_inference,
            retriever=mock_retriever,
        )
        
        step = PlanStep(
            id="analyze_step",
            description="Analyze",
            sub_agent="analyzer",
            instruction="Analyze",
        )
        
        result = await analyzer.execute(request_ctx, blackboard, step, "You are helpful")
        
        assert result.success
        assert result.replan_needed
        assert "vendor" in result.replan_reason.lower()

    def test_check_for_replan(self, mock_inference):
        analyzer = AnalyzerSubAgent(inference=mock_inference)
        
        content_with_replan = "Analysis complete.\nREPLAN_NEEDED: Need more data"
        replan_needed, reason = analyzer._check_for_replan(content_with_replan)
        assert replan_needed
        assert "more data" in reason
        
        content_without_replan = "Analysis complete."
        replan_needed, reason = analyzer._check_for_replan(content_without_replan)
        assert not replan_needed
        assert reason is None


class TestExecutorSubAgent:

    @pytest.mark.asyncio
    async def test_execute_with_tool_calls(self, request_ctx, blackboard, mock_inference):
        tool_call = ToolCall(
            id="call_456",
            name="create_po",
            arguments={"vendor_id": "V123", "amount": 1000},
        )
        mock_inference.complete = AsyncMock(return_value=InferenceResponse(
            content="Creating PO",
            tool_calls=[tool_call],
            finish_reason="tool_calls",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ))
        
        async def mock_create_po(ctx, vendor_id, amount):
            return {"po_id": "PO-789", "status": "created"}
        
        executor = ExecutorSubAgent(
            inference=mock_inference,
            tool_functions={"create_po": mock_create_po},
            tools=[{
                "type": "function",
                "function": {
                    "name": "create_po",
                    "description": "Create PO",
                    "parameters": {"type": "object", "properties": {}},
                },
            }],
        )
        
        step = PlanStep(
            id="exec_step",
            description="Create PO",
            sub_agent="executor",
            instruction="Create a new PO",
        )
        
        result = await executor.execute(request_ctx, blackboard, step, "You are helpful")
        
        assert result.success
        assert len(blackboard.tool_results) == 1
        assert blackboard.tool_results[0].tool_name == "create_po"

    @pytest.mark.asyncio
    async def test_execute_hil_required(self, request_ctx, blackboard, mock_inference):
        tool_call = ToolCall(
            id="call_delete",
            name="delete_po",
            arguments={"po_id": "PO-123"},
        )
        mock_inference.complete = AsyncMock(return_value=InferenceResponse(
            content="Deleting PO",
            tool_calls=[tool_call],
            finish_reason="tool_calls",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ))
        
        executor = ExecutorSubAgent(
            inference=mock_inference,
            tools=[{
                "type": "function",
                "function": {
                    "name": "delete_po",
                    "description": "Delete PO",
                    "parameters": {"type": "object", "properties": {}},
                },
            }],
        )
        
        step = PlanStep(
            id="exec_step",
            description="Delete PO",
            sub_agent="executor",
            instruction="Delete PO-123",
        )
        
        result = await executor.execute(request_ctx, blackboard, step, "You are helpful")
        
        assert result.success
        assert result.output["status"] == InteractionStatus.AWAITING_APPROVAL
        assert blackboard.has_pending_interactions()

    def test_requires_hil_destructive(self, mock_inference):
        executor = ExecutorSubAgent(inference=mock_inference)
        
        assert executor._requires_hil("delete_po", {})
        assert executor._requires_hil("remove_item", {})
        assert executor._requires_hil("cancel_order", {})
        assert not executor._requires_hil("search_po", {})
        assert not executor._requires_hil("get_vendor", {})

    def test_requires_hil_high_value(self, mock_inference):
        executor = ExecutorSubAgent(inference=mock_inference)
        
        assert executor._requires_hil("create_po", {"amount": 15000})
        assert not executor._requires_hil("create_po", {"amount": 5000})

    def test_describe_action(self, mock_inference):
        executor = ExecutorSubAgent(inference=mock_inference)
        
        description = executor._describe_action("create_po", {"vendor_id": "V1", "amount": 1000})
        
        assert "create_po" in description
        assert "vendor_id=V1" in description
        assert "amount=1000" in description

    def test_register_tool(self, mock_inference):
        executor = ExecutorSubAgent(inference=mock_inference)
        
        def my_tool(ctx):
            return "result"
        
        tool_def = {
            "type": "function",
            "function": {"name": "my_tool", "description": "My tool"},
        }
        
        executor.register_tool("my_tool", my_tool, tool_def)
        
        assert "my_tool" in executor._tool_functions
        assert len(executor._tools) == 1

    def test_summarize_results(self, mock_inference):
        from agentcore.core.models import ToolResult
        
        executor = ExecutorSubAgent(inference=mock_inference)
        
        results = [
            ToolResult.success_result("call_1", "tool_a", {"data": "test"}),
            ToolResult.failure_result("call_2", "tool_b", "Error occurred"),
        ]
        
        summary = executor._summarize_results(results)
        
        assert summary["total_actions"] == 2
        assert summary["successful"] == 1
        assert summary["failed"] == 1


class TestSynthesizerSubAgent:

    @pytest.mark.asyncio
    async def test_execute_generates_response(self, request_ctx, blackboard, mock_inference, mock_retriever):
        mock_inference.complete = AsyncMock(return_value=InferenceResponse(
            content="## PO 12345 Summary\n\nThe purchase order was found and is **approved**.",
            tool_calls=None,
            finish_reason="stop",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ))
        
        synthesizer = SynthesizerSubAgent(
            inference=mock_inference,
            retriever=mock_retriever,
        )
        
        blackboard.add_finding(source="researcher", content="PO 12345: approved")
        blackboard.plan = ExecutionPlan(query="Find PO", goal="Find PO")
        
        step = PlanStep(
            id="synth_step",
            description="Generate response",
            sub_agent="synthesizer",
            instruction="Create a summary",
        )
        
        result = await synthesizer.execute(request_ctx, blackboard, step, "You are helpful")
        
        assert result.success
        assert "PO 12345" in result.output
        assert blackboard.plan.final_result is not None

    @pytest.mark.asyncio
    async def test_generate_suggestions(self, request_ctx, mock_inference):
        mock_inference.complete = AsyncMock(return_value=InferenceResponse(
            content='["Check PO status", "View vendor details", "Create new PO"]',
            tool_calls=None,
            finish_reason="stop",
            model="gpt-4",
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
        ))
        
        synthesizer = SynthesizerSubAgent(inference=mock_inference)
        
        suggestions = await synthesizer.generate_suggestions(
            ctx=request_ctx,
            query="Find PO 12345",
            response="PO 12345 is approved",
            system_prompt="You are helpful",
        )
        
        assert len(suggestions) == 3
        assert "Check PO status" in suggestions

    @pytest.mark.asyncio
    async def test_summarize(self, request_ctx, mock_inference):
        mock_inference.complete = AsyncMock(return_value=InferenceResponse(
            content="PO 12345 approved for $5000.",
            tool_calls=None,
            finish_reason="stop",
            model="gpt-4",
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
        ))
        
        synthesizer = SynthesizerSubAgent(inference=mock_inference)
        
        summary = await synthesizer.summarize(
            ctx=request_ctx,
            content="This is a very long content about PO 12345 that needs to be summarized...",
            max_length=50,
        )
        
        assert len(summary) <= 50

    def test_get_format_instructions(self, mock_inference):
        synthesizer = SynthesizerSubAgent(inference=mock_inference)
        
        markdown_inst = synthesizer._get_format_instructions("markdown")
        assert "Markdown" in markdown_inst
        
        json_inst = synthesizer._get_format_instructions("json")
        assert "JSON" in json_inst
        
        plain_inst = synthesizer._get_format_instructions("plain")
        assert "plain text" in plain_inst


class TestSubAgentIntegration:

    @pytest.mark.asyncio
    async def test_full_workflow(self, request_ctx, blackboard, mock_inference, mock_retriever):
        plan_response = InferenceResponse(
            content='{"goal": "Find PO", "steps": [{"id": "s1", "description": "Research", "sub_agent": "researcher", "instruction": "Find PO"}]}',
            tool_calls=None,
            finish_reason="stop",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        research_response = InferenceResponse(
            content="Found PO 12345: approved",
            tool_calls=None,
            finish_reason="stop",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        synth_response = InferenceResponse(
            content="## Summary\nPO 12345 is approved.",
            tool_calls=None,
            finish_reason="stop",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        
        mock_inference.complete = AsyncMock(side_effect=[plan_response, research_response, synth_response])
        
        planner = PlannerSubAgent(inference=mock_inference, retriever=mock_retriever)
        researcher = ResearcherSubAgent(inference=mock_inference, retriever=mock_retriever)
        synthesizer = SynthesizerSubAgent(inference=mock_inference, retriever=mock_retriever)
        
        plan_step = PlanStep(id="plan", description="Plan", sub_agent="planner", instruction="Plan")
        plan_result = await planner.execute(request_ctx, blackboard, plan_step, "You are helpful")
        
        assert plan_result.success
        plan = plan_result.output
        blackboard.plan = plan
        
        research_step = plan.steps[0]
        research_result = await researcher.execute(request_ctx, blackboard, research_step, "You are helpful")
        
        assert research_result.success
        assert len(blackboard.findings) >= 1
        
        synth_step = PlanStep(id="synth", description="Synthesize", sub_agent="synthesizer", instruction="Create response")
        synth_result = await synthesizer.execute(request_ctx, blackboard, synth_step, "You are helpful")
        
        assert synth_result.success
        assert "Summary" in synth_result.output
