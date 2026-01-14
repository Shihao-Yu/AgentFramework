"""
Data Source Protocols for ContextForge.

Defines the contracts that all data sources must implement to integrate
with the ContextForge framework. This enables a plugin-like architecture
where new data sources can be added without modifying core logic.

Key Protocols:
- DataSource: Main interface for a data source (parser, generator, etc.)
- SchemaParser: Parses raw schema into source-specific models
- QueryGenerator: Generates queries from retrieval context
- OnboardingPipeline: Orchestrates tenant onboarding for a source

Usage:
    from app.contextforge.sources import get_source
    
    source = get_source("opensearch")
    schema = source.parse_schema(raw_mapping)
    query = await source.generate_query(context, question, llm_client)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Type,
    Union,
    runtime_checkable,
)

if TYPE_CHECKING:
    from ..storage.postgres_adapter import PostgresAdapter


# =============================================================================
# Unified Field Model
# =============================================================================


@dataclass
class UnifiedField:
    """
    Source-agnostic field representation for unified graph indexing.
    
    All source-specific schemas (FieldSpec, ColumnSpec, ParameterSpec, etc.)
    convert to this format for:
    - Graph-based retrieval across sources
    - Concept linking
    - Value synonym resolution
    
    This is the "lingua franca" that enables multi-source queries.
    
    Examples:
        # From OpenSearch FieldSpec
        UnifiedField(
            path="order.status",
            field_type="keyword",
            source_type="opensearch",
            maps_to="order",
            allowed_values=["P", "R", "C"],
            value_synonyms={"P": ["pending", "waiting"]}
        )
        
        # From PostgreSQL ColumnSpec
        UnifiedField(
            path="orders.status",
            field_type="varchar",
            source_type="postgres",
            maps_to="order",
        )
        
        # From REST API ParameterSpec
        UnifiedField(
            path="query.status",
            field_type="string",
            source_type="rest_api",
            maps_to="order",
        )
    """
    # Identity
    path: str                              # Dot-notation path (e.g., "order.status")
    field_type: str                        # Normalized type (text, keyword, number, date, boolean)
    source_type: str                       # Origin source ("opensearch", "postgres", "rest_api")
    
    # Semantic
    description: Optional[str] = None
    business_meaning: str = ""
    maps_to: Optional[str] = None          # Concept name (normalized lowercase)
    
    # Value constraints
    allowed_values: Optional[List[str]] = None
    value_synonyms: Dict[str, List[str]] = field(default_factory=dict)
    value_examples: List[str] = field(default_factory=list)
    
    # Metadata
    is_required: bool = False
    is_indexed: bool = True
    deprecated: bool = False
    human_edited: bool = False
    last_updated: Optional[datetime] = None
    
    # Source-specific metadata (preserved for generation)
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_canonical_value(self, user_value: str) -> Optional[str]:
        """Look up canonical value from synonym."""
        user_lower = user_value.lower().strip()
        for canonical, synonyms in self.value_synonyms.items():
            if user_lower == canonical.lower():
                return canonical
            if user_lower in [s.lower() for s in synonyms]:
                return canonical
        return None


@dataclass
class UnifiedSchema:
    """
    Multi-source schema container.
    
    Holds fields from multiple data sources, linked by shared concepts.
    This enables queries that understand "order" whether it's an OpenSearch
    index, a PostgreSQL table, or a REST API endpoint.
    """
    tenant_id: str
    document_name: str
    
    # Unified fields from all sources
    fields: List[UnifiedField] = field(default_factory=list)
    
    # Concepts shared across sources
    concepts: Dict[str, "ConceptInfo"] = field(default_factory=dict)
    
    # Source-specific schemas (preserved for generation)
    source_schemas: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: Optional[datetime] = None
    version: str = "1.0"
    
    def get_fields_for_source(self, source_type: str) -> List[UnifiedField]:
        """Get all fields from a specific source."""
        return [f for f in self.fields if f.source_type == source_type]
    
    def get_fields_for_concept(self, concept_name: str) -> List[UnifiedField]:
        """Get all fields mapped to a concept (across all sources)."""
        concept_lower = concept_name.lower()
        return [f for f in self.fields if f.maps_to == concept_lower]
    
    def get_sources(self) -> List[str]:
        """Get list of unique source types in this schema."""
        return list(set(f.source_type for f in self.fields))


@dataclass
class ConceptInfo:
    """Concept metadata shared across sources."""
    name: str
    description: str = ""
    aliases: List[str] = field(default_factory=list)
    value_synonyms: Dict[str, List[str]] = field(default_factory=dict)
    related_pronouns: List[str] = field(default_factory=list)


# =============================================================================
# Retrieval Context
# =============================================================================


@dataclass
class RetrievalContext:
    """
    Context retrieved for query generation.
    
    Contains matched fields, concepts, and source-specific context
    needed by the generator to produce a query.
    """
    # What was matched
    matched_fields: List[UnifiedField] = field(default_factory=list)
    matched_concepts: List[str] = field(default_factory=list)
    
    # Value mappings found (user term -> canonical value)
    value_mappings: Dict[str, str] = field(default_factory=dict)
    
    # Source-specific context (e.g., endpoint info for REST API)
    source_context: Dict[str, Any] = field(default_factory=dict)
    
    # Retrieval metadata
    confidence: float = 0.0
    retrieval_method: str = ""  # "graph", "vector", "hybrid"
    
    # Recommended source for this query
    recommended_source: Optional[str] = None
    routing_reason: str = ""


# =============================================================================
# Data Source Protocol
# =============================================================================


class SourceType(str, Enum):
    """Registered data source types."""
    OPENSEARCH = "opensearch"
    ELASTICSEARCH = "elasticsearch"
    POSTGRES = "postgres"
    CLICKHOUSE = "clickhouse"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REST_API = "rest_api"
    GRAPHQL = "graphql"


@runtime_checkable
class DataSource(Protocol):
    """
    Protocol defining the contract for all data sources.
    
    Each data source (OpenSearch, PostgreSQL, REST API, etc.) implements
    this protocol to integrate with ContextForge's pipelines.
    
    The protocol is designed for:
    - Onboarding: parse_schema() -> to_unified_fields()
    - Retrieval: build_graph() for graph-based context retrieval
    - Generation: generate_query() with extraction_strategy
    
    Example implementation:
        @register_source("opensearch")
        class OpenSearchSource(DataSourceBase):
            source_type = SourceType.OPENSEARCH
            
            def parse_schema(self, raw_schema, **kwargs):
                return MappingConverter(raw_schema).to_yaml_schema(**kwargs)
            
            def to_unified_fields(self, schema):
                return [field.to_unified() for field in schema.get_all_field_specs()]
            
            async def generate_query(self, context, question, llm_client):
                prompt = self.build_prompt(context, question)
                return await llm_client.submit_prompt(prompt)
    """
    
    source_type: SourceType
    
    # -------------------------------------------------------------------------
    # Schema Parsing
    # -------------------------------------------------------------------------
    
    def parse_schema(
        self, 
        raw_schema: Union[str, Dict[str, Any]], 
        **kwargs
    ) -> Any:
        """
        Parse raw schema into source-specific schema model.
        
        Args:
            raw_schema: Raw schema (DDL string, JSON mapping, OpenAPI spec, etc.)
            **kwargs: Source-specific options (e.g., index_pattern for OpenSearch)
        
        Returns:
            Source-specific schema model (YAMLSchemaV1, TableSchema, etc.)
        """
        ...
    
    def to_unified_fields(self, schema: Any) -> List[UnifiedField]:
        """
        Convert source-specific schema to unified fields.
        
        This enables cross-source retrieval by normalizing all schemas
        to a common format that can be indexed in the graph.
        
        Args:
            schema: Source-specific schema model
        
        Returns:
            List of UnifiedField for graph indexing
        """
        ...
    
    # -------------------------------------------------------------------------
    # Graph Building (Optional)
    # -------------------------------------------------------------------------
    
    @property
    def supports_graph(self) -> bool:
        """Whether this source benefits from graph-based retrieval."""
        ...
    
    def build_graph(self, schema: Any) -> Optional[Any]:
        """
        Build source-specific graph for retrieval.
        
        Not all sources need graphs:
        - OpenSearch: Concept graph with nested fields
        - PostgreSQL: FK/join graph
        - REST API: Usually no graph (endpoint matching suffices)
        
        Args:
            schema: Source-specific schema model
        
        Returns:
            Graph object or None if not supported
        """
        ...
    
    # -------------------------------------------------------------------------
    # Query Generation
    # -------------------------------------------------------------------------
    
    async def generate_query(
        self,
        context: RetrievalContext,
        question: str,
        llm_client: Any,
    ) -> str:
        """
        Generate a query in source-native format.
        
        Args:
            context: Retrieved context (fields, concepts, value mappings)
            question: User's natural language question
            llm_client: LLM client for generation
        
        Returns:
            Generated query string (SQL, OpenSearch DSL, API request, etc.)
        """
        ...
    
    # -------------------------------------------------------------------------
    # Onboarding
    # -------------------------------------------------------------------------
    
    async def onboard(
        self,
        tenant_id: str,
        document_name: str,
        raw_schema: Union[str, Dict[str, Any]],
        vector_store: Optional["PostgresAdapter"] = None,
        llm_client: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Onboard a tenant document for this source.
        
        Full onboarding flow:
        1. Parse schema -> source-specific model
        2. Optionally enrich with LLM (descriptions, value synonyms)
        3. Convert to unified fields
        4. Store in vector store
        5. Build graph if supported
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document/index/table name
            raw_schema: Raw schema to parse
            vector_store: Vector store for persistence
            llm_client: LLM for enrichment (optional)
            **kwargs: Source-specific options
        
        Returns:
            Onboarding result with status, metrics, etc.
        """
        ...
    
    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------
    
    @property
    def prompt_template_key(self) -> str:
        """Key for looking up prompt templates (e.g., 'postgres', 'opensearch')."""
        ...
    
    @property
    def display_name(self) -> str:
        """Human-readable name for this source."""
        ...


