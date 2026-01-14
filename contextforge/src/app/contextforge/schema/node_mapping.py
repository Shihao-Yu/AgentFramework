"""
Node Mapping Utilities for ContextForge.

Provides bidirectional mapping between ContextForge schema types and
Knowledge Verse database models (KnowledgeNode, KnowledgeEdge).

This module enables:
- Storing FieldSpec/ConceptSpec as KnowledgeNodes
- Reconstructing schema types from database records
- Building graph relationships from schema definitions
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.nodes import KnowledgeNode
    from .field_schema import FieldSpec, FieldType, SourceType
    from .yaml_schema import ConceptSpec, IndexSpec
    from .example_schema import ExampleSpec


# Node type constants for ContextForge data
class ContextForgeNodeType:
    """Node types used by ContextForge in KnowledgeNode."""
    
    FIELD = "contextforge_field"
    CONCEPT = "contextforge_concept"
    EXAMPLE = "contextforge_example"
    INDEX = "contextforge_index"
    ENDPOINT = "contextforge_endpoint"


# Edge type constants for ContextForge relationships
class ContextForgeEdgeType:
    """Edge types used by ContextForge in KnowledgeEdge."""
    
    # Field relationships
    FIELD_MAPS_TO_CONCEPT = "MAPS_TO"
    FIELD_RELATED_TO = "RELATED_TO"
    FIELD_BELONGS_TO_INDEX = "BELONGS_TO"
    
    # Concept relationships
    CONCEPT_HAS_ONE = "HAS_ONE"
    CONCEPT_HAS_MANY = "HAS_MANY"
    CONCEPT_BELONGS_TO = "BELONGS_TO"
    CONCEPT_REFERENCES = "REFERENCES"
    
    # Example relationships
    EXAMPLE_DEMONSTRATES = "DEMONSTRATES"
    EXAMPLE_USES_FIELD = "USES_FIELD"
    EXAMPLE_HAS_VARIANT = "HAS_VARIANT"


def field_spec_to_node_content(field: "FieldSpec") -> Dict[str, Any]:
    """
    Convert FieldSpec to KnowledgeNode content JSON.
    
    The content field stores the full FieldSpec data that can be
    reconstructed later.
    
    Args:
        field: FieldSpec instance
        
    Returns:
        Dict suitable for KnowledgeNode.content
    """
    return {
        # Core identity
        "name": field.name,
        "qualified_name": field.qualified_name,
        "type": str(field.type) if field.type else None,
        "nullable": field.nullable,
        
        # Business context
        "description": field.description,
        "business_meaning": field.business_meaning,
        
        # Schema linking
        "maps_to": field.maps_to,
        "aliases": field.aliases,
        "related_fields": field.related_fields,
        
        # Value information
        "allowed_values": field.allowed_values,
        "value_synonyms": field.value_synonyms,
        "value_examples": field.value_examples,
        "value_patterns": field.value_patterns,
        "value_encoding": field.value_encoding,
        
        # Query hints
        "searchable": field.searchable,
        "filterable": field.filterable,
        "sortable": field.sortable,
        "aggregatable": field.aggregatable,
        "search_guidance": field.search_guidance,
        "common_filters": field.common_filters,
        "aggregation_hints": field.aggregation_hints,
        
        # Source info
        "source_type": str(field.source_type) if field.source_type else None,
        "index_name": field.index_name,
        "parent_entity": field.parent_entity,
        
        # Metadata
        "is_required": field.is_required,
        "is_indexed": field.is_indexed,
        "is_sensitive": field.is_sensitive,
        "is_primary_key": field.is_primary_key,
        "human_edited": field.human_edited,
        "last_modified": field.last_modified.isoformat() if field.last_modified else None,
        "modified_by": field.modified_by,
        
        # Schema version marker
        "_contextforge_version": "1.0",
        "_schema_type": "field_spec",
    }


def node_content_to_field_spec(content: Dict[str, Any]) -> "FieldSpec":
    """
    Reconstruct FieldSpec from KnowledgeNode content.
    
    Args:
        content: KnowledgeNode.content dict
        
    Returns:
        Reconstructed FieldSpec instance
    """
    from .field_schema import FieldSpec, FieldType, SourceType
    
    # Parse type enum
    field_type = content.get("type")
    if field_type:
        try:
            field_type = FieldType(field_type)
        except ValueError:
            field_type = field_type  # Keep as string if not valid enum
    
    # Parse source type enum
    source_type = content.get("source_type")
    if source_type:
        try:
            source_type = SourceType(source_type)
        except ValueError:
            source_type = source_type
    
    # Parse datetime
    last_modified = content.get("last_modified")
    if last_modified and isinstance(last_modified, str):
        last_modified = datetime.fromisoformat(last_modified)
    
    return FieldSpec(
        name=content.get("name", ""),
        qualified_name=content.get("qualified_name"),
        type=field_type or FieldType.STRING,
        nullable=content.get("nullable", True),
        description=content.get("description"),
        business_meaning=content.get("business_meaning"),
        maps_to=content.get("maps_to", []),
        aliases=content.get("aliases", []),
        related_fields=content.get("related_fields", []),
        allowed_values=content.get("allowed_values", []),
        value_synonyms=content.get("value_synonyms", {}),
        value_examples=content.get("value_examples", []),
        value_patterns=content.get("value_patterns"),
        value_encoding=content.get("value_encoding"),
        searchable=content.get("searchable", True),
        filterable=content.get("filterable", True),
        sortable=content.get("sortable", True),
        aggregatable=content.get("aggregatable", False),
        search_guidance=content.get("search_guidance"),
        common_filters=content.get("common_filters", []),
        aggregation_hints=content.get("aggregation_hints"),
        source_type=source_type or SourceType.UNKNOWN,
        index_name=content.get("index_name"),
        parent_entity=content.get("parent_entity"),
        is_required=content.get("is_required", False),
        is_indexed=content.get("is_indexed", False),
        is_sensitive=content.get("is_sensitive", False),
        is_primary_key=content.get("is_primary_key", False),
        human_edited=content.get("human_edited", False),
        last_modified=last_modified,
        modified_by=content.get("modified_by"),
    )


def concept_spec_to_node_content(concept: "ConceptSpec") -> Dict[str, Any]:
    """
    Convert ConceptSpec to KnowledgeNode content JSON.
    
    Args:
        concept: ConceptSpec instance
        
    Returns:
        Dict suitable for KnowledgeNode.content
    """
    # Convert relationships to serializable format
    relationships_data = []
    for rel in concept.relationships:
        relationships_data.append({
            "target": rel.target,
            "type": str(rel.type),
            "via_field": rel.via_field,
            "description": rel.description,
            "inverse_name": rel.inverse_name,
        })
    
    return {
        "name": concept.name,
        "description": concept.description,
        "aliases": concept.aliases,
        "synonyms": concept.synonyms,
        "value_synonyms": concept.value_synonyms,
        "related_pronouns": concept.related_pronouns,
        "related_to": concept.related_to,
        "relationships": relationships_data,
        "auto_suggested": concept.auto_suggested,
        "confidence": concept.confidence,
        "source_patterns": concept.source_patterns,
        
        "_contextforge_version": "1.0",
        "_schema_type": "concept_spec",
    }


def node_content_to_concept_spec(content: Dict[str, Any]) -> "ConceptSpec":
    """
    Reconstruct ConceptSpec from KnowledgeNode content.
    
    Args:
        content: KnowledgeNode.content dict
        
    Returns:
        Reconstructed ConceptSpec instance
    """
    from .yaml_schema import ConceptSpec, ConceptRelationship, RelationshipType
    
    # Parse relationships
    relationships = []
    for rel_data in content.get("relationships", []):
        rel_type = rel_data.get("type")
        try:
            rel_type = RelationshipType(rel_type.upper())
        except (ValueError, AttributeError):
            rel_type = RelationshipType.REFERENCES
        
        relationships.append(ConceptRelationship(
            target=rel_data.get("target", ""),
            type=rel_type,
            via_field=rel_data.get("via_field"),
            description=rel_data.get("description"),
            inverse_name=rel_data.get("inverse_name"),
        ))
    
    return ConceptSpec(
        name=content.get("name", ""),
        description=content.get("description"),
        aliases=content.get("aliases", []),
        synonyms=content.get("synonyms", []),
        value_synonyms=content.get("value_synonyms", {}),
        related_pronouns=content.get("related_pronouns", []),
        related_to=content.get("related_to", []),
        relationships=relationships,
        auto_suggested=content.get("auto_suggested", False),
        confidence=content.get("confidence", 1.0),
        source_patterns=content.get("source_patterns", []),
    )


def example_spec_to_node_content(example: "ExampleSpec") -> Dict[str, Any]:
    """
    Convert ExampleSpec to KnowledgeNode content JSON.
    
    Args:
        example: ExampleSpec instance
        
    Returns:
        Dict suitable for KnowledgeNode.content
    """
    return {
        "id": example.id,
        "title": example.title,
        "description": example.description,
        "variants": example.variants,
        
        # Content
        "query": example.content.query,
        "query_type": example.content.query_type,
        "explanation": example.content.explanation,
        
        # Schema linking
        "linked_concepts": example.linked_concepts,
        "linked_fields": example.linked_fields,
        "linked_values": example.linked_values,
        "additional_context": example.additional_context,
        
        # Metadata
        "verified": example.verified,
        "source": example.source,
        "tags": example.tags,
        "created_at": example.created_at.isoformat() if example.created_at else None,
        "updated_at": example.updated_at.isoformat() if example.updated_at else None,
        "usage_count": example.usage_count,
        
        "_contextforge_version": "1.0",
        "_schema_type": "example_spec",
    }


def node_content_to_example_spec(content: Dict[str, Any]) -> "ExampleSpec":
    """
    Reconstruct ExampleSpec from KnowledgeNode content.
    
    Args:
        content: KnowledgeNode.content dict
        
    Returns:
        Reconstructed ExampleSpec instance
    """
    from .example_schema import ExampleSpec, ExampleContent
    
    # Parse datetimes
    created_at = content.get("created_at")
    if created_at and isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    
    updated_at = content.get("updated_at")
    if updated_at and isinstance(updated_at, str):
        updated_at = datetime.fromisoformat(updated_at)
    
    return ExampleSpec(
        id=content.get("id", ""),
        title=content.get("title", ""),
        description=content.get("description"),
        variants=content.get("variants", []),
        content=ExampleContent(
            query=content.get("query", ""),
            query_type=content.get("query_type", "sql"),
            explanation=content.get("explanation"),
        ),
        linked_concepts=content.get("linked_concepts", []),
        linked_fields=content.get("linked_fields", []),
        linked_values=content.get("linked_values", {}),
        additional_context=content.get("additional_context"),
        verified=content.get("verified", False),
        source=content.get("source", "user_provided"),
        tags=content.get("tags", []),
        created_at=created_at or datetime.utcnow(),
        updated_at=updated_at,
        usage_count=content.get("usage_count", 0),
    )


def create_field_node_data(
    field: "FieldSpec",
    tenant_id: str,
    dataset_name: str,
) -> Dict[str, Any]:
    """
    Create a dict with all data needed to create a KnowledgeNode for a field.
    
    This returns a dict that can be used with KnowledgeNode(**data) or
    as kwargs to a repository create method.
    
    Args:
        field: FieldSpec instance
        tenant_id: Tenant ID for isolation
        dataset_name: Name of the dataset this field belongs to
        
    Returns:
        Dict with KnowledgeNode field values
    """
    from app.models.enums import NodeType
    
    # Build tags from field metadata
    tags = list(field.aliases)
    if field.maps_to:
        tags.extend(field.maps_to)
    
    return {
        "tenant_id": tenant_id,
        "node_type": NodeType.FIELD,  # Using existing NodeType enum
        "title": field.full_name,
        "summary": field.description or f"Field: {field.full_name}",
        "content": field_spec_to_node_content(field),
        "tags": tags,
        "dataset_name": dataset_name,
        "field_path": field.qualified_name or field.name,
        "data_type": str(field.type) if field.type else None,
        "source": "contextforge",
    }


def create_concept_node_data(
    concept: "ConceptSpec",
    tenant_id: str,
    dataset_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a dict with all data needed to create a KnowledgeNode for a concept.
    
    Args:
        concept: ConceptSpec instance
        tenant_id: Tenant ID for isolation
        dataset_name: Optional dataset name
        
    Returns:
        Dict with KnowledgeNode field values
    """
    from app.models.enums import NodeType
    
    # Build tags from concept metadata
    tags = list(concept.aliases) + list(concept.synonyms)
    
    return {
        "tenant_id": tenant_id,
        "node_type": NodeType.CONCEPT,
        "title": concept.name,
        "summary": concept.description or f"Concept: {concept.name}",
        "content": concept_spec_to_node_content(concept),
        "tags": tags,
        "dataset_name": dataset_name,
        "source": "contextforge",
    }


