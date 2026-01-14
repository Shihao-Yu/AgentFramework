"""Message handlers for WebSocket communication."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional, Protocol

from agentcore.auth.context import RequestContext
from agentcore.auth.models import EnrichedUser, Locale as AuthLocale, Permission
from agentcore.transport.models import (
    AuthMessage,
    AuthResponse,
    EnrichedUserInfo,
    ErrorMessage,
    HumanInputMessage,
    MarkdownMessage,
    ProgressMessage,
    QueryMessage,
    SuggestionsMessage,
    UIInteractionMessage,
    UserInfo,
    FormDefinition,
    FormField,
)
from agentcore.transport.parser import serialize_message

if TYPE_CHECKING:
    from agentcore.core.agent import BaseAgent
    from agentcore.core.blackboard import Blackboard

logger = logging.getLogger(__name__)


class AuthProvider(Protocol):
    """Protocol for authentication providers."""
    
    async def authenticate(self, token: str) -> tuple[UserInfo, EnrichedUser]:
        """Authenticate a token and return user info.
        
        Args:
            token: JWT token
            
        Returns:
            Tuple of (raw user info, enriched user)
            
        Raises:
            Exception: If authentication fails
        """
        ...


class MessageHandler:
    """Handles incoming WebSocket messages and produces responses."""

    def __init__(
        self,
        agent: "BaseAgent",
        auth_provider: Optional[AuthProvider] = None,
    ):
        self._agent = agent
        self._auth_provider = auth_provider
        self._authenticated_user: Optional[EnrichedUser] = None
        self._session_blackboards: dict[str, "Blackboard"] = {}

    async def handle_auth(self, message: AuthMessage) -> AsyncIterator[str]:
        """Handle authentication message.
        
        Yields JSON-serialized response messages.
        """
        logger.info("Processing auth message")
        
        if self._auth_provider is None:
            user_info = UserInfo(
                upn="anonymous@local",
                name="Anonymous",
                email="anonymous@local",
            )
            enriched = EnrichedUser.anonymous()
            self._authenticated_user = enriched
            
            enriched_info = self._user_to_enriched_info(enriched)
            yield serialize_message(AuthResponse.success(user_info, enriched_info))
            
            suggestions = await self._get_initial_suggestions()
            if suggestions:
                yield serialize_message(SuggestionsMessage.create(suggestions))
            return
        
        try:
            user_info, enriched = await self._auth_provider.authenticate(message.token)
            self._authenticated_user = enriched
            
            enriched_info = self._user_to_enriched_info(enriched)
            yield serialize_message(AuthResponse.success(user_info, enriched_info))
            
            suggestions = await self._get_initial_suggestions()
            if suggestions:
                yield serialize_message(SuggestionsMessage.create(suggestions))
                
        except Exception as e:
            logger.exception(f"Authentication failed: {e}")
            yield serialize_message(AuthResponse.error(str(e)))

    async def handle_query(self, message: QueryMessage) -> AsyncIterator[str]:
        """Handle query message.
        
        Yields JSON-serialized response messages (progress, markdown, suggestions, etc.)
        """
        logger.info(f"Processing query: {message.query[:50]}...")
        
        if self._authenticated_user is None:
            yield serialize_message(ErrorMessage.auth_error("Not authenticated"))
            return
        
        ctx = self._create_request_context(message)
        
        try:
            async for chunk in self._agent.handle_message(
                ctx=ctx,
                message=message.query,
                attachments=self._convert_attachments(message.attachments),
            ):
                response = self._convert_agent_response(chunk)
                if response:
                    yield response
            
            yield serialize_message(ProgressMessage.complete())
            
        except Exception as e:
            logger.exception(f"Query handling failed: {e}")
            yield serialize_message(ErrorMessage.create(str(e)))

    async def handle_human_input(self, message: HumanInputMessage) -> AsyncIterator[str]:
        """Handle human input (form submission) message.
        
        Yields JSON-serialized response messages.
        """
        logger.info(f"Processing human input for interaction: {message.payload.interaction_id}")
        
        if self._authenticated_user is None:
            yield serialize_message(ErrorMessage.auth_error("Not authenticated"))
            return
        
        session_id = message.payload.session_id
        blackboard = self._session_blackboards.get(session_id)
        
        if blackboard is None:
            yield serialize_message(
                ErrorMessage.create(f"Session not found: {session_id}")
            )
            return
        
        ctx = RequestContext.create(
            user=self._authenticated_user,
            session_id=session_id,
            request_id=message.payload.interaction_id,
        )
        
        try:
            async for chunk in self._agent.handle_human_input(
                ctx=ctx,
                interaction_id=message.payload.interaction_id,
                response=message.payload.values,
                blackboard=blackboard,
            ):
                response = self._convert_agent_response(chunk)
                if response:
                    yield response
            
            yield serialize_message(ProgressMessage.complete())
            
        except Exception as e:
            logger.exception(f"Human input handling failed: {e}")
            yield serialize_message(ErrorMessage.create(str(e)))

    def _create_request_context(self, message: QueryMessage) -> RequestContext:
        """Create RequestContext from query message."""
        locale = AuthLocale(
            timezone=message.locale.location,
            language=message.locale.language,
        )
        
        ctx = RequestContext.create(
            user=self._authenticated_user,
            session_id=message.session_id,
            request_id=message.question_answer_uuid,
            locale=locale,
        )
        
        return ctx

    def _convert_attachments(self, attachments: list) -> list[dict[str, Any]]:
        """Convert attachment models to dicts for agent."""
        return [
            {
                "file_name": a.fileName,
                "size": a.size,
                "mime_type": a.type,
                "reference": a.reference,
            }
            for a in attachments
        ]

    def _convert_agent_response(self, chunk: dict[str, Any]) -> Optional[str]:
        """Convert agent response chunk to chat contract message."""
        chunk_type = chunk.get("type")
        payload = chunk.get("payload")
        
        if chunk_type == "component":
            component = payload.get("component") if isinstance(payload, dict) else None
            if component == "progress":
                status = payload.get("data", {}).get("status", "Processing")
                return serialize_message(ProgressMessage.create(status))
            elif component == "form" or component == "confirm":
                return self._convert_form_response(payload)
        
        elif chunk_type == "markdown":
            content = payload if isinstance(payload, str) else str(payload)
            return serialize_message(MarkdownMessage.create(content))
        
        elif chunk_type == "suggestions":
            options = payload.get("options", []) if isinstance(payload, dict) else []
            return serialize_message(SuggestionsMessage.create(options))
        
        elif chunk_type == "error":
            message = payload.get("message", "Unknown error") if isinstance(payload, dict) else str(payload)
            return serialize_message(ErrorMessage.create(message))
        
        return None

    def _convert_form_response(self, payload: dict[str, Any]) -> Optional[str]:
        """Convert form/confirm response to UIInteractionMessage."""
        data = payload.get("data", {})
        interaction_id = data.get("interaction_id", data.get("id", "unknown"))
        
        form_schema = data.get("form_schema") or data.get("form")
        if form_schema:
            form = FormDefinition(
                id=interaction_id,
                fields=[
                    FormField(
                        key=f.get("key", f.get("name", "")),
                        label=f.get("label", ""),
                        type=f.get("type", "text"),
                        required=f.get("required", False),
                    )
                    for f in form_schema.get("fields", [])
                ] if isinstance(form_schema, dict) else [],
            )
            return serialize_message(
                UIInteractionMessage.create_form(interaction_id, form)
            )
        
        prompt = data.get("prompt", "Please confirm")
        return serialize_message(
            UIInteractionMessage.create_confirm(interaction_id, prompt)
        )

    def _user_to_enriched_info(self, user: EnrichedUser) -> EnrichedUserInfo:
        """Convert EnrichedUser to EnrichedUserInfo for response."""
        return EnrichedUserInfo(
            user_id=user.user_id,
            ad_username=user.username,
            super_user=user.is_super_user,
            enabled=True,
            first_name=user.display_name.split()[0] if user.display_name else "",
            last_name=user.display_name.split()[-1] if user.display_name and " " in user.display_name else "",
            display_name=user.display_name,
            email=user.email,
            department=user.department,
            title=user.title,
            buyer=user.is_buyer,
            planner=user.is_planner,
            permissions=[p.value for p in user.permissions],
        )

    async def _get_initial_suggestions(self) -> list[str]:
        """Get initial suggestions based on agent capabilities."""
        return self._agent.example_queries[:3] if self._agent.example_queries else []

    def store_blackboard(self, session_id: str, blackboard: "Blackboard") -> None:
        """Store blackboard for session (for HIL continuation)."""
        self._session_blackboards[session_id] = blackboard

    def get_blackboard(self, session_id: str) -> Optional["Blackboard"]:
        """Get stored blackboard for session."""
        return self._session_blackboards.get(session_id)

    def clear_blackboard(self, session_id: str) -> None:
        """Clear stored blackboard for session."""
        self._session_blackboards.pop(session_id, None)

    @property
    def is_authenticated(self) -> bool:
        """Check if handler has authenticated user."""
        return self._authenticated_user is not None

    @property
    def authenticated_user(self) -> Optional[EnrichedUser]:
        """Get the authenticated user."""
        return self._authenticated_user
