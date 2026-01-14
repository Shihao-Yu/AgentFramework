"""Message parser for chat contract protocol."""

from __future__ import annotations

import json
import logging
from typing import Any, Union

from pydantic import ValidationError

from agentcore.transport.models import (
    AuthMessage,
    HumanInputMessage,
    IncomingMessage,
    MessageType,
    QueryMessage,
)

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Error parsing a message."""

    def __init__(self, message: str, raw_data: Any = None):
        super().__init__(message)
        self.raw_data = raw_data


def parse_message(data: Union[str, bytes, dict[str, Any]]) -> IncomingMessage:
    """Parse an incoming WebSocket message.
    
    Accepts JSON string, bytes, or already-parsed dict.
    
    Args:
        data: Raw message data
        
    Returns:
        Parsed message object (AuthMessage, QueryMessage, or HumanInputMessage)
        
    Raises:
        ParseError: If message cannot be parsed
    """
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON: {e}", raw_data=data)
    else:
        parsed = data
    
    if not isinstance(parsed, dict):
        raise ParseError(f"Expected object, got {type(parsed).__name__}", raw_data=data)
    
    msg_type = parsed.get("type")
    if not msg_type:
        raise ParseError("Missing 'type' field", raw_data=parsed)
    
    try:
        if msg_type == MessageType.AUTH.value:
            return AuthMessage.model_validate(parsed)
        elif msg_type == MessageType.QUERY.value:
            return QueryMessage.model_validate(parsed)
        elif msg_type == MessageType.HUMAN_INPUT.value:
            return HumanInputMessage.model_validate(parsed)
        else:
            raise ParseError(f"Unknown message type: {msg_type}", raw_data=parsed)
    except ValidationError as e:
        raise ParseError(f"Validation error for '{msg_type}': {e}", raw_data=parsed)


def serialize_message(message: Any) -> str:
    """Serialize an outgoing message to JSON string.
    
    Args:
        message: Pydantic model to serialize
        
    Returns:
        JSON string
    """
    if hasattr(message, "model_dump_json"):
        return message.model_dump_json(by_alias=True, exclude_none=True)
    elif hasattr(message, "model_dump"):
        return json.dumps(message.model_dump(by_alias=True, exclude_none=True))
    else:
        return json.dumps(message)