def create_example_node_data(
    example: "ExampleSpec",
    tenant_id: str,
    dataset_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a dict with all data needed to create a KnowledgeNode for an example.
    
    Args:
        example: ExampleSpec instance
        tenant_id: Tenant ID for isolation
        dataset_name: Optional dataset name
        
    Returns:
        Dict with KnowledgeNode field values
    """
    from app.models.enums import NodeType
    
    return {
        "tenant_id": tenant_id,
        "node_type": NodeType.EXAMPLE,
        "title": example.title,
        "summary": example.description or example.title,
        "content": example_spec_to_node_content(example),
        "tags": example.tags + example.linked_concepts,
        "dataset_name": dataset_name,
        "source": "contextforge",
    }


def is_contextforge_node(content: Dict[str, Any]) -> bool:
    """
    Check if a KnowledgeNode content was created by ContextForge.
    
    Args:
        content: KnowledgeNode.content dict
        
    Returns:
        True if this is a ContextForge-managed node
    """
    return content.get("_contextforge_version") is not None


def get_contextforge_schema_type(content: Dict[str, Any]) -> Optional[str]:
    """
    Get the ContextForge schema type from node content.
    
    Args:
        content: KnowledgeNode.content dict
        
    Returns:
        Schema type string ("field_spec", "concept_spec", "example_spec") or None
    """
    return content.get("_schema_type")
