"""WebSocket server for chat contract communication."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Optional
from uuid import uuid4

from agentcore.transport.models import (
    AuthMessage,
    ErrorMessage,
    HumanInputMessage,
    QueryMessage,
)
from agentcore.transport.parser import ParseError, parse_message, serialize_message
from agentcore.transport.handlers import MessageHandler

if TYPE_CHECKING:
    from fastapi import WebSocket
    from agentcore.core.agent import BaseAgent
    from agentcore.transport.handlers import AuthProvider

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    """WebSocket connection states."""
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    DISCONNECTED = "disconnected"


@dataclass
class Connection:
    """Represents an active WebSocket connection."""
    id: str
    websocket: "WebSocket"
    state: ConnectionState = ConnectionState.CONNECTING
    handler: Optional[MessageHandler] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)


class WebSocketServer:
    """WebSocket server implementing the chat contract protocol.
    
    Usage with FastAPI:
        ```python
        from fastapi import FastAPI, WebSocket
        from agentcore.transport import WebSocketServer
        
        app = FastAPI()
        ws_server = WebSocketServer(agent=my_agent)
        
        @app.websocket("/ws/chat")
        async def websocket_endpoint(websocket: WebSocket):
            await ws_server.handle_connection(websocket)
        ```
    """

    def __init__(
        self,
        agent: "BaseAgent",
        auth_provider: Optional["AuthProvider"] = None,
        auth_timeout: float = 30.0,
        idle_timeout: float = 300.0,
        max_connections: int = 100,
    ):
        """Initialize the WebSocket server.
        
        Args:
            agent: The agent to handle queries
            auth_provider: Optional authentication provider
            auth_timeout: Timeout for authentication (seconds)
            idle_timeout: Timeout for idle connections (seconds)
            max_connections: Maximum concurrent connections
        """
        self._agent = agent
        self._auth_provider = auth_provider
        self._auth_timeout = auth_timeout
        self._idle_timeout = idle_timeout
        self._max_connections = max_connections
        self._connections: dict[str, Connection] = {}
        self._on_connect: Optional[Callable[[Connection], None]] = None
        self._on_disconnect: Optional[Callable[[Connection], None]] = None

    async def handle_connection(self, websocket: "WebSocket") -> None:
        """Handle a WebSocket connection lifecycle.
        
        Args:
            websocket: FastAPI WebSocket instance
        """
        if len(self._connections) >= self._max_connections:
            await websocket.close(code=1013, reason="Server at capacity")
            return
        
        await websocket.accept()
        
        connection = Connection(
            id=str(uuid4()),
            websocket=websocket,
            state=ConnectionState.CONNECTING,
            handler=MessageHandler(
                agent=self._agent,
                auth_provider=self._auth_provider,
            ),
        )
        self._connections[connection.id] = connection
        
        logger.info(f"New connection: {connection.id}")
        
        if self._on_connect:
            self._on_connect(connection)
        
        try:
            connection.state = ConnectionState.AUTHENTICATING
            
            auth_success = await self._wait_for_auth(connection)
            if not auth_success:
                await self._send_error(connection, "Authentication timeout")
                return
            
            connection.state = ConnectionState.AUTHENTICATED
            
            await self._message_loop(connection)
            
        except Exception as e:
            logger.exception(f"Connection error {connection.id}: {e}")
        finally:
            await self._cleanup_connection(connection)

    async def _wait_for_auth(self, connection: Connection) -> bool:
        """Wait for authentication message.
        
        Returns True if authenticated successfully within timeout.
        """
        try:
            async with asyncio.timeout(self._auth_timeout):
                while True:
                    data = await connection.websocket.receive_text()
                    connection.update_activity()
                    
                    try:
                        message = parse_message(data)
                    except ParseError as e:
                        logger.warning(f"Parse error during auth: {e}")
                        await self._send_error(connection, str(e))
                        continue
                    
                    if isinstance(message, AuthMessage):
                        async for response in connection.handler.handle_auth(message):
                            await connection.websocket.send_text(response)
                        return connection.handler.is_authenticated
                    else:
                        await self._send_error(
                            connection,
                            "Expected auth message first"
                        )
        except asyncio.TimeoutError:
            logger.warning(f"Auth timeout for connection {connection.id}")
            return False
        except Exception as e:
            logger.exception(f"Auth error for connection {connection.id}: {e}")
            return False

    async def _message_loop(self, connection: Connection) -> None:
        """Main message processing loop."""
        while True:
            try:
                async with asyncio.timeout(self._idle_timeout):
                    data = await connection.websocket.receive_text()
            except asyncio.TimeoutError:
                logger.info(f"Idle timeout for connection {connection.id}")
                break
            except Exception as e:
                logger.debug(f"Connection {connection.id} closed: {e}")
                break
            
            connection.update_activity()
            
            try:
                message = parse_message(data)
            except ParseError as e:
                logger.warning(f"Parse error: {e}")
                await self._send_error(connection, str(e))
                continue
            
            try:
                if isinstance(message, AuthMessage):
                    async for response in connection.handler.handle_auth(message):
                        await connection.websocket.send_text(response)
                
                elif isinstance(message, QueryMessage):
                    connection.session_id = message.session_id
                    async for response in connection.handler.handle_query(message):
                        await connection.websocket.send_text(response)
                
                elif isinstance(message, HumanInputMessage):
                    async for response in connection.handler.handle_human_input(message):
                        await connection.websocket.send_text(response)
                
                else:
                    await self._send_error(
                        connection,
                        f"Unhandled message type: {type(message).__name__}"
                    )
                    
            except Exception as e:
                logger.exception(f"Handler error: {e}")
                await self._send_error(connection, str(e))

    async def _send_error(self, connection: Connection, message: str) -> None:
        """Send error message to connection."""
        try:
            error = ErrorMessage.create(message)
            await connection.websocket.send_text(serialize_message(error))
        except Exception as e:
            logger.warning(f"Failed to send error: {e}")

    async def _cleanup_connection(self, connection: Connection) -> None:
        """Clean up connection resources."""
        connection.state = ConnectionState.DISCONNECTED
        self._connections.pop(connection.id, None)
        
        if connection.session_id and connection.handler:
            connection.handler.clear_blackboard(connection.session_id)
        
        logger.info(f"Connection closed: {connection.id}")
        
        if self._on_disconnect:
            self._on_disconnect(connection)
        
        try:
            await connection.websocket.close()
        except Exception:
            pass

    def on_connect(self, callback: Callable[[Connection], None]) -> None:
        """Register callback for new connections."""
        self._on_connect = callback

    def on_disconnect(self, callback: Callable[[Connection], None]) -> None:
        """Register callback for disconnections."""
        self._on_disconnect = callback

    @property
    def connection_count(self) -> int:
        """Get current connection count."""
        return len(self._connections)

    @property
    def connections(self) -> list[Connection]:
        """Get all active connections."""
        return list(self._connections.values())

    def get_connection(self, connection_id: str) -> Optional[Connection]:
        """Get connection by ID."""
        return self._connections.get(connection_id)

    async def broadcast(self, message: str) -> int:
        """Broadcast message to all authenticated connections.
        
        Returns number of connections that received the message.
        """
        count = 0
        for conn in self._connections.values():
            if conn.state == ConnectionState.AUTHENTICATED:
                try:
                    await conn.websocket.send_text(message)
                    count += 1
                except Exception as e:
                    logger.warning(f"Broadcast failed for {conn.id}: {e}")
        return count

    async def close_all(self) -> None:
        """Close all connections."""
        for conn in list(self._connections.values()):
            await self._cleanup_connection(conn)
