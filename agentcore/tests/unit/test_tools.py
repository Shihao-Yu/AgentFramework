"""Unit tests for the tools module."""

from __future__ import annotations

import asyncio
from typing import Optional

import pytest

from agentcore.auth.context import RequestContext
from agentcore.auth.models import EnrichedUser, Permission
from agentcore.tools.decorator import tool, get_tool_spec, is_tool
from agentcore.tools.models import (
    HILConfig,
    ParameterType,
    RetentionStrategy,
    ToolParameter,
    ToolSpec,
)
from agentcore.tools.registry import ToolRegistry
from agentcore.tools.executor import ToolExecutor


@pytest.fixture
def user() -> EnrichedUser:
    return EnrichedUser(
        user_id=1,
        username="test",
        email="test@example.com",
        display_name="Test User",
        entity_id=1,
        entity_name="Test Corp",
        permissions=frozenset([Permission.BUYER, Permission.PO_CREATE]),
    )


@pytest.fixture
def ctx(user: EnrichedUser) -> RequestContext:
    return RequestContext.create(
        user=user,
        session_id="session-123",
        request_id="req-456",
    )


class TestToolParameter:
    def test_parameter_to_json_schema_basic(self):
        param = ToolParameter(
            name="vendor_id",
            type=ParameterType.STRING,
            description="The vendor ID",
            required=True,
        )
        
        schema = param.to_json_schema()
        
        assert schema["type"] == "string"
        assert schema["description"] == "The vendor ID"
    
    def test_parameter_to_json_schema_with_enum(self):
        param = ToolParameter(
            name="status",
            type=ParameterType.STRING,
            enum=["pending", "approved", "rejected"],
        )
        
        schema = param.to_json_schema()
        
        assert schema["enum"] == ["pending", "approved", "rejected"]
    
    def test_parameter_to_json_schema_with_default(self):
        param = ToolParameter(
            name="limit",
            type=ParameterType.INTEGER,
            required=False,
            default=10,
        )
        
        schema = param.to_json_schema()
        
        assert schema["default"] == 10
    
    def test_parameter_to_json_schema_array(self):
        param = ToolParameter(
            name="items",
            type=ParameterType.ARRAY,
            items_type=ParameterType.STRING,
        )
        
        schema = param.to_json_schema()
        
        assert schema["type"] == "array"
        assert schema["items"] == {"type": "string"}


class TestRetentionStrategy:
    def test_should_compact_by_chars(self):
        retention = RetentionStrategy(max_chars=100)
        
        short_result = "short"
        long_result = "x" * 200
        
        assert not retention.should_compact(short_result)
        assert retention.should_compact(long_result)
    
    def test_should_compact_by_items(self):
        retention = RetentionStrategy(max_items=5)
        
        short_list = [1, 2, 3]
        long_list = list(range(10))
        
        assert not retention.should_compact(short_list)
        assert retention.should_compact(long_list)
    
    def test_compact_list(self):
        retention = RetentionStrategy(max_items=3)
        
        result = retention.compact([1, 2, 3, 4, 5])
        
        assert result["items"] == [1, 2, 3]
        assert result["total_count"] == 5
        assert result["truncated"] is True
    
    def test_compact_dict_with_fields(self):
        retention = RetentionStrategy(compact_fields=["id", "name"])
        
        result = retention.compact({
            "id": 123,
            "name": "Test",
            "description": "Long description",
            "metadata": {"extra": "data"},
        })
        
        assert result == {"id": 123, "name": "Test"}
    
    def test_compact_by_chars(self):
        retention = RetentionStrategy(max_chars=20)
        
        result = retention.compact("This is a very long string that needs truncation")
        
        assert result["truncated"] is True
        assert len(result["summary"]) <= 23


class TestHILConfig:
    def test_requires_confirmation_always(self):
        hil = HILConfig(requires_confirmation=True)
        
        assert hil.requires_confirmation_for({})
        assert hil.requires_confirmation_for({"any": "args"})
    
    def test_requires_confirmation_by_threshold(self):
        hil = HILConfig(
            requires_confirmation=False,
            high_value_threshold=10000,
            high_value_field="amount",
        )
        
        assert not hil.requires_confirmation_for({"amount": 5000})
        assert hil.requires_confirmation_for({"amount": 15000})
        assert not hil.requires_confirmation_for({})


