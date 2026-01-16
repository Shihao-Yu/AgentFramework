"""
LLM Context API schemas for agent-optimized context retrieval.

Provides hierarchical, LLM-native structured output for:
- Knowledge context (FAQ, playbook, permissions, concepts)
- Schema context (fields, examples for query generation)
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

from app.models.enums import NodeType


class LLMContextRequest(BaseModel):
    """
    Request schema for LLM-optimized context retrieval.
    
    Supports two main modes:
    - Knowledge mode: FAQ, playbook, permissions, concepts
    - Schema mode: Dataset fields, examples for query generation
    
    Both can be combined in a single request.
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language query to find relevant context",
    )
    tenant_ids: List[str] = Field(
        default_factory=list,
        description="Tenant IDs to search (empty = user's accessible tenants)",
    )
    
    include_knowledge: bool = Field(
        default=True,
        description="Include FAQ, playbook, permissions, concepts",
    )
    include_schema: bool = Field(
        default=False,
        description="Include dataset schema fields and examples",
    )
    
    knowledge_types: Optional[List[NodeType]] = Field(
        default=None,
        description="Filter knowledge by types (None = faq, playbook, permission_rule, concept)",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags (AND logic)",
    )
    
    dataset_names: Optional[List[str]] = Field(
        default=None,
        description="Filter schema to specific datasets (None = all)",
    )
    
    search_method: Literal["hybrid", "bm25", "vector"] = Field(
        default="hybrid",
        description="Search method: hybrid (default), bm25 (keyword), or vector (semantic)",
    )
    
    expand_graph: bool = Field(
        default=True,
        description="Expand to related nodes via graph traversal",
    )
    max_depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum graph traversal depth",
    )
    
    max_knowledge_items: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum knowledge items to return",
    )
    max_schema_fields: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Maximum schema fields to return",
    )
    max_examples: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Maximum Q&A examples to return",
    )


class FAQItem(BaseModel):
    """FAQ item in LLM-friendly format."""
    id: int
    question: str
    answer: str
    tags: List[str] = Field(default_factory=list)
    score: float
    
    
class PlaybookItem(BaseModel):
    """Playbook item in LLM-friendly format."""
    id: int
    title: str
    domain: Optional[str] = None
    summary: Optional[str] = None
    content: str
    tags: List[str] = Field(default_factory=list)
    score: float


class PermissionItem(BaseModel):
    """Permission rule in LLM-friendly format."""
    id: int
    title: str
    feature: Optional[str] = None
    description: str
    permissions: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    conditions: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    score: float


class ConceptItem(BaseModel):
    """Business concept in LLM-friendly format."""
    id: int
    name: str
    description: str
    aliases: List[str] = Field(default_factory=list)
    related_questions: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    score: float


class KnowledgeGroup(BaseModel):
    """
    Group of related knowledge items under a topic/concept.
    
    Provides hierarchical organization for LLM comprehension.
    """
    topic: str = Field(description="Topic or concept name grouping these items")
    relevance_score: float = Field(description="How relevant this group is to the query")
    
    faqs: List[FAQItem] = Field(default_factory=list)
    playbooks: List[PlaybookItem] = Field(default_factory=list)
    permissions: List[PermissionItem] = Field(default_factory=list)
    concepts: List[ConceptItem] = Field(default_factory=list)


class KnowledgeContext(BaseModel):
    """
    Hierarchical knowledge context for LLM consumption.
    
    Organized by topic/concept for better LLM comprehension.
    """
    groups: List[KnowledgeGroup] = Field(default_factory=list)
    
    formatted: str = Field(
        default="",
        description="Pre-formatted hierarchical text ready for LLM prompt",
    )
    
    total_faqs: int = 0
    total_playbooks: int = 0
    total_permissions: int = 0
    total_concepts: int = 0


class FieldItem(BaseModel):
    """Schema field in LLM-friendly format."""
    path: str = Field(description="Full field path (e.g., table.column)")
    data_type: str = Field(description="Data type (varchar, int, etc.)")
    description: str = Field(default="")
    business_meaning: Optional[str] = Field(
        default=None,
        description="Business context for this field",
    )
    allowed_values: Optional[List[str]] = Field(
        default=None,
        description="Enum/allowed values if constrained",
    )
    value_meanings: Optional[Dict[str, str]] = Field(
        default=None,
        description="Mapping of values to their business meanings",
    )
    is_nullable: bool = Field(default=True)
    is_primary_key: bool = Field(default=False)
    is_foreign_key: bool = Field(default=False)
    references: Optional[str] = Field(
        default=None,
        description="Foreign key reference (e.g., vendors.id)",
    )
    score: float = Field(default=0.0)
    is_direct_match: bool = Field(
        default=False,
        description="True if directly matched by search, False if from expansion",
    )


class ConceptFieldGroup(BaseModel):
    """
    Group of fields under a business concept.
    
    Provides hierarchical organization showing concept -> fields relationship.
    """
    concept: str = Field(description="Business concept name")
    description: Optional[str] = Field(default=None)
    relevance_score: float
    is_matched: bool = Field(
        default=False,
        description="True if concept was directly matched by query",
    )
    
    fields: List[FieldItem] = Field(default_factory=list)
    
    children: List["ConceptFieldGroup"] = Field(default_factory=list)


class ExampleItem(BaseModel):
    """Q&A example in LLM-friendly format."""
    question: str
    query: str
    query_type: str = Field(description="sql, elasticsearch, or api")
    explanation: Optional[str] = None
    verified: bool = False
    relevance_score: float = Field(default=0.0)


class SchemaContext(BaseModel):
    """
    Hierarchical schema context for LLM consumption.
    
    Organized by concept for better LLM comprehension of data model.
    """
    dataset_name: Optional[str] = Field(
        default=None,
        description="Primary dataset name if single dataset",
    )
    source_type: Optional[str] = Field(
        default=None,
        description="Data source type (postgres, opensearch, etc.)",
    )
    
    concept_groups: List[ConceptFieldGroup] = Field(default_factory=list)
    examples: List[ExampleItem] = Field(default_factory=list)
    formatted: str = Field(
        default="",
        description="Pre-formatted hierarchical text ready for LLM prompt",
    )
    total_fields: int = 0
    total_concepts: int = 0
    total_examples: int = 0


ConceptFieldGroup.model_rebuild()


class LLMContextStats(BaseModel):
    faqs: int = 0
    playbooks: int = 0
    permissions: int = 0
    concepts: int = 0
    schema_fields: int = 0
    schema_concepts: int = 0
    examples: int = 0
    entry_points_found: int = 0
    nodes_expanded: int = 0
    max_depth_reached: int = 0


class LLMContextResponse(BaseModel):
    context: str = Field(
        description="Combined formatted context string ready for prompt injection",
    )
    knowledge: Optional[KnowledgeContext] = Field(
        default=None,
        description="Hierarchical knowledge context (if include_knowledge=true)",
    )
    schema_context: Optional[SchemaContext] = Field(
        default=None,
        description="Hierarchical schema context (if include_schema=true)",
    )
    stats: LLMContextStats = Field(default_factory=LLMContextStats)
    debug: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Debug information (entry point IDs, search scores, etc.)",
    )
