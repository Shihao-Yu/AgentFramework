"""
Field Schema for ContextForge.

This module defines the FieldSpec model for representing schema fields
from any data source (SQL tables, OpenSearch indices, REST API parameters).

Replaces LangfuseFieldMetadata with a cleaner, source-agnostic design.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class FieldType(str, Enum):
    """Common field types across all data sources."""
    
    # Primitives
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"
    
    # Complex
    JSON = "json"
    ARRAY = "array"
    OBJECT = "object"
    NESTED = "nested"
    
    # Search-specific
    TEXT = "text"
    KEYWORD = "keyword"
    
    # SQL-specific
    DECIMAL = "decimal"
    UUID = "uuid"
    
    # Special
    UNKNOWN = "unknown"


class SourceType(str, Enum):
    """Data source types."""
    
    SQL = "sql"
    POSTGRES = "postgres"
    MYSQL = "mysql"
    CLICKHOUSE = "clickhouse"
    OPENSEARCH = "opensearch"
    ELASTICSEARCH = "elasticsearch"
    REST_API = "rest_api"
    MONGODB = "mongodb"
    UNKNOWN = "unknown"


class FieldSpec(BaseModel):
    """
    Schema field metadata for ContextForge.
    
    Represents a field from any data source (SQL table column,
    OpenSearch field, REST API parameter, etc.).
    
    Used for:
    - Schema retrieval in RAG pipeline
    - Graph-based field relationships
    - Query generation context
    
    Example:
        >>> field = FieldSpec(
        ...     name="status",
        ...     qualified_name="orders.status",
        ...     type=FieldType.KEYWORD,
        ...     description="Order status",
        ...     maps_to=["order", "status"],
        ...     allowed_values=["pending", "shipped", "delivered"],
        ...     value_synonyms={"pending": ["waiting", "open"]},
        ... )
    """
    
    # === Identity ===
    name: str = Field(..., description="Field name")
    qualified_name: Optional[str] = Field(
        default=None,
        description="Full path including parent (e.g., 'orders.status', 'items.product_id')"
    )
    
    # === Type Information ===
    type: Union[FieldType, str] = Field(
        default=FieldType.STRING,
        description="Data type of the field"
    )
    nullable: bool = Field(default=True, description="Whether field can be null")
    
    # === Business Context ===
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of field purpose"
    )
    business_meaning: Optional[str] = Field(
        default=None,
        description="Business context and how the field is used"
    )
    
    # === Schema Linking (for graph integration) ===
    maps_to: List[str] = Field(
        default_factory=list,
        description="Concepts this field maps to (e.g., ['order', 'status'])"
    )
    aliases: List[str] = Field(
        default_factory=list,
        description="Alternative names for this field"
    )
    related_fields: List[str] = Field(
        default_factory=list,
        description="Related fields (foreign keys, references)"
    )
    
    # === Value Information ===
    allowed_values: List[str] = Field(
        default_factory=list,
        description="Valid enum values (exhaustive list)"
    )
    value_synonyms: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Canonical value -> synonyms mapping (e.g., {'pending': ['waiting', 'open']})"
    )
    value_examples: List[str] = Field(
        default_factory=list,
        description="Example values (non-exhaustive)"
    )
    value_patterns: Optional[str] = Field(
        default=None,
        description="Regex pattern or format description"
    )
    value_encoding: Optional[Dict[str, str]] = Field(
        default=None,
        description="Value encoding map (e.g., {'P': 'Pending', 'A': 'Approved'})"
    )
    
    # === Query Hints ===
    searchable: bool = Field(default=True, description="Can be used in search/WHERE clauses")
    filterable: bool = Field(default=True, description="Can be used for filtering")
    sortable: bool = Field(default=True, description="Can be used for sorting")
    aggregatable: bool = Field(default=False, description="Can be used in aggregations")
    search_guidance: Optional[str] = Field(
        default=None,
        description="How to use this field in queries"
    )
    common_filters: List[str] = Field(
        default_factory=list,
        description="Common filter patterns for this field"
    )
    aggregation_hints: Optional[str] = Field(
        default=None,
        description="Aggregation usage hints"
    )
    
    # === Source Information ===
    source_type: Union[SourceType, str] = Field(
        default=SourceType.UNKNOWN,
        description="Data source type"
    )
    index_name: Optional[str] = Field(
        default=None,
        description="Parent index/table/collection name"
    )
    parent_entity: Optional[str] = Field(
        default=None,
        description="Parent entity name"
    )
    
    # === Nested Fields ===
    nested_fields: Optional[List['FieldSpec']] = Field(
        default=None,
        description="Nested field definitions for object/nested types"
    )
    
    # === Metadata Flags ===
    is_required: bool = Field(default=False, description="Is this field required?")
    is_indexed: bool = Field(default=False, description="Is this field indexed?")
    is_sensitive: bool = Field(default=False, description="Contains PII or sensitive data?")
    is_primary_key: bool = Field(default=False, description="Is this a primary key?")
    
    # === Versioning ===
    human_edited: bool = Field(default=False, description="Has been manually edited")
    last_modified: Optional[datetime] = Field(default=None, description="Last modification time")
    modified_by: Optional[str] = Field(default=None, description="Who made the last modification")
    
    # === Vector Embedding (for semantic search) ===
    embedding: List[float] = Field(
        default_factory=list,
        description="Vector embedding for semantic search"
    )
    
    model_config = ConfigDict(use_enum_values=True)
    
    @property
    def full_name(self) -> str:
        """Get the most specific name available."""
        return self.qualified_name or self.name
    
    @property
    def path(self) -> str:
        """Alias for qualified_name/full_name (compatibility with yaml_schema.FieldSpec)."""
        return self.full_name
    
    @property
    def es_type(self) -> str:
        """Alias for type (compatibility with yaml_schema.FieldSpec)."""
        return str(self.type)
    
    def has_value_synonyms(self) -> bool:
        """Check if this field has value synonyms defined."""
        return bool(self.value_synonyms)
    
    def get_canonical_value(self, synonym: str) -> Optional[str]:
        """
        Get canonical value for a synonym.
        
        Args:
            synonym: The synonym to look up
            
        Returns:
            Canonical value if found, None otherwise
        """
        synonym_lower = synonym.lower()
        for canonical, synonyms in self.value_synonyms.items():
            if synonym_lower == canonical.lower():
                return canonical
            if synonym_lower in [s.lower() for s in synonyms]:
                return canonical
        return None
    
    def to_context_string(self, include_values: bool = True) -> str:
        """
        Format field for LLM context.
        
        Args:
            include_values: Whether to include allowed values and synonyms
            
        Returns:
            Formatted string for prompt context
        """
        parts = [f"{self.full_name} ({self.type})"]
        
        if self.description:
            parts.append(f": {self.description}")
        
        if include_values and self.allowed_values:
            parts.append(f"\n  Allowed: {', '.join(self.allowed_values[:10])}")
            if len(self.allowed_values) > 10:
                parts.append(f"... (+{len(self.allowed_values) - 10} more)")
        
        if include_values and self.value_synonyms:
            for canonical, synonyms in list(self.value_synonyms.items())[:5]:
                parts.append(f"\n  '{canonical}' = {', '.join(synonyms)}")
        
        return "".join(parts)


# For backward compatibility during migration
LangfuseFieldMetadata = FieldSpec

# Enable forward references for nested FieldSpec
FieldSpec.model_rebuild()