class TestToolSpec:
    def test_to_openai_format_basic(self):
        spec = ToolSpec(
            id="test_tool_1_0_0",
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(
                    name="param1",
                    type=ParameterType.STRING,
                    description="First param",
                    required=True,
                ),
                ToolParameter(
                    name="param2",
                    type=ParameterType.INTEGER,
                    required=False,
                    default=10,
                ),
            ],
        )
        
        openai_format = spec.to_openai_format()
        
        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "test_tool"
        assert openai_format["function"]["description"] == "A test tool"
        
        params = openai_format["function"]["parameters"]
        assert params["type"] == "object"
        assert "param1" in params["properties"]
        assert "param2" in params["properties"]
        assert params["required"] == ["param1"]
    
    def test_get_parameter(self):
        spec = ToolSpec(
            id="test_1",
            name="test",
            description="Test",
            parameters=[
                ToolParameter(name="a", type=ParameterType.STRING),
                ToolParameter(name="b", type=ParameterType.INTEGER),
            ],
        )
        
        assert spec.get_parameter("a") is not None
        assert spec.get_parameter("a").type == ParameterType.STRING
        assert spec.get_parameter("c") is None
    
    def test_requires_hil_for(self):
        spec = ToolSpec(
            id="test_1",
            name="test",
            description="Test",
            hil=HILConfig(
                requires_confirmation=False,
                high_value_threshold=5000,
            ),
        )
        
        assert not spec.requires_hil_for({"amount": 1000})
        assert spec.requires_hil_for({"amount": 10000})
    
    def test_compact_result_with_retention(self):
        spec = ToolSpec(
            id="test_1",
            name="test",
            description="Test",
            retention=RetentionStrategy(max_items=2),
        )
        
        result = spec.compact_result([1, 2, 3, 4, 5])
        
        assert result["truncated"] is True
        assert result["items"] == [1, 2]


class TestToolDecorator:
    def test_basic_decorator(self):
        @tool()
        def my_tool(value: str) -> str:
            return value.upper()
        
        assert is_tool(my_tool)
        spec = get_tool_spec(my_tool)
        
        assert spec is not None
        assert spec.name == "my_tool"
        assert len(spec.parameters) == 1
        assert spec.parameters[0].name == "value"
        assert spec.parameters[0].type == ParameterType.STRING
    
    def test_decorator_with_docstring(self):
        @tool()
        def search_vendors(
            query: str,
            limit: int = 10,
        ) -> list:
            """Search for vendors.
            
            Args:
                query: Search query text
                limit: Maximum results
                
            Returns:
                List of matching vendors
            """
            return []
        
        spec = get_tool_spec(search_vendors)
        
        assert spec.description == "Search for vendors."
        assert spec.get_parameter("query").description == "Search query text"
        assert spec.get_parameter("limit").description == "Maximum results"
        assert spec.get_parameter("limit").required is False
    
    def test_decorator_with_options(self):
        @tool(
            name="custom_name",
            description="Custom description",
            tags=["test", "example"],
            requires_permissions=["Admin"],
            timeout=60.0,
        )
        def my_func(x: int) -> int:
            return x * 2
        
        spec = get_tool_spec(my_func)
        
        assert spec.name == "custom_name"
        assert spec.description == "Custom description"
        assert spec.tags == ["test", "example"]
        assert spec.requires_permissions == ["Admin"]
        assert spec.timeout == 60.0
    
    def test_decorator_with_optional_params(self):
        @tool()
        def optional_tool(
            required_param: str,
            optional_param: Optional[str] = None,
        ) -> dict:
            return {}
        
        spec = get_tool_spec(optional_tool)
        
        assert spec.get_parameter("required_param").required is True
        assert spec.get_parameter("optional_param").required is False
    
    def test_decorator_with_list_params(self):
        @tool()
        def list_tool(items: list[str]) -> int:
            return len(items)
        
        spec = get_tool_spec(list_tool)
        param = spec.get_parameter("items")
        
        assert param.type == ParameterType.ARRAY
        assert param.items_type == ParameterType.STRING
    
    def test_async_decorator(self):
        @tool()
        async def async_tool(value: str) -> str:
            return value
        
        spec = get_tool_spec(async_tool)
        
        assert spec.is_async is True
    
    def test_decorator_skips_ctx_param(self):
        @tool()
        def tool_with_ctx(ctx: RequestContext, value: str) -> str:
            return value
        
        spec = get_tool_spec(tool_with_ctx)
        
        assert len(spec.parameters) == 1
        assert spec.parameters[0].name == "value"


