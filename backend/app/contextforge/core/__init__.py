"""
ContextForge Core - Foundation types, protocols, and utilities.

This module provides the foundational components:
- models: Data models (QueryType, Complexity, DocumentMasterConfig, etc.)
- protocols: DataSource protocol and registry
- constants: Centralized constants (no magic strings)
- planning_models: Multi-step query planning models
- utils: Serialization and validation utilities
"""

from .models import (
    QueryType,
    Complexity,
    QAStatus,
    SearchRules,
    VectorStoreConfig,
    APIConnectorConfig,
    DocumentMasterConfig,
    Relationship,
    APIEndpointMetadata,
    SQLTableMetadata,
    NoSQLCollectionMetadata,
    EntityMetadata,
    QueryExecutionRecord,
    PromotionCandidate,
    PromotionCriteria,
    ComplexityReport,
    ValidationResult,
    EnrichmentOptions,
    OnboardingResult,
    MergeResult,
    SchemaDiff,
    MergePlan,
    MergeAction,
    QueryGenerationResult,
    ConceptSubgraph,
)

from .protocols import (
    SourceType,
    UnifiedField,
    UnifiedSchema,
    ConceptInfo,
    RetrievalContext,
    DataSource,
    DataSourceBase,
    register_source,
    get_source,
    list_sources,
    is_source_registered,
)

from .constants import (
    CollectionType,
    Status,
    FeedbackType,
    QAStatusValue,
    Config,
    PromotionResultKey,
    MetadataKey,
    Defaults,
)

from .planning_models import (
    PlanStatus,
    StepStatus,
    DisambiguationCategory,
    DisambiguationOption,
    DisambiguationQuestion,
    QueryPlanStep,
    PlanVersion,
    QueryPlan,
    PlanExecutionState,
    QueryPlanSummary,
    PlanExecutionResult,
)

from .utils import (
    to_json_dict,
    to_json,
    from_json_dict,
    from_json,
    serialize_for_storage,
    validate_required_fields,
    validate_field_length,
    generate_rewritten_question,
    generate_question_from_query,
    sanitize_query_for_execution,
    ConversationContext,
)

__all__ = [
    # Models
    "QueryType",
    "Complexity",
    "QAStatus",
    "SearchRules",
    "VectorStoreConfig",
    "APIConnectorConfig",
    "DocumentMasterConfig",
    "Relationship",
    "APIEndpointMetadata",
    "SQLTableMetadata",
    "NoSQLCollectionMetadata",
    "EntityMetadata",
    "QueryExecutionRecord",
    "PromotionCandidate",
    "PromotionCriteria",
    "ComplexityReport",
    "ValidationResult",
    "EnrichmentOptions",
    "OnboardingResult",
    "MergeResult",
    "SchemaDiff",
    "MergePlan",
    "MergeAction",
    "QueryGenerationResult",
    "ConceptSubgraph",
    # Protocols
    "SourceType",
    "UnifiedField",
    "UnifiedSchema",
    "ConceptInfo",
    "RetrievalContext",
    "DataSource",
    "DataSourceBase",
    "register_source",
    "get_source",
    "list_sources",
    "is_source_registered",
    # Constants
    "CollectionType",
    "Status",
    "FeedbackType",
    "QAStatusValue",
    "Config",
    "PromotionResultKey",
    "MetadataKey",
    "Defaults",
    # Planning
    "PlanStatus",
    "StepStatus",
    "DisambiguationCategory",
    "DisambiguationOption",
    "DisambiguationQuestion",
    "QueryPlanStep",
    "PlanVersion",
    "QueryPlan",
    "PlanExecutionState",
    "QueryPlanSummary",
    "PlanExecutionResult",
    # Utils
    "to_json_dict",
    "to_json",
    "from_json_dict",
    "from_json",
    "serialize_for_storage",
    "validate_required_fields",
    "validate_field_length",
    "generate_rewritten_question",
    "generate_question_from_query",
    "sanitize_query_for_execution",
    "ConversationContext",
]
