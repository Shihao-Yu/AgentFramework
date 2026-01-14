import json
import os
from typing import AsyncIterator, Optional, Type, TypeVar

from pydantic import BaseModel

from infra.inference.models import (
    Message,
    ToolCall,
    ToolDefinition,
    InferenceConfig,
    InferenceResponse,
    TokenUsage,
)
from infra.settings.ssl import get_ssl_settings

T = TypeVar("T", bound=BaseModel)


class InferenceClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: float = 120.0,
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = base_url or os.environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
        self._model = model
        self._timeout = timeout
        self._client = None
        self._http_client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError("openai package required. Install with: pip install openai")

            try:
                import httpx
            except ImportError:
                raise ImportError("httpx package required. Install with: pip install httpx")

            ssl_settings = get_ssl_settings()
            ca_cert = ssl_settings.get_ca_cert()

            self._http_client = httpx.AsyncClient(verify=ca_cert)
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
                http_client=self._http_client,
            )
        return self._client

    async def complete(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        config: Optional[InferenceConfig] = None,
    ) -> InferenceResponse:
        config = config or InferenceConfig()
        client = self._get_client()

        openai_messages = [self._to_openai_message(m) for m in messages]

        kwargs: dict = {
            "model": config.model or self._model,
            "messages": openai_messages,
            "temperature": config.temperature,
        }

        if config.max_tokens:
            kwargs["max_tokens"] = config.max_tokens

        if tools:
            kwargs["tools"] = [t.to_openai_format() for t in tools]

        if config.response_format:
            kwargs["response_format"] = config.response_format

        if config.stop:
            kwargs["stop"] = config.stop

        response = await client.chat.completions.create(**kwargs)
        return self._parse_response(response)

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        config: Optional[InferenceConfig] = None,
    ) -> AsyncIterator[str]:
        config = config or InferenceConfig()
        client = self._get_client()

        openai_messages = [self._to_openai_message(m) for m in messages]

        kwargs: dict = {
            "model": config.model or self._model,
            "messages": openai_messages,
            "temperature": config.temperature,
            "stream": True,
        }

        if config.max_tokens:
            kwargs["max_tokens"] = config.max_tokens

        if tools:
            kwargs["tools"] = [t.to_openai_format() for t in tools]

        if config.stop:
            kwargs["stop"] = config.stop

        stream = await client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[InferenceConfig] = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append(Message.system(system_prompt))
        messages.append(Message.user(prompt))

        response = await self.complete(messages, config=config)
        return response.content or ""

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[InferenceConfig] = None,
    ) -> dict:
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

        response = await self.complete(messages, config=config)
        return json.loads(response.content or "{}")

    async def complete_structured(
        self,
        messages: list[Message],
        response_model: Type[T],
        config: Optional[InferenceConfig] = None,
    ) -> T:
        """Complete a chat with structured output parsed into a Pydantic model.

        Uses OpenAI's structured output feature for reliable JSON schema adherence.

        Args:
            messages: List of messages for the conversation.
            response_model: Pydantic model class to parse the response into.
            config: Optional inference configuration.

        Returns:
            Parsed Pydantic model instance.
        """
        config = config or InferenceConfig()
        client = self._get_client()

        openai_messages = [self._to_openai_message(m) for m in messages]

        kwargs: dict = {
            "model": config.model or self._model,
            "messages": openai_messages,
            "temperature": config.temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            },
        }

        if config.max_tokens:
            kwargs["max_tokens"] = config.max_tokens

        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or "{}"
        return response_model.model_validate_json(content)

    def _to_openai_message(self, message: Message) -> dict:
        msg: dict = {"role": message.role.value}

        if message.content is not None:
            msg["content"] = message.content

        if message.name is not None:
            msg["name"] = message.name

        if message.tool_call_id is not None:
            msg["tool_call_id"] = message.tool_call_id

        if message.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in message.tool_calls
            ]

        return msg

    def _parse_response(self, response) -> InferenceResponse:
        choice = response.choices[0]
        message = choice.message

        tool_calls = None
        if message.tool_calls:
            tool_calls = []
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, arguments=args)
                )

        usage = TokenUsage(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            total_tokens=response.usage.total_tokens if response.usage else 0,
        )

        return InferenceResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            model=response.model,
            usage=usage,
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> "InferenceClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
