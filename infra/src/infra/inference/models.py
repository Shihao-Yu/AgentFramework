from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    arguments: dict[str, Any]

    def to_openai_format(self) -> dict:
        import json
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments),
            },
        }


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: MessageRole
    content: Optional[str] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(
        cls, content: Optional[str] = None, tool_calls: Optional[list[ToolCall]] = None
    ) -> "Message":
        return cls(role=MessageRole.ASSISTANT, content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, tool_call_id: str, content: str, name: Optional[str] = None) -> "Message":
        return cls(role=MessageRole.TOOL, content=content, tool_call_id=tool_call_id, name=name)

    def to_openai_format(self) -> dict:
        msg: dict[str, Any] = {"role": self.role.value}

        if self.content is not None:
            msg["content"] = self.content

        if self.name is not None:
            msg["name"] = self.name

        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id

        if self.tool_calls:
            msg["tool_calls"] = [tc.to_openai_format() for tc in self.tool_calls]

        return msg


class ToolDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai_format(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class InferenceConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    stop: Optional[list[str]] = None
    response_format: Optional[dict] = None


class TokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class InferenceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    finish_reason: str = "stop"
    model: str = ""
    usage: TokenUsage = TokenUsage()

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    @property
    def prompt_tokens(self) -> int:
        return self.usage.prompt_tokens

    @property
    def completion_tokens(self) -> int:
        return self.usage.completion_tokens

    @property
    def total_tokens(self) -> int:
        return self.usage.total_tokens

    def to_message(self) -> Message:
        return Message.assistant(content=self.content, tool_calls=self.tool_calls)