# =============================================================================
# Base Implementation
# =============================================================================


class DataSourceBase(ABC):
    """
    Abstract base class for data sources.
    
    Provides common functionality and default implementations.
    Subclasses must implement the abstract methods.
    """
    
    source_type: SourceType
    
    @abstractmethod
    def parse_schema(
        self, 
        raw_schema: Union[str, Dict[str, Any]], 
        **kwargs
    ) -> Any:
        """Parse raw schema into source-specific model."""
        raise NotImplementedError
    
    @abstractmethod
    def to_unified_fields(self, schema: Any) -> List[UnifiedField]:
        """Convert source schema to unified fields."""
        raise NotImplementedError
    
    @property
    def supports_graph(self) -> bool:
        """Default: no graph support. Override for sources that need it."""
        return False
    
    def build_graph(self, schema: Any) -> Optional[Any]:
        """Default: no graph. Override for sources that need it."""
        return None
    
    @abstractmethod
    async def generate_query(
        self,
        context: RetrievalContext,
        question: str,
        llm_client: Any,
    ) -> str:
        """Generate query in source-native format."""
        raise NotImplementedError
    
    async def onboard(
        self,
        tenant_id: str,
        document_name: str,
        raw_schema: Union[str, Dict[str, Any]],
        vector_store: Optional["PostgresAdapter"] = None,
        llm_client: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Default onboarding implementation.
        
        Can be overridden for source-specific onboarding needs.
        """
        # 1. Parse schema
        schema = self.parse_schema(raw_schema, **kwargs)
        
        # 2. Convert to unified fields
        unified_fields = self.to_unified_fields(schema)
        
        # 3. Build graph if supported
        graph = None
        if self.supports_graph:
            graph = self.build_graph(schema)
        
        # 4. Store in vector store if provided
        if vector_store is not None:
            # Implementation depends on vector store API
            pass
        
        return {
            "status": "success",
            "tenant_id": tenant_id,
            "document_name": document_name,
            "source_type": self.source_type.value,
            "field_count": len(unified_fields),
            "has_graph": graph is not None,
        }
    
    @property
    def prompt_template_key(self) -> str:
        """Default: use source_type value."""
        return self.source_type.value
    
    @property
    def display_name(self) -> str:
        """Default: capitalize source_type."""
        return self.source_type.value.replace("_", " ").title()


# =============================================================================
# Source Registry
# =============================================================================

# Registry of data source implementations
_SOURCE_REGISTRY: Dict[str, Type[DataSourceBase]] = {}


def register_source(source_type: Union[str, SourceType]):
    """
    Decorator to register a data source implementation.
    
    Usage:
        @register_source(SourceType.OPENSEARCH)
        class OpenSearchSource(DataSourceBase):
            ...
    """
    def decorator(cls: Type[DataSourceBase]):
        key = source_type.value if isinstance(source_type, SourceType) else source_type
        _SOURCE_REGISTRY[key] = cls
        return cls
    return decorator


def get_source(source_type: Union[str, SourceType], **config) -> DataSourceBase:
    """
    Get a data source instance by type.
    
    Args:
        source_type: Source type (string or SourceType enum)
        **config: Configuration passed to source constructor
    
    Returns:
        DataSourceBase instance
    
    Raises:
        ValueError: If source type is not registered
    
    Usage:
        source = get_source("opensearch")
        source = get_source(SourceType.POSTGRES, host="localhost")
    """
    key = source_type.value if isinstance(source_type, SourceType) else source_type
    if key not in _SOURCE_REGISTRY:
        available = list(_SOURCE_REGISTRY.keys())
        raise ValueError(
            f"Unknown source type: {key}. "
            f"Available: {available}. "
            f"Register with @register_source('{key}')"
        )
    return _SOURCE_REGISTRY[key](**config)


def list_sources() -> List[str]:
    """List all registered source types."""
    return list(_SOURCE_REGISTRY.keys())


def is_source_registered(source_type: Union[str, SourceType]) -> bool:
    """Check if a source type is registered."""
    key = source_type.value if isinstance(source_type, SourceType) else source_type
    return key in _SOURCE_REGISTRY