class TestToolRegistry:
    def test_register_decorated_function(self):
        registry = ToolRegistry()
        
        @tool()
        def my_tool(x: int) -> int:
            return x
        
        registry.register(my_tool)
        
        assert "my_tool" in registry
        assert registry.get("my_tool") is not None
    
    def test_register_raises_for_undecorated(self):
        registry = ToolRegistry()
        
        def not_a_tool(x: int) -> int:
            return x
        
        with pytest.raises(ValueError, match="not decorated"):
            registry.register(not_a_tool)
    
    def test_register_spec(self):
        registry = ToolRegistry()
        
        spec = ToolSpec(
            id="manual_1",
            name="manual",
            description="Manual tool",
        )
        
        def manual_func() -> str:
            return "manual"
        
        registry.register_spec(spec, manual_func)
        
        assert "manual" in registry
        assert registry.get_function("manual") is manual_func
    
    def test_list_tools_by_tags(self):
        registry = ToolRegistry()
        
        @tool(tags=["purchasing"])
        def tool_a(x: int) -> int:
            return x
        
        @tool(tags=["inventory"])
        def tool_b(x: int) -> int:
            return x
        
        @tool(tags=["purchasing", "inventory"])
        def tool_c(x: int) -> int:
            return x
        
        registry.register(tool_a)
        registry.register(tool_b)
        registry.register(tool_c)
        
        purchasing_tools = registry.list_tools(tags=["purchasing"])
        
        assert len(purchasing_tools) == 2
        names = [t.name for t in purchasing_tools]
        assert "tool_a" in names
        assert "tool_c" in names
    
    def test_get_tools_for_context_with_permissions(self, ctx):
        registry = ToolRegistry()
        
        @tool(requires_permissions=["Buyer"])
        def buyer_tool(x: int) -> int:
            return x
        
        @tool(requires_permissions=["Admin"])
        def admin_tool(x: int) -> int:
            return x
        
        @tool()
        def public_tool(x: int) -> int:
            return x
        
        registry.register(buyer_tool)
        registry.register(admin_tool)
        registry.register(public_tool)
        
        available = registry.get_tools_for_context(ctx)
        names = [t.name for t in available]
        
        assert "buyer_tool" in names
        assert "public_tool" in names
        assert "admin_tool" not in names
    
    def test_get_openai_tools(self, ctx):
        registry = ToolRegistry()
        
        @tool()
        def my_tool(value: str) -> str:
            """A simple tool."""
            return value
        
        registry.register(my_tool)
        
        tools = registry.get_openai_tools(ctx)
        
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "my_tool"
    
    def test_validate_permission_success(self, ctx):
        registry = ToolRegistry()
        
        @tool(requires_permissions=["Buyer"])
        def buyer_tool(x: int) -> int:
            return x
        
        registry.register(buyer_tool)
        
        is_valid, error = registry.validate_permission("buyer_tool", ctx)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_permission_failure(self, ctx):
        registry = ToolRegistry()
        
        @tool(requires_permissions=["Admin"])
        def admin_tool(x: int) -> int:
            return x
        
        registry.register(admin_tool)
        
        is_valid, error = registry.validate_permission("admin_tool", ctx)
        
        assert is_valid is False
        assert "Permission denied" in error
    
    def test_unregister(self):
        registry = ToolRegistry()
        
        @tool()
        def my_tool(x: int) -> int:
            return x
        
        registry.register(my_tool)
        assert "my_tool" in registry
        
        result = registry.unregister("my_tool")
        
        assert result is True
        assert "my_tool" not in registry
    
    def test_register_all_from_object(self):
        registry = ToolRegistry()
        
        class MyAgent:
            @tool()
            def tool_one(self, x: int) -> int:
                return x
            
            @tool()
            def tool_two(self, y: str) -> str:
                return y
            
            def not_a_tool(self) -> None:
                pass
        
        agent = MyAgent()
        count = registry.register_all(agent)
        
        assert count == 2
        assert "tool_one" in registry
        assert "tool_two" in registry


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_execute_success(self, ctx):
        registry = ToolRegistry()
        
        @tool()
        async def add_numbers(a: int, b: int) -> int:
            return a + b
        
        registry.register(add_numbers)
        executor = ToolExecutor(registry)
        
        result = await executor.execute(
            ctx=ctx,
            tool_name="add_numbers",
            arguments={"a": 2, "b": 3},
            tool_call_id="call_1",
        )
        
        assert result.success is True
        assert result.result == 5
        assert result.tool_name == "add_numbers"
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, ctx):
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        
        result = await executor.execute(
            ctx=ctx,
            tool_name="nonexistent",
            arguments={},
            tool_call_id="call_1",
        )
        
        assert result.success is False
        assert "not found" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_permission_denied(self, ctx):
        registry = ToolRegistry()
        
        @tool(requires_permissions=["Admin"])
        async def admin_tool(x: int) -> int:
            return x
        
        registry.register(admin_tool)
        executor = ToolExecutor(registry)
        
        result = await executor.execute(
            ctx=ctx,
            tool_name="admin_tool",
            arguments={"x": 5},
            tool_call_id="call_1",
        )
        
        assert result.success is False
        assert "Permission denied" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, ctx):
        registry = ToolRegistry()
        
        @tool(timeout=0.1)
        async def slow_tool(x: int) -> int:
            await asyncio.sleep(1)
            return x
        
        registry.register(slow_tool)
        executor = ToolExecutor(registry)
        
        result = await executor.execute(
            ctx=ctx,
            tool_name="slow_tool",
            arguments={"x": 5},
            tool_call_id="call_1",
        )
        
        assert result.success is False
        assert "timed out" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_with_exception(self, ctx):
        registry = ToolRegistry()
        
        @tool()
        async def failing_tool(x: int) -> int:
            raise ValueError("Something went wrong")
        
        registry.register(failing_tool)
        executor = ToolExecutor(registry)
        
        result = await executor.execute(
            ctx=ctx,
            tool_name="failing_tool",
            arguments={"x": 5},
            tool_call_id="call_1",
        )
        
        assert result.success is False
        assert "Something went wrong" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_sync_function(self, ctx):
        registry = ToolRegistry()
        
        @tool()
        def sync_tool(x: int, y: int) -> int:
            return x * y
        
        registry.register(sync_tool)
        executor = ToolExecutor(registry)
        
        result = await executor.execute(
            ctx=ctx,
            tool_name="sync_tool",
            arguments={"x": 3, "y": 4},
            tool_call_id="call_1",
        )
        
        assert result.success is True
        assert result.result == 12
    
    @pytest.mark.asyncio
    async def test_execute_many_parallel(self, ctx):
        registry = ToolRegistry()
        call_times = []
        
        @tool()
        async def tracked_tool(value: int) -> int:
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)
            return value * 2
        
        registry.register(tracked_tool)
        executor = ToolExecutor(registry)
        
        results = await executor.execute_many(
            ctx=ctx,
            tool_calls=[
                {"id": "call_1", "name": "tracked_tool", "arguments": {"value": 1}},
                {"id": "call_2", "name": "tracked_tool", "arguments": {"value": 2}},
                {"id": "call_3", "name": "tracked_tool", "arguments": {"value": 3}},
            ],
            parallel=True,
        )
        
        assert len(results) == 3
        assert all(r.success for r in results)
        assert [r.result for r in results] == [2, 4, 6]
        
        time_diff = max(call_times) - min(call_times)
        assert time_diff < 0.05
    
    @pytest.mark.asyncio
    async def test_execute_many_sequential(self, ctx):
        registry = ToolRegistry()
        call_order = []
        
        @tool()
        async def ordered_tool(value: int) -> int:
            call_order.append(value)
            return value
        
        registry.register(ordered_tool)
        executor = ToolExecutor(registry)
        
        results = await executor.execute_many(
            ctx=ctx,
            tool_calls=[
                {"id": "call_1", "name": "ordered_tool", "arguments": {"value": 1}},
                {"id": "call_2", "name": "ordered_tool", "arguments": {"value": 2}},
                {"id": "call_3", "name": "ordered_tool", "arguments": {"value": 3}},
            ],
            parallel=False,
        )
        
        assert call_order == [1, 2, 3]
    
    def test_check_hil_required(self):
        registry = ToolRegistry()
        
        @tool(hil=HILConfig(requires_confirmation=True, confirmation_prompt="Confirm?"))
        def hil_tool(x: int) -> int:
            return x
        
        @tool()
        def normal_tool(x: int) -> int:
            return x
        
        registry.register(hil_tool)
        registry.register(normal_tool)
        executor = ToolExecutor(registry)
        
        requires, prompt = executor.check_hil_required("hil_tool", {})
        assert requires is True
        assert prompt == "Confirm?"
        
        requires, prompt = executor.check_hil_required("normal_tool", {})
        assert requires is False
    
    @pytest.mark.asyncio
    async def test_execute_with_retention(self, ctx):
        registry = ToolRegistry()
        
        @tool(retention=RetentionStrategy(max_items=2))
        async def list_tool(count: int) -> list:
            return list(range(count))
        
        registry.register(list_tool)
        executor = ToolExecutor(registry)
        
        result = await executor.execute(
            ctx=ctx,
            tool_name="list_tool",
            arguments={"count": 10},
            tool_call_id="call_1",
        )
        
        assert result.success is True
        assert result.result == list(range(10))
        assert result.compact_result["items"] == [0, 1]
        assert result.compact_result["truncated"] is True
