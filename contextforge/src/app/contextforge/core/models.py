"""
Data models for ContextForge.

This module defines all dataclasses used across the framework:
- Master configuration (DocumentMasterConfig)
- Entity metadata (EntityMetadata)
- Type-specific metadata (APIEndpointMetadata, SQLTableMetadata, NoSQLCollectionMetadata)
- Configuration classes (SearchRules, VectorStoreConfig, APIConnectorConfig)
- Query execution and promotion tracking
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..schema.field_schema import FieldSpec


# ============================================================================
# Retrieval Context Models
# ============================================================================


@dataclass
class ConceptSubgraph:
    """
    Represents a concept and its related fields as a hierarchical subgraph.

    Used in the FEED phase to group related fields by concept, enabling
    the LLM to understand parent-child relationships (e.g., spend_category
    contains sub_category).

    Example structure:
        ConceptSubgraph(
            concept_name="spend_category",
            fields=[spend_category.id, spend_category.name],
            children={"sub_category": ConceptSubgraph(...)},
            relationships=[("sub_category", "CONTAINS")],
            fusion_score=0.85
        )
    """

    concept_name: str  # Root concept name (e.g., "spend_category")
    fields: List[Any]  # Fields belonging to this concept (FieldSpec)
    children: Dict[str, "ConceptSubgraph"] = field(default_factory=dict)
    relationships: List[tuple] = field(default_factory=list)  # [(target_concept, edge_type)]
    fusion_score: float = 0.0  # Highest field score in this concept
    depth: int = 0  # Nesting depth (0 = root)
    is_matched: bool = False  # True if this concept was directly matched

    def all_fields(self) -> List[Any]:
        """Get all fields including from children (flattened)."""
        result = list(self.fields)
        for child in self.children.values():
            result.extend(child.all_fields())
        return result

    def total_field_count(self) -> int:
        """Count total fields including children."""
        count = len(self.fields)
        for child in self.children.values():
            count += child.total_field_count()
        return count


# ============================================================================
# Query Type and Status Enums
# ============================================================================


class QueryType(str, Enum):
    """Supported query types"""

    # SQL Dialects
    SQL_SERVER = "sql_server"
    MYSQL = "mysql"
    POSTGRES = "postgres"
    ORACLE = "oracle"
    SQLITE = "sqlite"
    CLICKHOUSE = "clickhouse"

    # NoSQL
    MONGODB = "mongodb"

    # Search Engines
    OPENSEARCH = "opensearch"
    ELASTICSEARCH = "elasticsearch"

    # APIs
    REST_API = "rest_api"


class Complexity(str, Enum):
    """Schema complexity levels"""

    EASY = "easy"  # 1-2 entities, <20 fields, no relationships
    MEDIUM = "medium"  # 1 entity with 50+ fields OR 3-10 entities
    COMPLEX = "complex"  # >10 entities OR relationships OR >200 fields


class QAStatus(str, Enum):
    """Q&A example review status"""

    PENDING = "pending"  # Awaiting human review
    APPROVED = "approved"  # Approved for training
    REJECTED = "rejected"  # Rejected, exclude from training


@dataclass
class SearchRules:
    """Search and retrieval configuration"""

    schema_top_k: int = 10  # How many schema fields to retrieve
    examples_top_n: int = 5  # How many Q&A examples to retrieve
    similarity_threshold: float = 0.7
    enable_cross_document: bool = False  # Search across tenant's docs
    enable_fuzzy_matching: bool = True


@dataclass
class VectorStoreConfig:
    """Vector store configuration - adapted for PostgreSQL + pgvector"""

    store_type: str = "postgres"  # postgres (pgvector), in_memory
    collection_prefix: str = ""  # e.g., "tenant_acme"
    persistence_path: str = "."  # Not used for postgres
    embedding_dimension: int = 1024  # Stella model default
    embedding_model: str = "stella"  # Embedding model identifier
    tenant_credentials: Dict[str, str] = field(default_factory=dict)

    # PostgreSQL settings
    postgres_dsn: str = ""  # Connection string if not using default


@dataclass
class APIConnectorConfig:
    """REST API connector configuration (for query_type='REST_API')"""

    base_url: str  # e.g., "https://api.company.com"
    auth_type: str  # "bearer", "api_key", "oauth", "basic"
    auth_credentials: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30  # Request timeout in seconds
    retry_strategy: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class DocumentMasterConfig:
    """Master configuration for a tenant's document"""

    # Identity
    document_name: str  # e.g., "acme_orders"
    tenant_id: str  # Multi-tenant isolation key
    version: str  # Schema version (semver)

    # Query Type
    query_type: QueryType  # Enum: SQL_SERVER, MYSQL, POSTGRES, etc.
    query_dialect: str  # Specific dialect (e.g., "T-SQL", "PL/SQL")

    # Storage Configuration
    vector_store: VectorStoreConfig  # PostgreSQL by default
    embedding_model: str  # e.g., "text-embedding-3-small"

    # Business Context
    business_domain: str  # e.g., "E-commerce Orders"
    business_description: str  # High-level purpose

    # Schema Metadata
    schema_complexity: Complexity  # Enum: EASY, MEDIUM, COMPLEX
    total_entities: int  # Tables/Collections/Endpoints
    total_fields: int  # Total field count
    has_relationships: bool  # Cross-entity relationships exist

    # Generation Rules
    formatting_rules: List[str]  # Query formatting guidelines
    search_rules: SearchRules  # How to search this schema
    validation_rules: List[str]  # Query validation requirements

    # Prompt Templates (4-Prompt Architecture)
    schema_analysis_prompt: Optional[str] = None
    field_inference_prompt: Optional[str] = None
    qa_generation_prompt: Optional[str] = None
    query_generation_prompt: Optional[str] = None

    # Additional Context
    static_documentation: Optional[str] = None

    # API Connector (for REST_API query_type)
    api_config: Optional[APIConnectorConfig] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_inference_at: datetime = field(default_factory=datetime.now)


