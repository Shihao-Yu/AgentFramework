"""Request/response models for Agent API."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class QueryLocale(BaseModel):
    timezone: str = "UTC"
    language: str = "en-US"


class QueryContext(BaseModel):
    user_id: int
    username: str = ""
    email: str = ""
    display_name: str = ""
    permissions: list[str] = Field(default_factory=list)
    is_admin: bool = False
    is_buyer: bool = False
    is_planner: bool = False
    entity_id: Optional[int] = None
    entity_name: Optional[str] = None


class QueryRequest(BaseModel):
    query: str
    session_id: str
    request_id: Optional[str] = None
    context: QueryContext
    locale: QueryLocale = Field(default_factory=QueryLocale)
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "healthy"
    agent_id: str
    version: str = "1.0.0"
