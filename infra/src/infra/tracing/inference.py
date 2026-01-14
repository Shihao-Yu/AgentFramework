"""Traced inference client that automatically logs LLM calls to Langfuse."""

import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Optional, Type, TypeVar

from pydantic import BaseModel

from infra.inference import (
    InferenceClient,
    InferenceConfig,
    InferenceResponse,
    Message,
    ToolDefinition,
)
from infra.tracing.client import TracingClient
from infra.tracing.context import TraceContext

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class TracedInferenceClient:
    """Wrapper around InferenceClient that automatically logs to Langfuse.

    All LLM calls are logged as generations in the active trace context.
    If no trace context is active, calls pass through without logging.

    Example:
        ```python
        tracing = TracingClient()
        inference = InferenceClient()
        client = TracedInferenceClient(inference, tracing)

        # With active trace - logs to Langfuse
        trace_ctx = tracing.start_trace(ctx, "my_agent")
        response = await client.complete([Message.user("Hello")])

        # Without trace - works normally, no logging
        response = await client.complete([Message.user("Hello")])
        ```
    """

    def __init__(
        self,
        client: InferenceClient,
        tracing: TracingClient,
    ):
        self._client = client
        self._tracing = tracing

    async def complete(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        config: Optional[InferenceConfig] = None,
        *,
        generation_name: str = "llm_completion",
        metadata: Optional[dict] = None,
    ) -> InferenceResponse:
        """Complete a chat, logging to Langfuse if trace is active."""
        trace_ctx = TraceContext.current()

        if trace_ctx is None or not self._tracing.enabled:
            return await self._client.complete(messages, tools, config)

        return await self._traced_complete(
            messages=messages,
            tools=tools,
            config=config,
            trace_ctx=trace_ctx,
            generation_name=generation_name,
            metadata=metadata,
        )

    async def _traced_complete(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]],
        config: Optional[InferenceConfig],
        trace_ctx: TraceContext,
        generation_name: str,
        metadata: Optional[dict],
    ) -> InferenceResponse:
        """Execute completion with Langfuse generation logging."""
        config = config or InferenceConfig()
        model = config.model or self._client._model
        start_time = datetime.now(timezone.utc)

        openai_messages = [self._message_to_dict(m) for m in messages]
        model_params = {
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }

        generation = None
        if trace_ctx._trace is not None:
            try:
                parent = trace_ctx.current_span or trace_ctx._trace
                generation = parent.generation(
                    name=generation_name,
                    model=model,
                    input=openai_messages,
                    model_parameters=model_params,
                    metadata=metadata or {},
                )
            except Exception as e:
                logger.warning(f"Failed to create Langfuse generation: {e}")

        try:
            response = await self._client.complete(messages, tools, config)

            if generation is not None:
                try:
                    usage = {
                        "input": response.usage.prompt_tokens,
                        "output": response.usage.completion_tokens,
                    }
                    trace_ctx.record_inference(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                    )
                    generation.end(
                        output=response.content,
                        level="DEFAULT",
                        usage=usage,
                        metadata={
                            **(metadata or {}),
                            "finish_reason": response.finish_reason,
                            "duration_ms": (
                                datetime.now(timezone.utc) - start_time
                            ).total_seconds() * 1000,
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to end Langfuse generation: {e}")

            return response

        except Exception as e:
            if generation is not None:
                try:
                    generation.end(
                        output=str(e),
                        level="ERROR",
                        metadata={
                            **(metadata or {}),
                            "error": str(e),
                            "duration_ms": (
                                datetime.now(timezone.utc) - start_time
                            ).total_seconds() * 1000,
                        },
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to log error to Langfuse: {log_err}")
            raise

    async def complete_structured(
        self,
        messages: list[Message],
        response_model: Type[T],
        config: Optional[InferenceConfig] = None,
        *,
        generation_name: str = "llm_structured",
        metadata: Optional[dict] = None,
    ) -> T:
        """Complete with structured output, logging to Langfuse if trace is active."""
        trace_ctx = TraceContext.current()

        if trace_ctx is None or not self._tracing.enabled:
            return await self._client.complete_structured(messages, response_model, config)

        config = config or InferenceConfig()
        model = config.model or self._client._model
        start_time = datetime.now(timezone.utc)

        openai_messages = [self._message_to_dict(m) for m in messages]
        model_params = {
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "response_model": response_model.__name__,
        }

        generation = None
        if trace_ctx._trace is not None:
            try:
                parent = trace_ctx.current_span or trace_ctx._trace
                generation = parent.generation(
                    name=generation_name,
                    model=model,
                    input=openai_messages,
                    model_parameters=model_params,
                    metadata={
                        **(metadata or {}),
                        "schema": response_model.model_json_schema(),
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to create Langfuse generation: {e}")

        try:
            result = await self._client.complete_structured(messages, response_model, config)

            if generation is not None:
                try:
                    trace_ctx.record_inference()
                    generation.end(
                        output=result.model_dump_json(),
                        level="DEFAULT",
                        metadata={
                            **(metadata or {}),
                            "duration_ms": (
                                datetime.now(timezone.utc) - start_time
                            ).total_seconds() * 1000,
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to end Langfuse generation: {e}")

            return result

        except Exception as e:
            if generation is not None:
                try:
                    generation.end(
                        output=str(e),
                        level="ERROR",
                        metadata={
                            **(metadata or {}),
                            "error": str(e),
                            "duration_ms": (
                                datetime.now(timezone.utc) - start_time
                            ).total_seconds() * 1000,
                        },
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to log error to Langfuse: {log_err}")
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        config: Optional[InferenceConfig] = None,
        *,
        generation_name: str = "llm_stream",
        metadata: Optional[dict] = None,
    ) -> AsyncIterator[str]:
        """Stream completion, logging to Langfuse when complete."""
        trace_ctx = TraceContext.current()

        if trace_ctx is None or not self._tracing.enabled:
            async for chunk in self._client.stream(messages, tools, config):
                yield chunk
            return

        config = config or InferenceConfig()
        model = config.model or self._client._model
        start_time = datetime.now(timezone.utc)

        openai_messages = [self._message_to_dict(m) for m in messages]
        model_params = {
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }

        generation = None
        if trace_ctx._trace is not None:
            try:
                parent = trace_ctx.current_span or trace_ctx._trace
                generation = parent.generation(
                    name=generation_name,
                    model=model,
                    input=openai_messages,
                    model_parameters=model_params,
                    metadata=metadata or {},
                )
            except Exception as e:
                logger.warning(f"Failed to create Langfuse generation: {e}")

        collected_content = []
        error = None

        try:
            async for chunk in self._client.stream(messages, tools, config):
                collected_content.append(chunk)
                yield chunk
        except Exception as e:
            error = e
            raise
        finally:
            if generation is not None:
                try:
                    full_content = "".join(collected_content)
                    trace_ctx.record_inference()
                    generation.end(
                        output=full_content if not error else str(error),
                        level="ERROR" if error else "DEFAULT",
                        metadata={
                            **(metadata or {}),
                            "duration_ms": (
                                datetime.now(timezone.utc) - start_time
                            ).total_seconds() * 1000,
                            **({"error": str(error)} if error else {}),
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to end Langfuse generation: {e}")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[InferenceConfig] = None,
        *,
        generation_name: str = "llm_generate",
        metadata: Optional[dict] = None,
    ) -> str:
        """Generate text from a prompt, logging to Langfuse if trace is active."""
        messages = []
        if system_prompt:
            messages.append(Message.system(system_prompt))
        messages.append(Message.user(prompt))

        response = await self.complete(
            messages, config=config, generation_name=generation_name, metadata=metadata
        )
        return response.content or ""

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[InferenceConfig] = None,
        *,
        generation_name: str = "llm_generate_json",
        metadata: Optional[dict] = None,
    ) -> dict:
        """Generate JSON from a prompt, logging to Langfuse if trace is active."""
        config = config or InferenceConfig()
        config = InferenceConfig(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            response_format={"type": "json_object"},
        )

        messages = []
        base_system = "Respond with valid JSON only."
        if system_prompt:
            messages.append(Message.system(f"{system_prompt}\n\n{base_system}"))
        else:
            messages.append(Message.system(base_system))
        messages.append(Message.user(prompt))

        response = await self.complete(
            messages, config=config, generation_name=generation_name, metadata=metadata
        )

        import json
        return json.loads(response.content or "{}")

    def _message_to_dict(self, message: Message) -> dict:
        """Convert Message to dict for Langfuse logging."""
        return {
            "role": message.role.value,
            "content": message.content,
            **({"name": message.name} if message.name else {}),
            **({"tool_call_id": message.tool_call_id} if message.tool_call_id else {}),
        }

    async def close(self) -> None:
        """Close the underlying client."""
        await self._client.close()

    async def __aenter__(self) -> "TracedInferenceClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