@dataclass
class Relationship:
    """Cross-entity relationship"""

    from_field: str
    to_entity: str
    to_field: str
    relationship_type: str  # "one-to-many", "many-to-one", "many-to-many"
    description: Optional[str] = None


@dataclass
class APIEndpointMetadata:
    """API-specific metadata (only populated when type='endpoint')"""

    http_method: str  # "GET", "POST", "PUT", "DELETE"
    endpoint_path: str  # "/api/finance/spend-categories"
    query_parameters: List[str] = field(default_factory=list)
    request_body_schema: Optional[Dict] = None
    response_content_type: str = "application/json"
    requires_auth: bool = True


@dataclass
class SQLTableMetadata:
    """SQL-specific metadata"""

    primary_key: Optional[str] = None
    indexes: List[str] = field(default_factory=list)
    foreign_keys: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class NoSQLCollectionMetadata:
    """NoSQL-specific metadata"""

    shard_key: Optional[str] = None
    indexes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EntityMetadata:
    """Represents an entity within a document (table/endpoint/index/collection)"""

    name: str
    type: str  # "table", "endpoint", "index", "collection", "view"
    fields: List["FieldSpec"]  # Use FieldSpec from schema module
    relationships: List[Relationship]
    description: str
    common_queries: List[str] = field(default_factory=list)

    # Type-specific metadata (Union-typed, only one populated)
    metadata: Optional[
        Union[APIEndpointMetadata, SQLTableMetadata, NoSQLCollectionMetadata]
    ] = None


@dataclass
class QueryExecutionRecord:
    """
    Record of a query generation and execution.

    Used for usage tracking, learning, and promotion logic.
    """

    # Execution Identity
    execution_id: str  # UUID for this execution
    tenant_id: str
    document_name: str

    # Query Context
    user_question: str  # Natural language question from user
    generated_query: str  # Query generated by LLM
    query_type: str  # "postgres", "opensearch", etc.

    # Generation Metadata
    confidence: float  # Confidence score (0-1)
    context_used: Dict[str, int] = field(default_factory=dict)
    examples_matched: List[str] = field(default_factory=list)

    # Timestamps
    timestamp: datetime = field(default_factory=datetime.now)

    # Execution Result (optional - filled if query executed)
    execution_success: Optional[bool] = None
    execution_time_ms: Optional[float] = None
    rows_returned: Optional[int] = None
    error_message: Optional[str] = None

    # User Feedback (optional - filled if user provides feedback)
    user_feedback: Optional[str] = None  # FeedbackType value
    corrected_query: Optional[str] = None
    feedback_timestamp: Optional[datetime] = None
    feedback_comment: Optional[str] = None

    # Promotion Tracking
    promoted_to_examples: bool = False
    promotion_timestamp: Optional[datetime] = None


