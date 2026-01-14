import pytest
from unittest.mock import AsyncMock, MagicMock

from pydantic import BaseModel

from infra.inference import InferenceClient, InferenceResponse, Message, InferenceConfig
from infra.inference.models import TokenUsage
from infra.tracing import TracingClient, TracedInferenceClient, TraceContext


class TestTracedInferenceClient:

    @pytest.fixture
    def mock_inference_client(self):
        client = MagicMock(spec=InferenceClient)
        client._model = "gpt-4o-mini"
        client.complete = AsyncMock(
            return_value=InferenceResponse(
                content="Hello!",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )
        )
        client.stream = AsyncMock()
        return client

    @pytest.fixture
    def mock_tracing_client(self):
        client = MagicMock(spec=TracingClient)
        client.enabled = True
        return client

    @pytest.fixture
    def traced_client(self, mock_inference_client, mock_tracing_client):
        return TracedInferenceClient(mock_inference_client, mock_tracing_client)

    @pytest.mark.asyncio
    async def test_complete_without_trace_context(self, traced_client, mock_inference_client):
        response = await traced_client.complete([Message.user("Hi")])

        assert response.content == "Hello!"
        mock_inference_client.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_complete_with_trace_context_creates_generation(
        self, traced_client, mock_inference_client
    ):
        mock_trace = MagicMock()
        mock_generation = MagicMock()
        mock_trace.generation = MagicMock(return_value=mock_generation)

        trace_ctx = TraceContext.create(
            session_id="sess-1",
            user_id="user-1",
        )
        trace_ctx._trace = mock_trace

        try:
            response = await traced_client.complete(
                [Message.user("Test")],
                generation_name="test_gen",
            )

            assert response.content == "Hello!"
            mock_trace.generation.assert_called_once()
            mock_generation.end.assert_called_once()
        finally:
            trace_ctx.clear()

    @pytest.mark.asyncio
    async def test_complete_records_token_usage(self, traced_client, mock_inference_client):
        mock_trace = MagicMock()
        mock_generation = MagicMock()
        mock_trace.generation = MagicMock(return_value=mock_generation)

        trace_ctx = TraceContext.create(
            session_id="sess-1",
            user_id="user-1",
        )
        trace_ctx._trace = mock_trace

        try:
            await traced_client.complete([Message.user("Test")])

            assert trace_ctx.total_input_tokens == 10
            assert trace_ctx.total_output_tokens == 5
            assert trace_ctx.inference_calls == 1
        finally:
            trace_ctx.clear()

    @pytest.mark.asyncio
    async def test_complete_structured_without_trace(
        self, traced_client, mock_inference_client
    ):
        class Output(BaseModel):
            value: str

        mock_inference_client.complete_structured = AsyncMock(
            return_value=Output(value="test")
        )

        result = await traced_client.complete_structured(
            [Message.user("Get value")],
            response_model=Output,
        )

        assert result.value == "test"
        mock_inference_client.complete_structured.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_delegates_correctly(self, traced_client):
        result = await traced_client.generate("Hello", system_prompt="Be helpful")

        assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_tracing_disabled_skips_logging(
        self, mock_inference_client, mock_tracing_client
    ):
        mock_tracing_client.enabled = False
        traced_client = TracedInferenceClient(mock_inference_client, mock_tracing_client)

        mock_trace = MagicMock()
        trace_ctx = TraceContext.create(session_id="s", user_id="u")
        trace_ctx._trace = mock_trace

        try:
            await traced_client.complete([Message.user("Hi")])
            mock_trace.generation.assert_not_called()
        finally:
            trace_ctx.clear()
