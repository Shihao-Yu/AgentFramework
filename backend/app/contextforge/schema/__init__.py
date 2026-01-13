"""
ContextForge Schema Types.

This module provides schema definitions for representing data source metadata:
- FieldSpec: Field metadata for any data source (SQL, OpenSearch, REST API)
- ExampleSpec: Q&A examples for few-shot learning with graph integration
- YAMLSchemaV1: Root schema format for storing index/endpoint configurations
- API Schema: REST API endpoint and parameter specifications

These types are the foundation for:
- Schema retrieval in the RAG pipeline
- Graph-based field relationships
- Query generation context
- Unified data source abstraction
"""

from .field_schema import (
    FieldSpec,
    FieldType,
    SourceType,
    # Backward compatibility
    LangfuseFieldMetadata,
)
from .example_schema import (
    ExampleSpec,
    ExampleContent,
    # Backward compatibility
    LangfuseQAExample,
)
from .yaml_schema import (
    YAMLSchemaV1,
    IndexSpec,
    ConceptSpec,
    ConceptRelationship,
    RelationshipType,
    QAExampleSpec,
    QueryMode,
    SchemaType,
)
from .api_schema import (
    EndpointSpec,
    ParameterSpec,
    ParameterLocation,
    HTTPMethod,
    ResponseFieldSpec,
    RequestBodySpec,
    APISchemaInfo,
    SecuritySchemeSpec,
)
from .node_mapping import (
    ContextForgeNodeType,
    ContextForgeEdgeType,
    field_spec_to_node_content,
    node_content_to_field_spec,
    concept_spec_to_node_content,
    node_content_to_concept_spec,
    example_spec_to_node_content,
    node_content_to_example_spec,
    create_field_node_data,
    create_concept_node_data,
    create_example_node_data,
    is_contextforge_node,
    get_contextforge_schema_type,
)

__all__ = [
    # Field Schema
    "FieldSpec",
    "FieldType",
    "SourceType",
    "LangfuseFieldMetadata",
    # Example Schema
    "ExampleSpec",
    "ExampleContent",
    "LangfuseQAExample",
    # YAML Schema
    "YAMLSchemaV1",
    "IndexSpec",
    "ConceptSpec",
    "ConceptRelationship",
    "RelationshipType",
    "QAExampleSpec",
    "QueryMode",
    "SchemaType",
    # API Schema
    "EndpointSpec",
    "ParameterSpec",
    "ParameterLocation",
    "HTTPMethod",
    "ResponseFieldSpec",
    "RequestBodySpec",
    "APISchemaInfo",
    "SecuritySchemeSpec",
    # Node Mapping
    "ContextForgeNodeType",
    "ContextForgeEdgeType",
    "field_spec_to_node_content",
    "node_content_to_field_spec",
    "concept_spec_to_node_content",
    "node_content_to_concept_spec",
    "example_spec_to_node_content",
    "node_content_to_example_spec",
    "create_field_node_data",
    "create_concept_node_data",
    "create_example_node_data",
    "is_contextforge_node",
    "get_contextforge_schema_type",
]
