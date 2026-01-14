import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel

from infra.inference import Message, MessageRole, ToolCall, ToolDefinition, InferenceConfig, InferenceResponse
from infra.inference.client import InferenceClient
from infra.inference.models import TokenUsage


class TestMessage:
    def test_system(self):
        msg = Message.system("You are helpful")
        assert msg.role == MessageRole.SYSTEM
        assert msg.content == "You are helpful"

    def test_user(self):
        msg = Message.user("Hello!")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"

    def test_assistant(self):
        msg = Message.assistant("Hi there!")
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Hi there!"

    def test_assistant_with_tool_calls(self):
        tool_call = ToolCall(id="1", name="search", arguments={"query": "test"})
        msg = Message.assistant(tool_calls=[tool_call])
        assert msg.role == MessageRole.ASSISTANT
        assert msg.tool_calls == [tool_call]

    def test_tool(self):
        msg = Message.tool("call_1", "Result here")
        assert msg.role == MessageRole.TOOL
        assert msg.tool_call_id == "call_1"
        assert msg.content == "Result here"


class TestToolCall:
    def test_create(self):
        tc = ToolCall(id="abc", name="search", arguments={"q": "test"})
        assert tc.id == "abc"
        assert tc.name == "search"
        assert tc.arguments == {"q": "test"}


class TestToolDefinition:
    def test_to_openai_format(self):
        tool = ToolDefinition(
            name="search",
            description="Search for something",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        )
        result = tool.to_openai_format()
        assert result["type"] == "function"
        assert result["function"]["name"] == "search"
        assert result["function"]["description"] == "Search for something"


class TestInferenceConfig:
    def test_defaults(self):
        config = InferenceConfig()
        assert config.temperature == 0.7
        assert config.model is None
        assert config.max_tokens is None

    def test_custom(self):
        config = InferenceConfig(model="gpt-4", temperature=0.0, max_tokens=100)
        assert config.model == "gpt-4"
        assert config.temperature == 0.0
        assert config.max_tokens == 100


class TestInferenceResponse:
    def test_content(self):
        response = InferenceResponse(content="Hello!")
        assert response.content == "Hello!"
        assert response.has_tool_calls is False

    def test_tool_calls(self):
        tc = ToolCall(id="1", name="fn", arguments={})
        response = InferenceResponse(tool_calls=[tc])
        assert response.has_tool_calls is True

    def test_to_message(self):
        response = InferenceResponse(content="Response text")
        msg = response.to_message()
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Response text"

    def test_usage(self):
        response = InferenceResponse(
            content="Hi",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        assert response.usage.prompt_tokens == 10
        assert response.usage.completion_tokens == 5
        assert response.usage.total_tokens == 15


class TestInferenceClientStructured:
    """Tests for complete_structured method."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        return mock_client

    @pytest.fixture
    def client(self, mock_openai_client):
        """Create InferenceClient with mocked OpenAI."""
        client = InferenceClient(api_key="test-key")
        client._client = mock_openai_client
        return client

    @pytest.mark.asyncio
    async def test_complete_structured_returns_model(self, client, mock_openai_client):
        """Test that complete_structured returns a validated Pydantic model."""

        class TestResponse(BaseModel):
            name: str
            age: int

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"name": "Alice", "age": 30}'))
        ]
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await client.complete_structured(
            messages=[Message.user("Get info")],
            response_model=TestResponse,
        )

        assert isinstance(result, TestResponse)
        assert result.name == "Alice"
        assert result.age == 30

    @pytest.mark.asyncio
    async def test_complete_structured_uses_json_schema(self, client, mock_openai_client):
        """Test that complete_structured passes correct response_format."""

        class Classification(BaseModel):
            category: str
            confidence: float

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"category": "tech", "confidence": 0.95}'))
        ]
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        await client.complete_structured(
            messages=[Message.user("Classify")],
            response_model=Classification,
        )

        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"]["type"] == "json_schema"
        assert call_kwargs["response_format"]["json_schema"]["name"] == "Classification"
        assert call_kwargs["response_format"]["json_schema"]["strict"] is True

    @pytest.mark.asyncio
    async def test_complete_structured_with_config(self, client, mock_openai_client):
        """Test that config options are passed through."""

        class Output(BaseModel):
            value: str

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"value": "test"}'))
        ]
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        config = InferenceConfig(model="gpt-4", temperature=0.0, max_tokens=100)
        await client.complete_structured(
            messages=[Message.user("Generate")],
            response_model=Output,
            config=config,
        )

        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["max_tokens"] == 100
