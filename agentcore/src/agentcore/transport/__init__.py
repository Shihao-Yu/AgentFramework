"""Transport module for WebSocket communication.

This module implements the chat_contract protocol for real-time
communication between UI and Agent via WebSocket.
"""

from agentcore.transport.models import (
    MessageType,
    AuthMessage,
    QueryMessage,
    HumanInputMessage,
    AuthResponse,
    SuggestionsMessage,
    ProgressMessage,
    UIInteractionMessage,
    UIFieldOptionsMessage,
    MarkdownMessage,
    ErrorMessage,
    Locale,
    UserAgent,
    Attachment,
    FormField,
    FormDefinition,
    TableColumn,
    TableRow,
    SuggestionOption,
)
from agentcore.transport.parser import parse_message, ParseError
from agentcore.transport.server import WebSocketServer, ConnectionState
from agentcore.transport.handlers import MessageHandler

__all__ = [
    # Message Types
    "MessageType",
    # UI -> Agent Messages
    "AuthMessage",
    "QueryMessage",
    "HumanInputMessage",
    # Agent -> UI Messages
    "AuthResponse",
    "SuggestionsMessage",
    "ProgressMessage",
    "UIInteractionMessage",
    "UIFieldOptionsMessage",
    "MarkdownMessage",
    "ErrorMessage",
    # Supporting Models
    "Locale",
    "UserAgent",
    "Attachment",
    "FormField",
    "FormDefinition",
    "TableColumn",
    "TableRow",
    "SuggestionOption",
    # Parser
    "parse_message",
    "ParseError",
    # Server
    "WebSocketServer",
    "ConnectionState",
    # Handlers
    "MessageHandler",
]
