"""
Constants for ContextForge - Eliminates magic strings across the codebase.

This module centralizes all string constants used throughout ContextForge,
making them easier to maintain and preventing typos.
"""


# ============================================================================
# Collection Types (adapted for PostgreSQL node_types)
# ============================================================================


class CollectionType:
    """Node type suffixes for different data types in PostgreSQL."""

    SCHEMA = "schema_field"        # Field metadata and schema information
    EXAMPLES = "schema_example"    # Q&A example pairs
    CONFIG = "schema_index"        # Master document configuration
    EXECUTIONS = "query_execution" # Query execution records
    DOCUMENTATION = "documentation" # Additional documentation


# ============================================================================
# Status Values
# ============================================================================


class Status:
    """Operation status values."""

    SUCCESS = "success"
    ERROR = "error"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"
    COMPLETED = "completed"


# ============================================================================
# Feedback Types
# ============================================================================


class FeedbackType:
    """User feedback types for query quality assessment."""

    POSITIVE = "positive"      # Query is correct
    NEGATIVE = "negative"      # Query is wrong
    CORRECTED = "corrected"    # User provided correction
    NEUTRAL = "neutral"        # No strong opinion


# ============================================================================
# Q&A Status Values
# ============================================================================


class QAStatusValue:
    """Status values for Q&A pairs in the review workflow."""

    PENDING_REVIEW = "pending_review"    # Waiting for human review
    APPROVED = "approved"                # Approved for use
    REJECTED = "rejected"                # Rejected, don't use
    NEEDS_UPDATE = "needs_update"        # Needs modification


# ============================================================================
# Configuration
# ============================================================================


class Config:
    """Configuration file names and paths."""

    CONFIG_FILENAME = ".contextforge.yaml"
    CONFIG_ENV_VAR = "CONTEXTFORGE_CONFIG"


# ============================================================================
# Promotion Result Keys
# ============================================================================


class PromotionResultKey:
    """Keys for promotion result dictionaries."""

    STATUS = "status"
    REASON = "reason"
    QUESTION = "question"
    QUERY = "query"
    PROMPT_VERSION = "prompt_version"
    NEEDS_REVIEW = "needs_review"
    PROMOTED = "promoted"
    ERRORS = "errors"


# ============================================================================
# Metadata Keys
# ============================================================================


class MetadataKey:
    """Common metadata keys for documents."""

    TENANT_ID = "tenant_id"
    DOCUMENT_NAME = "document_name"
    DATASET_NAME = "dataset_name"
    FIELD_NAME = "field_name"
    FIELD_TYPE = "field_type"
    QUESTION = "question"
    QUERY = "query"
    CONFIDENCE = "confidence"
    SOURCE = "source"
    USAGE_COUNT = "usage_count"
    REVIEWED = "reviewed"
    STATUS = "status"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


# ============================================================================
# Default Values
# ============================================================================


class Defaults:
    """Default configuration values."""

    # Storage
    POSTGRES_PATH = "./data"  # For any file-based caching

    # Retrieval
    SIMILARITY_THRESHOLD = 0.85
    TOP_K_RESULTS = 5
    LLM_CONTEXT_THRESHOLD = 0.6  # Minimum score for LLM context

    # Promotion
    MIN_CONFIDENCE = 0.9
    MIN_USAGE_COUNT = 5
    MIN_SUCCESS_RATE = 0.8

    # Scoring weights (fusion strategy)
    CONCEPT_WEIGHT = 0.30
    VALUE_WEIGHT = 0.35
    PRONOUN_WEIGHT = 0.15
    BM25_WEIGHT = 0.20

    # Graph
    EXPANSION_HOPS = 2
    FUZZY_THRESHOLD = 0.8
    MAX_FIELDS = 30

    # Cache
    GRAPH_CACHE_TTL_SECONDS = 300


# ============================================================================
# Retrieval Strategies
# ============================================================================


class RetrievalStrategy:
    """Available retrieval strategies."""

    CONCEPT = "concept"    # Graph traversal via concepts
    FIELD = "field"        # Field path keyword matching
    HYBRID = "hybrid"      # Concept + field fallback
    FUSION = "fusion"      # Parallel weighted scoring (best quality)


# ============================================================================
# Edge Types for Graph
# ============================================================================


class EdgeTypeValue:
    """Edge types in the schema graph."""

    HAS_FIELD = "has_field"        # Index → Field
    NESTED_IN = "nested_in"        # Nested Field → Parent Field
    MAPS_TO = "maps_to"            # Field → Concept
    RELATES_TO = "relates_to"      # Concept → Concept
    ALIAS_OF = "alias_of"          # Alias → Field/Concept
    HAS_VALUE = "has_value"        # Concept → Value
    SYNONYM_OF = "synonym_of"      # Alias → Value
    DEMONSTRATES = "demonstrates"  # Example → Concept
    USES_FIELD = "uses_field"      # Example → Field
    USES_VALUE = "uses_value"      # Example → Value
    HAS_VARIANT = "has_variant"    # Example → Variant keyword alias


# ============================================================================
# Node Types for Graph
# ============================================================================


class NodeTypeValue:
    """Node types in the schema graph."""

    INDEX = "index"
    FIELD = "field"
    CONCEPT = "concept"
    ALIAS = "alias"
    VALUE = "value"
    EXAMPLE = "example"
    ENDPOINT = "endpoint"
    PARAM = "param"
    RESPONSE_FIELD = "response_field"
