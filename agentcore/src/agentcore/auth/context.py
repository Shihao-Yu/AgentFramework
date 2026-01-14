"""Request context with contextvars support."""

import uuid
from contextvars import ContextVar
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from agentcore.auth.models import EnrichedUser, Locale, EntityContext, PageContext


_request_context: ContextVar[Optional["RequestContext"]] = ContextVar(
    "request_context", default=None
)


class RequestContext(BaseModel):
    """Request-scoped context carrying user info and request metadata."""

    model_config = ConfigDict(frozen=True)

    user: EnrichedUser
    session_id: str
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    locale: Locale = Field(default_factory=Locale)
    entity: Optional[EntityContext] = None
    page: Optional[PageContext] = None
    extra: dict[str, Any] = Field(default_factory=dict)

    def set_current(self) -> None:
        """Set this context as the current request context."""
        _request_context.set(self)

    @classmethod
    def current(cls) -> Optional["RequestContext"]:
        """Get the current request context, or None if not set."""
        return _request_context.get()

    @classmethod
    def require_current(cls) -> "RequestContext":
        """Get the current request context, raising if not set.
        
        Raises:
            RuntimeError: If no request context is set
        """
        ctx = _request_context.get()
        if ctx is None:
            raise RuntimeError("No request context set. Call ctx.set_current() first.")
        return ctx

    @classmethod
    def clear_current(cls) -> None:
        """Clear the current request context."""
        _request_context.set(None)

    def with_extra(self, **kwargs: Any) -> "RequestContext":
        """Create a new context with additional extra data.
        
        Args:
            **kwargs: Extra data to add
            
        Returns:
            New RequestContext with merged extra data
        """
        new_extra = {**self.extra, **kwargs}
        return self.model_copy(update={"extra": new_extra})

    def with_page(self, page: PageContext) -> "RequestContext":
        """Create a new context with different page context."""
        return self.model_copy(update={"page": page})

    @classmethod
    def create(
        cls,
        user: EnrichedUser,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        locale: Optional[Locale] = None,
        entity: Optional[EntityContext] = None,
        page: Optional[PageContext] = None,
        **extra: Any,
    ) -> "RequestContext":
        """Create a new request context with defaults.
        
        Args:
            user: Authenticated user
            session_id: Session ID (generated if not provided)
            request_id: Request ID (generated if not provided)
            locale: User locale settings
            entity: Entity context
            page: Page context
            **extra: Additional metadata
            
        Returns:
            New RequestContext
        """
        return cls(
            user=user,
            session_id=session_id or str(uuid.uuid4()),
            request_id=request_id or str(uuid.uuid4()),
            locale=locale or Locale(),
            entity=entity,
            page=page,
            extra=extra,
        )

    @classmethod
    def for_system(cls, session_id: Optional[str] = None) -> "RequestContext":
        """Create a context for system/internal operations."""
        return cls.create(
            user=EnrichedUser.system(),
            session_id=session_id or "system",
        )

    @classmethod
    def for_anonymous(cls, session_id: Optional[str] = None) -> "RequestContext":
        """Create a context for anonymous operations."""
        return cls.create(
            user=EnrichedUser.anonymous(),
            session_id=session_id,
        )