@dataclass
class PromotionCandidate:
    """
    Aggregated usage data for a promotion candidate.

    Result from analyzing QueryExecutionRecords to identify
    high-quality Q&A pairs for promotion.
    """

    # Q&A Content
    question: str
    query: str
    query_type: str

    # Aggregated Statistics
    usage_count: int
    success_count: int
    success_rate: float
    avg_confidence: float

    # Feedback Statistics
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0
    corrected_count: int = 0
    feedback_ratio: float = 0.0

    # Temporal Information
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    days_active: int = 0

    # Promotion Status
    already_promoted: bool = False
    promotion_score: float = 0.0

    # Example Execution IDs (for traceability)
    execution_ids: List[str] = field(default_factory=list)


@dataclass
class PromotionCriteria:
    """
    Configurable criteria for automatic promotion to examples.
    """

    # Primary Criteria
    min_confidence: float = 0.9
    min_usage_count: int = 5

    # Quality Criteria
    min_success_rate: float = 0.8
    min_positive_feedback_ratio: float = 0.7

    # Temporal Criteria
    min_age_days: int = 1
    max_recency_days: int = 30

    # Diversity Criteria
    max_similar_promoted: int = 3
    similarity_threshold: float = 0.85

    # Manual Review
    requires_human_review: bool = True


# Result dataclasses for pipeline operations


@dataclass
class ComplexityReport:
    """Report from schema complexity analysis"""

    total_entities: int
    total_fields: int
    max_fields_per_entity: int
    has_relationships: bool
    complexity: Complexity
    entities: List[EntityMetadata]
    fields: List[str]  # Raw field definitions
    entity_context: str  # Context for inference


@dataclass
class ValidationResult:
    """Result from inference validation"""

    is_valid: bool
    quality_score: float  # 0-100
    issues: List[str]
    warnings: List[str]


@dataclass
class EnrichmentOptions:
    """
    Fine-grained control over LLM enrichment during onboarding.
    """

    # What to enrich
    enrich_field_metadata: bool = True
    enrich_qa_pairs: bool = True

    # Generation parameters
    target_qa_count: int = 20
    max_fields_per_batch: int = 10

    # Quality control
    min_quality_score: float = 60.0
    mark_for_review: bool = True

    # Merge behavior
    preserve_existing: bool = True
    append_qa: bool = True


@dataclass
class OnboardingResult:
    """Result from tenant onboarding."""

    status: str  # "SUCCESS", "REQUIRES_REVIEW", "FAILED"
    quality_score: float

    # Processing metrics
    entities_processed: int = 0
    fields_processed: int = 0
    qa_pairs_generated: int = 0

    # Source type (from plugin architecture)
    source_type: Optional[str] = None

    # Schema version tracking
    schema_version: Optional[int] = None
    previous_version: Optional[int] = None

    # Enrichment status
    enrichment_performed: bool = False
    enrichment_fields_count: int = 0
    enrichment_qa_count: int = 0

    # Issues and warnings
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class MergeResult:
    """Result from schema merge operation"""

    status: str  # "SUCCESS", "REQUIRES_REVIEW"
    new_version: str
    fields_added: int
    fields_removed: int
    fields_modified: int
    conflicts: List[str]
    human_edits_preserved: int


@dataclass
class SchemaDiff:
    """Difference between two schemas"""

    added_fields: List["FieldSpec"]
    removed_fields: List["FieldSpec"]
    modified_fields: List[str]  # Field names
    human_edited_fields_count: int


@dataclass
class MergePlan:
    """Plan for merging schema changes"""

    actions: List["MergeAction"] = field(default_factory=list)

    def add_action(self, action: "MergeAction"):
        self.actions.append(action)


@dataclass
class MergeAction:
    """Individual merge action"""

    type: str  # "CREATE", "ARCHIVE", "AUTO_UPDATE", "CONFLICT"
    field_name: str
    strategy: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class QueryGenerationResult:
    """Result from query generation"""

    query: str
    confidence: float
    context_used: Dict[str, int]

    # Dataset routing info
    routed_dataset: Optional[str] = None
    routing_confidence: Optional[float] = None
    routing_method: Optional[str] = None  # "forced", "hybrid", "llm_rerank"

    # Assumptions tracking
    assumptions: List[str] = field(default_factory=list)
