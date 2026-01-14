"""Session models for AgentCore."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agentcore.inference import MessageRole


class MessageData(BaseModel):
    """Data for a single message in a session."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    role: MessageRole
    content: Optional[str] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI message format."""
        msg: dict[str, Any] = {"role": self.role.value}
        
        if self.content is not None:
            msg["content"] = self.content
        
        if self.name is not None:
            msg["name"] = self.name
        
        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id
        
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        
        return msg


class Session(BaseModel):
    """Session representing a conversation with an agent."""

    model_config = ConfigDict(frozen=False)

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: int
    agent_type: str
    state: dict[str, Any] = Field(default_factory=dict)
    blackboard_data: dict[str, Any] = Field(default_factory=dict)
    messages: list[MessageData] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    def add_message(self, message: MessageData) -> None:
        """Add a message to the session."""
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)

    def get_messages(
        self,
        limit: Optional[int] = None,
        roles: Optional[list[MessageRole]] = None,
    ) -> list[MessageData]:
        """Get messages with optional filtering."""
        msgs = self.messages
        
        if roles:
            msgs = [m for m in msgs if m.role in roles]
        
        if limit:
            msgs = msgs[-limit:]
        
        return msgs

    def get_openai_messages(
        self,
        limit: Optional[int] = None,
        include_system: bool = True,
    ) -> list[dict[str, Any]]:
        """Get messages in OpenAI format."""
        msgs = self.messages
        
        if not include_system:
            msgs = [m for m in msgs if m.role != MessageRole.SYSTEM]
        
        if limit:
            msgs = msgs[-limit:]
        
        return [m.to_openai_format() for m in msgs]

    def clear_messages(self) -> None:
        """Clear all messages."""
        self.messages = []
        self.updated_at = datetime.now(timezone.utc)

    def set_state(self, key: str, value: Any) -> None:
        """Set a state value."""
        self.state[key] = value
        self.updated_at = datetime.now(timezone.utc)

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        return self.state.get(key, default)

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def message_count(self) -> int:
        """Get number of messages."""
        return len(self.messages)

    @property
    def duration_seconds(self) -> float:
        """Get session duration in seconds."""
        return (self.updated_at - self.created_at).total_seconds()


class Checkpoint(BaseModel):
    """Checkpoint for session state recovery."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    thread_id: str
    checkpoint_id: str
    parent_checkpoint_id: Optional[str] = None
    state: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
