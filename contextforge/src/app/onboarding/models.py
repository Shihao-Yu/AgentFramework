"""
Pydantic models for structured output extraction.

These models are used with InferenceClient.complete_structured() to get
reliable JSON schema adherence from the LLM.
"""

from typing import Optional
from pydantic import BaseModel, Field


# =============================================================================
# FAQ Extraction
# =============================================================================

class FAQExtraction(BaseModel):
    """Structured output for FAQ extraction."""

    question: str = Field(description="The question being answered")
    answer: str = Field(description="The complete answer")
    tags: list[str] = Field(
        default_factory=list,
        description="3-5 relevant tags for categorization",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="Confidence score from 0.0 to 1.0",
    )


# =============================================================================
# Playbook Extraction
# =============================================================================

class PlaybookStep(BaseModel):
    """A single step in a playbook/procedure."""

    order: int = Field(description="Step number (1-based)")
    action: str = Field(description="What to do in this step")
    details: Optional[str] = Field(
        default=None,
        description="Additional details or notes for this step",
    )


class PlaybookExtraction(BaseModel):
    """Structured output for Playbook/Procedure extraction."""

    title: str = Field(description="Procedure title")
    description: str = Field(description="Brief summary of what this procedure accomplishes")
    prerequisites: list[str] = Field(
        default_factory=list,
        description="Prerequisites or requirements before starting",
    )
    steps: list[PlaybookStep] = Field(
        description="Ordered list of steps to complete the procedure",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="3-5 relevant tags for categorization",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="Confidence score from 0.0 to 1.0",
    )


# =============================================================================
# Concept Extraction
# =============================================================================

class ConceptExtraction(BaseModel):
    """Structured output for Concept/Glossary term extraction."""

    term: str = Field(description="The term being defined")
    definition: str = Field(description="Clear, concise definition")
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names, acronyms, or synonyms",
    )
    examples: list[str] = Field(
        default_factory=list,
        description="Usage examples if present in the text",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="3-5 relevant tags for categorization",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="Confidence score from 0.0 to 1.0",
    )


# =============================================================================
# Feature Permission Extraction
# =============================================================================

class PermissionRule(BaseModel):
    """A single permission rule defining who can do what."""

    role: str = Field(description="Role or user group (e.g., 'Buyer', 'Admin')")
    action: str = Field(description="What action they can perform")
    condition: Optional[str] = Field(
        default=None,
        description="Condition or limit (e.g., 'up to $5,000')",
    )


class FeaturePermissionExtraction(BaseModel):
    """Structured output for Feature Permission extraction."""

    feature: str = Field(description="Feature or action this permission controls")
    rules: list[PermissionRule] = Field(
        description="Permission rules defining who can do what",
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="Additional conditions or notes",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="3-5 relevant tags for categorization",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="Confidence score from 0.0 to 1.0",
    )


# =============================================================================
# Entity Extraction
# =============================================================================

class EntityExtraction(BaseModel):
    """Structured output for Entity extraction."""

    name: str = Field(description="Entity name")
    entity_type: str = Field(
        description="Type of entity: Vendor, Product, Department, Customer, etc.",
    )
    attributes: dict[str, str] = Field(
        default_factory=dict,
        description="Key attributes as key-value pairs",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="3-5 relevant tags for categorization",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="Confidence score from 0.0 to 1.0",
    )
