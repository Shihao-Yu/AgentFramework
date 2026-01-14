"""
YAML Schema Models for Data Source Onboarding.

Defines Pydantic models for the human-editable YAML schema format that:
- Stores field mappings with business annotations
- Defines business concepts and their relationships
- Supports smart merging when re-importing updated mappings
- Enables graph-based context retrieval

Supports multiple data sources:
- OpenSearch indices
- REST API endpoints
- SQL databases (PostgreSQL, ClickHouse, etc.)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from .api_schema import EndpointSpec


class QueryMode(str, Enum):
    """Supported query languages."""
    PPL = "PPL"
    DSL = "DSL"
    SQL = "SQL"


class SchemaType(str, Enum):
    """
    Type of data source this schema describes.
    
    Enables unified schemas that can contain multiple data source types,
    allowing a single query to route to OpenSearch OR REST API based on context.
    """
    OPENSEARCH = "opensearch"
    REST_API = "rest_api"
    SQL = "sql"  # Generic SQL (PostgreSQL, MySQL, etc.)
    POSTGRES = "postgres"
    CLICKHOUSE = "clickhouse"
    MONGODB = "mongodb"
    GRAPHQL = "graphql"
    MIXED = "mixed"  # Contains multiple data source types


class FieldSpec(BaseModel):
    """
    Specification for a single field in an index/table.

    Combines auto-imported metadata (path, es_type) with
    human-annotated semantics (description, maps_to).

    This is the SINGLE SOURCE OF TRUTH for field metadata within YAML schemas.
    """
    # Auto-imported from mapping
    path: str = Field(..., description="Dot-notation field path (e.g., 'customer.email')")
    es_type: str = Field(..., description="Field type (keyword, text, nested, integer, etc.)")

    # Human-annotated semantic info
    description: Optional[str] = Field(None, description="Human-readable field description")
    maps_to: Optional[str] = Field(None, description="Business concept this field maps to")
    business_meaning: str = Field(default="", description="Business context and usage")

    # Value constraints
    allowed_values: Optional[List[str]] = Field(
        default=None,
        description="Valid enum values for this field (e.g., ['Pending', 'Approved', 'Rejected'])"
    )
    value_examples: List[str] = Field(
        default_factory=list,
        description="Example values for this field (e.g., ['ORD-001', 'ORD-002'])"
    )
    value_encoding: Optional[Dict[str, str]] = Field(
        default=None,
        description="Value encoding map (e.g., {'P': 'Pending', 'A': 'Approved'})"
    )
    value_patterns: Optional[str] = Field(
        default=None,
        description="Regex pattern or format description (e.g., 'YYYY-MM-DD')"
    )

    # Value synonyms for LLM context
    value_synonyms: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Maps canonical values to synonyms. e.g., {'Pending': ['waiting', 'open']}"
    )

    # Search optimization
    search_guidance: str = Field(
        default="",
        description="How to use this field in queries (e.g., 'Use term query for exact match')"
    )
    common_filters: List[str] = Field(
        default_factory=list,
        description="Common filter patterns for this field"
    )
    aggregation_hints: Optional[str] = Field(
        default=None,
        description="Aggregation usage hints"
    )

    # Relationships
    related_fields: List[str] = Field(
        default_factory=list,
        description="Related fields (foreign keys, references)"
    )

    # Optional annotations
    aliases: List[str] = Field(default_factory=list, description="Alternative names for this field")
    pii: bool = Field(False, description="Contains personally identifiable information")
    searchable: bool = Field(True, description="Should this field be included in search context")
    aggregatable: bool = Field(True, description="Can be used in aggregations")
    is_required: bool = Field(False, description="Is this field required?")
    is_indexed: bool = Field(True, description="Is this field indexed?")

    # Nested fields (for nested/object types)
    nested_fields: List["FieldSpec"] = Field(
        default_factory=list,
        description="Child fields for nested/object types"
    )

    # Metadata
    auto_imported: bool = Field(True, description="Was this field auto-imported from mapping")
    human_edited: bool = Field(False, description="Has been manually edited by human")
    last_updated: Optional[datetime] = Field(None, description="Last modification timestamp")
    modified_by: str = Field(default="system", description="Who made the last modification")

    model_config = ConfigDict(use_enum_values=True)

    def get_all_paths(self) -> List[str]:
        """Get all field paths including nested fields."""
        paths = [self.path]
        for nested in self.nested_fields:
            paths.extend(nested.get_all_paths())
        return paths

    def get_canonical_value(self, synonym: str) -> Optional[str]:
        """
        Find the canonical value for a synonym.

        Args:
            synonym: A value synonym to look up (case-insensitive)

        Returns:
            The canonical value if found, None otherwise
        """
        synonym_lower = synonym.lower()
        for canonical, synonyms in self.value_synonyms.items():
            if synonym_lower == canonical.lower():
                return canonical
            if synonym_lower in [s.lower() for s in synonyms]:
                return canonical
        return None


class IndexSpec(BaseModel):
    """
    Specification for an OpenSearch index or SQL table.

    Contains all fields and their mappings to concepts.
    """
    name: str = Field(..., description="Index name or pattern (e.g., 'orders-*')")
    description: Optional[str] = Field(None, description="Index purpose and contents")
    query_mode: QueryMode = Field(QueryMode.PPL, description="Preferred query language")

    @field_validator('query_mode', mode='before')
    @classmethod
    def validate_query_mode(cls, v):
        """Convert string to QueryMode enum."""
        if isinstance(v, str):
            return QueryMode(v)
        return v

    # Fields in this index
    fields: List[FieldSpec] = Field(default_factory=list, description="All fields in this index")

    # Index-level metadata
    primary_key: Optional[str] = Field(None, description="Primary identifier field")
    timestamp_field: Optional[str] = Field(None, description="Main timestamp field")

    # Ownership
    owner: Optional[str] = Field(None, description="Team or person responsible")
    data_freshness: Optional[str] = Field(None, description="Data update frequency")

    model_config = ConfigDict(use_enum_values=True)

    def get_field(self, path: str) -> Optional[FieldSpec]:
        """Get a field by its path."""
        for field in self.fields:
            if field.path == path:
                return field
            # Check nested fields
            for nested in field.nested_fields:
                if nested.path == path:
                    return nested
        return None

    def get_fields_by_concept(self, concept: str) -> List[FieldSpec]:
        """Get all fields mapped to a specific concept."""
        result = []
        for field in self.fields:
            if field.maps_to == concept:
                result.append(field)
            for nested in field.nested_fields:
                if nested.maps_to == concept:
                    result.append(nested)
        return result

    def get_all_field_paths(self) -> List[str]:
        """Get all field paths in this index."""
        paths = []
        for field in self.fields:
            paths.extend(field.get_all_paths())
        return paths


class RelationshipType(str, Enum):
    """Types of relationships between concepts."""
    HAS_ONE = "HAS_ONE"           # One-to-one relationship
    HAS_MANY = "HAS_MANY"         # One-to-many relationship
    BELONGS_TO = "BELONGS_TO"     # Many-to-one (inverse of HAS_ONE/MANY)
    MANY_TO_MANY = "MANY_TO_MANY" # Many-to-many relationship
    CONTAINS = "CONTAINS"         # Hierarchical containment
    REFERENCES = "REFERENCES"     # Generic reference (FK)


class ConceptRelationship(BaseModel):
    """
    Explicit relationship between concepts.

    Specifies cardinality and the field that creates the relationship.

    Example YAML:
        relationships:
          - target: spendcategory
            type: HAS_ONE
            via_field: SpendCategory
    """
    target: str = Field(..., description="Target concept name")
    type: RelationshipType = Field(..., description="Relationship type")
    via_field: Optional[str] = Field(None, description="Field that creates this relationship")
    description: Optional[str] = Field(None, description="Human-readable description")
    inverse_name: Optional[str] = Field(None, description="Name of inverse relationship")

    @field_validator('type', mode='before')
    @classmethod
    def validate_type(cls, v):
        """Convert string to RelationshipType enum."""
        if isinstance(v, str):
            return RelationshipType(v.upper())
        return v

    @field_validator('target')
    @classmethod
    def normalize_target(cls, v: str) -> str:
        """Ensure target concept names are lowercase."""
        return v.lower().strip()


class ConceptSpec(BaseModel):
    """
    Specification for a business concept.

    Concepts represent domain entities (order, customer, product) that
    fields map to. They enable semantic navigation of the schema.

    Enhanced with:
    - value_synonyms: Maps canonical field values to user synonyms
    - related_pronouns: Pronouns that reference this concept
    - synonyms: Alternative names for the concept entity itself
    - relationships: Explicit typed relationships to other concepts
    """
    name: str = Field(..., description="Concept name (lowercase)")
    description: Optional[str] = Field(None, description="Business meaning")

    # Semantic helpers
    aliases: List[str] = Field(default_factory=list, description="Alternative names/synonyms")
    related_to: List[str] = Field(
        default_factory=list,
        description="DEPRECATED: Use 'relationships'. Simple list of related concept names."
    )

    # Explicit typed relationships
    relationships: List[ConceptRelationship] = Field(
        default_factory=list,
        description="Explicit relationships to other concepts"
    )

    # Enhanced semantic enrichment
    synonyms: List[str] = Field(
        default_factory=list,
        description="Synonyms for the concept name"
    )
    value_synonyms: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Maps canonical values to synonyms"
    )
    related_pronouns: List[str] = Field(
        default_factory=list,
        description="Pronouns/phrases that reference this concept"
    )

    # Auto-suggestion metadata
    auto_suggested: bool = Field(False, description="Was this concept auto-suggested")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Suggestion confidence")
    source_patterns: List[str] = Field(
        default_factory=list,
        description="Field patterns that suggested this concept"
    )

    @field_validator('aliases', 'related_to', 'synonyms', 'related_pronouns', 'source_patterns', mode='before')
    @classmethod
    def convert_none_to_list(cls, v):
        """Convert None to empty list."""
        return v if v is not None else []

    @field_validator('value_synonyms', mode='before')
    @classmethod
    def convert_none_to_dict(cls, v):
        """Convert None to empty dict."""
        return v if v is not None else {}

    @field_validator('name')
    @classmethod
    def normalize_name(cls, v: str) -> str:
        """Ensure concept names are lowercase."""
        return v.lower().strip()

    @field_validator('aliases', 'related_to')
    @classmethod
    def normalize_string_lists(cls, v: List[str]) -> List[str]:
        """Normalize string list values to lowercase."""
        return [s.lower().strip() for s in v] if v else []

    def get_canonical_value(self, synonym: str) -> Optional[str]:
        """
        Find the canonical value for a synonym.

        Args:
            synonym: A value synonym to look up (case-insensitive)

        Returns:
            The canonical value if found, None otherwise
        """
        synonym_lower = synonym.lower()
        for canonical, synonyms in self.value_synonyms.items():
            if synonym_lower == canonical.lower():
                return canonical
            if synonym_lower in [s.lower() for s in synonyms]:
                return canonical
        return None

    def matches_pronoun(self, text: str) -> bool:
        """
        Check if any related pronoun appears in the text.

        Args:
            text: Text to search for pronouns

        Returns:
            True if a related pronoun is found
        """
        text_lower = text.lower()
        for pronoun in self.related_pronouns:
            if pronoun.lower() in text_lower:
                return True
        return False


class QAExampleSpec(BaseModel):
    """
    A question-answer example for context enrichment.

    Optional but useful for providing query generation hints.
    """
    question: str = Field(..., description="Natural language question")
    query: str = Field(..., description="Query (PPL/DSL/SQL)")

    # Semantic links
    concepts_used: List[str] = Field(default_factory=list, description="Concepts involved")
    fields_used: List[str] = Field(default_factory=list, description="Fields referenced")

    # Metadata
    verified: bool = Field(False, description="Has been verified as correct")
    source: Optional[str] = Field(None, description="Where this example came from")


class YAMLSchemaV1(BaseModel):
    """
    Root schema for the YAML configuration file.

    This is the main document format for storing index schemas,
    business concepts, and their relationships.
    
    UNIFIED SCHEMA DESIGN:
    - concepts[] are SHARED across all data sources
    - indices[] for OpenSearch data
    - endpoints[] for REST API data
    - schema_type indicates primary or mixed usage
    """
    # Schema metadata
    version: str = Field("1.0", description="Schema format version")
    tenant_id: str = Field(..., description="Tenant identifier")
    schema_type: SchemaType = Field(
        SchemaType.OPENSEARCH,
        description="Primary schema type"
    )
    last_synced: Optional[datetime] = Field(None, description="Last sync with data source")

    # SHARED semantic layer
    concepts: List[ConceptSpec] = Field(
        default_factory=list,
        description="Business concepts - SHARED across all data sources"
    )

    # OpenSearch data source
    indices: List[IndexSpec] = Field(
        default_factory=list,
        description="OpenSearch indices with field mappings"
    )
    
    # REST API data source
    endpoints: List[Any] = Field(  # Using Any to avoid circular import
        default_factory=list,
        description="REST API endpoints with parameters"
    )

    # Optional Q&A examples
    examples: List[QAExampleSpec] = Field(
        default_factory=list,
        description="Question-query pairs for context enrichment"
    )

    model_config = ConfigDict(use_enum_values=True)
    
    @field_validator('schema_type', mode='before')
    @classmethod
    def validate_schema_type(cls, v):
        """Convert string to SchemaType enum."""
        if isinstance(v, str):
            return SchemaType(v.lower())
        return v

    # === LOOKUP METHODS ===

    def get_index(self, name: str) -> Optional[IndexSpec]:
        """Get an index by name or pattern."""
        for idx in self.indices:
            if idx.name == name:
                return idx
        return None

    def get_concept(self, name: str) -> Optional[ConceptSpec]:
        """Get a concept by name."""
        name_lower = name.lower()
        for concept in self.concepts:
            if concept.name == name_lower:
                return concept
        return None

    def get_concept_by_alias(self, alias: str) -> Optional[ConceptSpec]:
        """Find a concept by one of its aliases."""
        alias_lower = alias.lower()
        for concept in self.concepts:
            if alias_lower in concept.aliases or alias_lower == concept.name:
                return concept
        return None

    def get_all_concept_names(self) -> Set[str]:
        """Get all concept names including aliases."""
        names = set()
        for concept in self.concepts:
            names.add(concept.name)
            names.update(concept.aliases)
        return names

    def get_fields_for_concept(self, concept_name: str) -> List[FieldSpec]:
        """Get all fields across all indices mapped to a concept."""
        result = []
        for idx in self.indices:
            result.extend(idx.get_fields_by_concept(concept_name))
        return result

    def get_concept_by_synonym(self, synonym: str) -> Optional[ConceptSpec]:
        """Find a concept by one of its synonyms."""
        synonym_lower = synonym.lower()
        for concept in self.concepts:
            if synonym_lower in [s.lower() for s in concept.synonyms]:
                return concept
        return None

    def find_concepts_by_value(self, value: str) -> List[tuple]:
        """
        Find concepts where the value is a known synonym.

        Returns:
            List of (concept, canonical_value, is_exact_match) tuples
        """
        results = []
        for concept in self.concepts:
            canonical = concept.get_canonical_value(value)
            if canonical:
                is_exact = value.lower() == canonical.lower()
                results.append((concept, canonical, is_exact))
        return results

    def find_concepts_by_pronoun(self, text: str) -> List[ConceptSpec]:
        """Find concepts whose related pronouns appear in the text."""
        return [c for c in self.concepts if c.matches_pronoun(text)]

    # === UNIFIED DATA SOURCE METHODS ===
    
    def has_opensearch(self) -> bool:
        """Check if schema contains OpenSearch indices."""
        return len(self.indices) > 0
    
    def has_api(self) -> bool:
        """Check if schema contains REST API endpoints."""
        return len(self.endpoints) > 0
    
    def get_data_source_types(self) -> List[SchemaType]:
        """Get all data source types present in this schema."""
        types = []
        if self.indices:
            types.append(SchemaType.OPENSEARCH)
        if self.endpoints:
            types.append(SchemaType.REST_API)
        return types

    # === YAML PERSISTENCE ===

    def to_yaml(self, path: Path) -> None:
        """Save schema to YAML file."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_yaml_string())

    def to_yaml_string(self, for_editing: bool = True) -> str:
        """
        Convert schema to YAML string.

        Args:
            for_editing: If True, format for human editing
        """
        if not for_editing:
            data = self.model_dump(exclude_none=True, mode='json')
            return yaml.dump(data, sort_keys=False, allow_unicode=True,
                           default_flow_style=False, width=120)

        # Build clean structure for human editing
        data: Dict[str, Any] = {
            'version': self.version,
            'tenant_id': self.tenant_id,
        }

        # === CONCEPTS ===
        if self.concepts:
            data['concepts'] = []
            for concept in self.concepts:
                entry: Dict[str, Any] = {'name': concept.name}
                if concept.description:
                    entry['description'] = concept.description
                if concept.aliases:
                    entry['aliases'] = concept.aliases
                if concept.synonyms:
                    entry['synonyms'] = concept.synonyms
                if concept.value_synonyms:
                    entry['value_synonyms'] = concept.value_synonyms
                if concept.related_pronouns:
                    entry['related_pronouns'] = concept.related_pronouns
                if concept.related_to:
                    entry['related_to'] = concept.related_to
                data['concepts'].append(entry)

        # === INDICES ===
        if self.indices:
            data['indices'] = []
            for index in self.indices:
                index_data: Dict[str, Any] = {'name': index.name}
                if index.description:
                    index_data['description'] = index.description

                if index.fields:
                    index_data['fields'] = []
                    for field in index.fields:
                        field_data: Dict[str, Any] = {
                            'path': field.path,
                            'es_type': field.es_type,
                        }
                        if field.description:
                            field_data['description'] = field.description
                        if field.maps_to:
                            field_data['maps_to'] = field.maps_to
                        if field.value_examples:
                            field_data['value_examples'] = field.value_examples
                        if field.aliases:
                            field_data['aliases'] = field.aliases
                        if field.allowed_values:
                            field_data['allowed_values'] = field.allowed_values
                        if field.value_synonyms:
                            field_data['value_synonyms'] = field.value_synonyms
                        if field.pii:
                            field_data['pii'] = True
                        index_data['fields'].append(field_data)

                data['indices'].append(index_data)

        yaml_str = yaml.dump(
            data,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=120
        )

        # Add header comment
        header = """# ContextForge Schema - Edit this file to enrich field metadata
#
# CONCEPTS: Business entities that fields map to
#   - name: concept name (lowercase)
#   - description: what this entity represents
#   - aliases: [alt_name] alternative names users might say
#   - value_synonyms: {CanonicalValue: [synonym1, synonym2]}
#   - related_pronouns: [my, mine] for user-owned entities
#
# FIELDS: Nested fields are flattened with full dot-notation paths
#   - path: field path, e.g., customer.address.city (required)
#   - es_type: Field type (required)
#   - description: human-readable description
#   - maps_to: concept name this field belongs to
#   - pii: true if contains personal data
#
"""
        return header + yaml_str

    @classmethod
    def from_yaml(cls, path: Path) -> "YAMLSchemaV1":
        """Load schema from YAML file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    @classmethod
    def from_yaml_string(cls, yaml_string: str) -> "YAMLSchemaV1":
        """Load schema from YAML string."""
        data = yaml.safe_load(yaml_string)
        return cls.model_validate(data)

    @classmethod
    def create_empty(cls, tenant_id: str) -> "YAMLSchemaV1":
        """Create a new empty schema for a tenant."""
        return cls(
            tenant_id=tenant_id,
            last_synced=datetime.now(),
            concepts=[],
            indices=[],
            examples=[]
        )

    # === MERGE OPERATIONS ===

    def merge_index(self, new_index: IndexSpec, preserve_annotations: bool = True) -> None:
        """
        Merge a new/updated index into the schema.

        Merge rules:
        - New fields: Add with null annotations
        - Existing fields: Preserve human annotations, update es_type
        - Removed fields: Keep in schema (explicit deletion required)
        """
        existing = self.get_index(new_index.name)

        if existing is None:
            self.indices.append(new_index)
            return

        # Build lookup of existing fields
        existing_fields: Dict[str, FieldSpec] = {}
        for field in existing.fields:
            existing_fields[field.path] = field
            for nested in field.nested_fields:
                existing_fields[nested.path] = nested

        # Merge fields
        merged_fields: List[FieldSpec] = []
        for new_field in new_index.fields:
            if new_field.path in existing_fields:
                old_field = existing_fields[new_field.path]
                if preserve_annotations:
                    merged_field = FieldSpec(
                        path=new_field.path,
                        es_type=new_field.es_type,
                        description=old_field.description,
                        maps_to=old_field.maps_to,
                        aliases=old_field.aliases,
                        pii=old_field.pii,
                        searchable=old_field.searchable,
                        aggregatable=old_field.aggregatable,
                        is_required=old_field.is_required,
                        is_indexed=old_field.is_indexed,
                        human_edited=old_field.human_edited,
                        nested_fields=new_field.nested_fields,
                        auto_imported=True,
                        last_updated=datetime.now()
                    )
                else:
                    merged_field = new_field
                merged_fields.append(merged_field)
            else:
                new_field.auto_imported = True
                new_field.last_updated = datetime.now()
                merged_fields.append(new_field)

        existing.fields = merged_fields
        existing.description = new_index.description or existing.description
        self.last_synced = datetime.now()

    def add_concept(self, concept: ConceptSpec) -> None:
        """Add a concept if it doesn't already exist."""
        if self.get_concept(concept.name) is None:
            self.concepts.append(concept)

    def link_field_to_concept(self, field_path: str, concept_name: str) -> bool:
        """
        Link a field to a concept across all indices.

        Returns True if the field was found and linked.
        """
        found = False
        for idx in self.indices:
            field = idx.get_field(field_path)
            if field:
                field.maps_to = concept_name
                found = True
        return found


# Enable forward references for nested FieldSpec
FieldSpec.model_rebuild()
