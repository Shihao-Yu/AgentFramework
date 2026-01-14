"""
API schemas for the onboarding endpoints.
"""

from typing import Literal
from pydantic import BaseModel, Field


# Supported node types for onboarding
NodeType = Literal["FAQ", "PLAYBOOK", "CONCEPT", "FEATURE_PERMISSION", "ENTITY"]


class ContentItem(BaseModel):
    """A single content item to be processed by onboarding pipelines."""

    text: str = Field(
        description="The raw text content to extract knowledge from",
        min_length=10,
    )
    node_types: list[NodeType] = Field(
        description="Node types to attempt extraction for",
        min_length=1,
    )


class OnboardRequest(BaseModel):
    """Request to onboard knowledge from raw text."""

    items: list[ContentItem] = Field(
        description="List of content items to process",
        min_length=1,
    )
    tenant_id: str = Field(
        description="Tenant ID to create staging nodes under",
    )
    source_tag: str = Field(
        default="",
        description="Free-form source tag (e.g., 'confluence-import', 'manual')",
    )


class OnboardResponse(BaseModel):
    """Response from the onboard endpoint."""

    created: int = Field(
        description="Number of staging nodes created",
    )
    staging_ids: list[int] = Field(
        description="IDs of created staging nodes",
    )


class OnboardItemResult(BaseModel):
    """Result for a single extracted item (used in detailed response if needed)."""

    node_type: str
    title: str
    confidence: float
    staging_id: int
