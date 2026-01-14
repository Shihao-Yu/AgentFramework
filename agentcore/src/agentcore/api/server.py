"""AgentAPI - FastAPI wrapper for BaseAgent."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from agentcore.api.models import HealthResponse, QueryRequest
from agentcore.auth.context import RequestContext
from agentcore.auth.models import EnrichedUser, Locale, Permission
from agentcore.registry.models import AgentInfo
from agentcore.transport.server import WebSocketServer

if TYPE_CHECKING:
    from agentcore.core.agent import BaseAgent
    from agentcore.registry.client import RegistryClient
    from agentcore.registry.heartbeat import HeartbeatManager
    from agentcore.transport.handlers import AuthProvider

logger = logging.getLogger(__name__)


class AgentAPI:
    """FastAPI wrapper that exposes a BaseAgent as HTTP/WebSocket service.
    
    Provides:
    - GET /health - Health check
    - GET /capabilities - Agent registration info
    - POST /api/v1/query - HTTP streaming (SSE) for queries
    - WebSocket /ws - Direct WebSocket connections
    
    Optional:
    - Auto-registration with agent registry on startup
    - Heartbeat to keep agent alive in registry
    - Auto-unregistration on shutdown
    """

    def __init__(
        self,
        agent: "BaseAgent",
        registry: Optional["RegistryClient"] = None,
        auth_provider: Optional["AuthProvider"] = None,
        base_url: Optional[str] = None,
        heartbeat_interval: int = 10,
    ):
        self._agent = agent
        self._registry = registry
        self._auth_provider = auth_provider
        self._base_url = base_url or "http://localhost:8000"
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_manager: Optional["HeartbeatManager"] = None
        
        self._ws_server = WebSocketServer(
            agent=agent,
            auth_provider=auth_provider,
        )
        
        self._app = FastAPI(
            title=agent.name,
            version=agent.version,
            lifespan=self._lifespan,
        )
        self._setup_routes()

    @property
    def app(self) -> FastAPI:
        return self._app

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI) -> AsyncIterator[None]:
        await self._startup()
        try:
            yield
        finally:
            await self._shutdown()

    async def _startup(self) -> None:
        logger.info(f"Starting agent: {self._agent.agent_id}")
        
        if self._registry is not None:
            await self._register()
            await self._start_heartbeat()

    async def _shutdown(self) -> None:
        logger.info(f"Shutting down agent: {self._agent.agent_id}")
        
        await self._ws_server.close_all()
        
        if self._heartbeat_manager is not None:
            await self._heartbeat_manager.stop()
        
        if self._registry is not None:
            await self._unregister()

    async def _register(self) -> None:
        if self._registry is None:
            return
        
        agent_info = self._get_agent_info()
        await self._registry.register(agent_info)
        logger.info(f"Registered agent: {self._agent.agent_id}")

    async def _unregister(self) -> None:
        if self._registry is None:
            return
        
        try:
            await self._registry.unregister(self._agent.agent_id)
            logger.info(f"Unregistered agent: {self._agent.agent_id}")
        except Exception as e:
            logger.warning(f"Failed to unregister agent: {e}")

    async def _start_heartbeat(self) -> None:
        if self._registry is None:
            return
        
        from agentcore.registry.heartbeat import HeartbeatManager
        
        self._heartbeat_manager = HeartbeatManager(
            registry=self._registry,
            agent_id=self._agent.agent_id,
            interval=self._heartbeat_interval,
        )
        await self._heartbeat_manager.start()

    def _get_agent_info(self) -> AgentInfo:
        return AgentInfo(
            agent_id=self._agent.agent_id,
            name=self._agent.name,
            description=self._agent.description,
            version=self._agent.version,
            team=self._agent.team,
            base_url=self._base_url,
            capabilities=self._agent.capabilities,
            domains=self._agent.domains,
            example_queries=self._agent.example_queries,
        )

    def _setup_routes(self) -> None:
        @self._app.get("/health", response_model=HealthResponse)
        async def health() -> HealthResponse:
            return HealthResponse(
                status="healthy",
                agent_id=self._agent.agent_id,
                version=self._agent.version,
            )

        @self._app.get("/capabilities")
        async def capabilities() -> dict[str, Any]:
            return self._get_agent_info().model_dump()

        @self._app.post("/api/v1/query")
        async def query(request: QueryRequest) -> StreamingResponse:
            return StreamingResponse(
                self._handle_query(request),
                media_type="text/event-stream",
            )

        @self._app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            await self._ws_server.handle_connection(websocket)

    async def _handle_query(self, request: QueryRequest) -> AsyncIterator[str]:
        ctx = self._create_request_context(request)
        
        try:
            async for chunk in self._agent.handle_message(
                ctx=ctx,
                message=request.query,
                attachments=request.attachments,
            ):
                event_data = self._format_sse_event(chunk)
                yield event_data
            
            yield self._format_sse_event({"type": "done", "payload": None})
            
        except Exception as e:
            logger.exception(f"Query handling failed: {e}")
            yield self._format_sse_event({
                "type": "error",
                "payload": {"message": str(e)},
            })

    def _create_request_context(self, request: QueryRequest) -> RequestContext:
        permissions = frozenset(
            Permission(p) for p in request.context.permissions
            if p in [e.value for e in Permission]
        )
        
        user = EnrichedUser(
            user_id=request.context.user_id,
            username=request.context.username,
            email=request.context.email,
            display_name=request.context.display_name,
            permissions=permissions,
            is_admin=request.context.is_admin,
            is_buyer=request.context.is_buyer,
            is_planner=request.context.is_planner,
            entity_id=request.context.entity_id or 0,
            entity_name=request.context.entity_name or "",
        )
        
        locale = Locale(
            timezone=request.locale.timezone,
            language=request.locale.language,
        )
        
        return RequestContext.create(
            user=user,
            session_id=request.session_id,
            request_id=request.request_id or str(uuid4()),
            locale=locale,
        )

    def _format_sse_event(self, data: dict[str, Any]) -> str:
        return f"data: {json.dumps(data)}\n\n"
