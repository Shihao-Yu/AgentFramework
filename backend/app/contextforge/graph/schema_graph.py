"""
Schema Graph for Index/Field/Concept Relationships

A NetworkX-based graph that represents schema structure with:
- Index nodes (index patterns)
- Field nodes (with dot-notation paths)
- Concept nodes (business entities)

Edges connect these nodes to enable semantic traversal:
- HAS_FIELD: Index -> Field
- NESTED_IN: Field -> Parent Field
- MAPS_TO: Field -> Concept
- RELATES_TO: Concept -> Concept
- ALIAS_OF: Field/Concept -> Alias

This enables context retrieval by:
1. Matching keywords to concepts
2. Traversing to find related fields
3. Loading field metadata for query generation
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

try:
    import networkx as nx
except ImportError:
    raise ImportError(
        "networkx is required for schema graph. Install with: pip install networkx"
    )

from ..schema.yaml_schema import (
    ConceptSpec,
    IndexSpec,
    YAMLSchemaV1,
)
from ..schema.field_schema import FieldSpec
from ..schema.api_schema import EndpointSpec, ParameterSpec, ResponseFieldSpec

if TYPE_CHECKING:
    from ..schema.example_schema import ExampleSpec

logger = logging.getLogger(__name__)


class NodeType:
    """Node types in the schema graph"""
    INDEX = "index"
    FIELD = "field"
    CONCEPT = "concept"
    ALIAS = "alias"
    VALUE = "value"       # Canonical value node for value_synonyms
    EXAMPLE = "example"   # Q&A example node
    ENDPOINT = "endpoint" # REST API endpoint node
    PARAM = "param"       # REST API parameter node
    RESPONSE_FIELD = "response_field"  # REST API response field node


class EdgeType:
    """Edge types in the schema graph"""
    HAS_FIELD = "has_field"       # Index -> Field
    NESTED_IN = "nested_in"       # Nested Field -> Parent Field
    MAPS_TO = "maps_to"           # Field -> Concept
    RELATES_TO = "relates_to"     # Concept -> Concept
    ALIAS_OF = "alias_of"         # Alias -> Field/Concept
    HAS_VALUE = "has_value"       # Concept -> Value (canonical values)
    SYNONYM_OF = "synonym_of"     # Alias -> Value (value synonyms)
    DEMONSTRATES = "demonstrates" # Example -> Concept
    USES_FIELD = "uses_field"     # Example -> Field
    USES_VALUE = "uses_value"     # Example -> Value
    HAS_VARIANT = "has_variant"   # Example -> Variant keyword alias
    HAS_PARAM = "has_param"       # Endpoint -> Param
    ENDPOINT_MAPS_TO = "endpoint_maps_to"  # Endpoint -> Concept
    PATH_CONTAINS = "path_contains"  # Endpoint -> path segment alias
    RETURNS = "returns"           # Endpoint -> Response Field
    RESPONSE_MAPS_TO = "response_maps_to"  # Response Field -> Concept


@dataclass
class GraphNode:
    """Node data in the schema graph"""
    id: str
    node_type: str  # NodeType value
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Result from graph search operations"""
    matched_concepts: List[Tuple[str, float]]  # (concept_name, score)
    matched_fields: List[str]  # field paths
    expanded_fields: Set[str]  # all reachable fields
    adjacency: Dict[str, List[Tuple[str, str]]]  # node -> [(neighbor, edge_type)]
    traversal_path: List[str]  # nodes visited during traversal
    hop_count: int
    field_scores: Dict[str, float] = field(default_factory=dict)  # field_path -> score
    matched_endpoint_keys: Set[str] = field(default_factory=set)  # "METHOD:/path" keys


class SchemaGraph:
    """
    NetworkX graph for schema relationships with semantic search.

    Builds a graph from YAMLSchemaV1 with nodes for indices, fields,
    and concepts. Supports multiple search strategies:
    - Concept-based: keyword -> concept -> fields
    - Field-based: field path -> related fields
    - Hybrid: concept first, field fallback

    Example:
        >>> graph = SchemaGraph()
        >>> graph.load_from_yaml(Path("schema.yaml"))
        >>> result = graph.find_fields_by_concept("customer")
        >>> print(result.matched_fields)
        ['customer.id', 'customer.email', 'customer.name']
    """

    def __init__(self):
        """Initialize empty graph"""
        self._graph: nx.DiGraph = nx.DiGraph()
        self._schema: Optional[YAMLSchemaV1] = None

        # Indexes for fast lookup
        self._concept_to_fields: Dict[str, Set[str]] = {}  # concept -> field paths
        self._field_to_concepts: Dict[str, Set[str]] = {}  # field path -> concepts
        self._alias_to_entity: Dict[str, str] = {}  # alias -> concept/field name
        self._index_fields: Dict[str, Set[str]] = {}  # index name -> field paths

        # Value synonym indexes
        self._value_to_concept: Dict[str, Tuple[str, str]] = {}  # value -> (concept, canonical)
        self._concept_to_values: Dict[str, Set[str]] = {}  # concept -> set of canonical values

        # Path segment indexes for REST API endpoint search
        self._path_segment_to_endpoints: Dict[str, Set[str]] = {}  # segment -> {"GET:/path", ...}
        
        # Response field indexes for REST API response search
        self._response_path_to_endpoints: Dict[str, Set[str]] = {}  # "status" -> {"GET:/orders", ...}
        self._concept_to_response_endpoints: Dict[str, Set[str]] = {}  # concept -> endpoint keys

        # Example indexes for fast lookup
        self._concept_to_examples: Dict[str, Set[str]] = {}   # concept -> example_ids
        self._field_to_examples: Dict[str, Set[str]] = {}     # field_path -> example_ids
        self._value_to_examples: Dict[str, Set[str]] = {}     # "field:value" -> example_ids
        self._keyword_to_examples: Dict[str, Set[str]] = {}   # keyword -> example_ids

    @property
    def graph(self) -> nx.DiGraph:
        """Access the underlying NetworkX graph"""
        return self._graph

    @property
    def schema(self) -> Optional[YAMLSchemaV1]:
        """Access the loaded schema"""
        return self._schema

    # === PUBLIC INDEX ACCESS ===

    @property
    def concept_to_fields(self) -> Dict[str, Set[str]]:
        """
        Get concept -> fields mapping (read-only copy).

        Returns a copy to prevent external modification.
        """
        return {k: v.copy() for k, v in self._concept_to_fields.items()}

    @property
    def field_to_concepts(self) -> Dict[str, Set[str]]:
        """
        Get field -> concepts mapping (read-only copy).

        Returns a copy to prevent external modification.
        """
        return {k: v.copy() for k, v in self._field_to_concepts.items()}

    @property
    def index_fields(self) -> Dict[str, Set[str]]:
        """
        Get index -> fields mapping (read-only copy).

        Returns a copy to prevent external modification.
        """
        return {k: v.copy() for k, v in self._index_fields.items()}

    # === GRAPH CONSTRUCTION ===

    def load_from_yaml(self, yaml_path: Path) -> None:
        """
        Build graph from YAML schema file.

        Args:
            yaml_path: Path to YAML schema file
        """
        schema = YAMLSchemaV1.from_yaml(yaml_path)
        self.load_from_schema(schema)
        logger.info(f"Loaded schema graph from {yaml_path}")

    def load_from_schema(self, schema: YAMLSchemaV1) -> None:
        """
        Build graph from YAMLSchemaV1 object.

        Args:
            schema: Parsed YAML schema
        """
        self._schema = schema
        self._graph.clear()
        self._clear_indexes()

        # Add concepts first (they're the semantic anchors)
        for concept in schema.concepts:
            self._add_concept_node(concept)

        # Add indices and their fields
        for index in schema.indices:
            self._add_index_node(index)

        # Add REST API endpoints and their parameters
        for endpoint in schema.endpoints:
            self._add_endpoint_node(endpoint)

        # Add concept relationships (typed and legacy)
        for concept in schema.concepts:
            # Handle typed relationships
            for rel in concept.relationships:
                if self._graph.has_node(f"concept:{rel.target}"):
                    self._graph.add_edge(
                        f"concept:{concept.name}",
                        f"concept:{rel.target}",
                        relation=EdgeType.RELATES_TO,
                        relationship_type=rel.type.value if hasattr(rel.type, 'value') else rel.type,
                        via_field=rel.via_field,
                        description=rel.description,
                    )

            # Handle simple related_to list (backwards compatibility)
            for related in concept.related_to:
                # Skip if already handled via typed relationship
                typed_targets = {r.target for r in concept.relationships}
                if related in typed_targets:
                    continue
                if self._graph.has_node(f"concept:{related}"):
                    self._graph.add_edge(
                        f"concept:{concept.name}",
                        f"concept:{related}",
                        relation=EdgeType.RELATES_TO,
                        relationship_type="REFERENCES",  # Default for legacy
                        via_field=None,
                        description=None,
                    )

        # Add Q&A examples as nodes
        for idx, example in enumerate(schema.examples):
            self._add_example_node(example, idx)

        logger.info(
            f"Built schema graph: {self._graph.number_of_nodes()} nodes, "
            f"{self._graph.number_of_edges()} edges, "
            f"{len(schema.examples)} examples"
        )

    def save_to_yaml(self, yaml_path: Path) -> None:
        """
        Persist current schema to YAML file.

        Args:
            yaml_path: Path to save YAML file
        """
        if self._schema is None:
            raise ValueError("No schema loaded to save")
        self._schema.to_yaml(yaml_path)

    def _clear_indexes(self) -> None:
        """Clear all lookup indexes"""
        self._concept_to_fields.clear()
        self._field_to_concepts.clear()
        self._alias_to_entity.clear()
        self._index_fields.clear()
        self._value_to_concept.clear()
        self._concept_to_values.clear()
        self._path_segment_to_endpoints.clear()
        self._response_path_to_endpoints.clear()
        self._concept_to_response_endpoints.clear()
        # Example indexes
        self._concept_to_examples.clear()
        self._field_to_examples.clear()
        self._value_to_examples.clear()
        self._keyword_to_examples.clear()

    def _add_concept_node(self, concept: ConceptSpec) -> None:
        """Add a concept node with its aliases, synonyms, and value nodes"""
        node_id = f"concept:{concept.name}"
        self._graph.add_node(
            node_id,
            node_type=NodeType.CONCEPT,
            name=concept.name,
            description=concept.description,
            aliases=concept.aliases,
            synonyms=concept.synonyms,
            related_to=concept.related_to,
            related_pronouns=concept.related_pronouns,
            auto_suggested=concept.auto_suggested,
            confidence=concept.confidence,
        )

        # Add alias nodes
        for alias in concept.aliases:
            alias_id = f"alias:{alias}"
            self._graph.add_node(
                alias_id,
                node_type=NodeType.ALIAS,
                name=alias,
                alias_of=concept.name,
            )
            self._graph.add_edge(
                alias_id,
                node_id,
                relation=EdgeType.ALIAS_OF,
            )
            self._alias_to_entity[alias.lower()] = concept.name

        # Add synonym nodes (distinct from aliases - synonyms for concept name itself)
        for synonym in concept.synonyms:
            syn_id = f"alias:{synonym}"
            if not self._graph.has_node(syn_id):
                self._graph.add_node(
                    syn_id,
                    node_type=NodeType.ALIAS,
                    name=synonym,
                    alias_of=concept.name,
                )
                self._graph.add_edge(
                    syn_id,
                    node_id,
                    relation=EdgeType.ALIAS_OF,
                )
            self._alias_to_entity[synonym.lower()] = concept.name

        # Initialize indexes
        self._concept_to_fields[concept.name] = set()
        self._concept_to_values[concept.name] = set()

        # Add value nodes for value_synonyms
        for canonical, synonyms in concept.value_synonyms.items():
            value_id = f"value:{concept.name}:{canonical.lower()}"
            self._graph.add_node(
                value_id,
                node_type=NodeType.VALUE,
                name=canonical,
                concept=concept.name,
                synonyms=synonyms,
            )
            # Edge: Concept -> Value
            self._graph.add_edge(
                node_id,
                value_id,
                relation=EdgeType.HAS_VALUE,
            )

            # Index the canonical value
            self._value_to_concept[canonical.lower()] = (concept.name, canonical)
            self._concept_to_values[concept.name].add(canonical)

            # Add synonym alias nodes for each value synonym
            for syn in synonyms:
                syn_alias_id = f"alias:value:{syn.lower()}"
                if not self._graph.has_node(syn_alias_id):
                    self._graph.add_node(
                        syn_alias_id,
                        node_type=NodeType.ALIAS,
                        name=syn,
                        alias_of=canonical,
                        alias_type="value_synonym",
                    )
                self._graph.add_edge(
                    syn_alias_id,
                    value_id,
                    relation=EdgeType.SYNONYM_OF,
                )
                # Index the synonym
                self._value_to_concept[syn.lower()] = (concept.name, canonical)

    def _add_index_node(self, index: IndexSpec) -> None:
        """Add an index node with its fields"""
        index_id = f"index:{index.name}"
        # Handle query_mode - could be enum or string from YAML
        query_mode_value = index.query_mode
        if hasattr(query_mode_value, 'value'):
            query_mode_value = query_mode_value.value
        elif isinstance(query_mode_value, str):
            query_mode_value = query_mode_value
        else:
            query_mode_value = "PPL"

        self._graph.add_node(
            index_id,
            node_type=NodeType.INDEX,
            name=index.name,
            description=index.description,
            query_mode=query_mode_value,
            primary_key=index.primary_key,
            timestamp_field=index.timestamp_field,
        )

        # Initialize field set for this index
        self._index_fields[index.name] = set()

        # Add fields
        for field_spec in index.fields:
            self._add_field_node(field_spec, index.name)

    def _add_field_node(
        self,
        field_spec: FieldSpec,
        index_name: str,
        parent_field: Optional[str] = None,
    ) -> None:
        """Add a field node with its concept mapping"""
        field_id = f"field:{index_name}:{field_spec.path}"
        self._graph.add_node(
            field_id,
            node_type=NodeType.FIELD,
            name=field_spec.path,
            path=field_spec.path,
            es_type=field_spec.es_type,
            description=field_spec.description,
            maps_to=field_spec.maps_to,
            pii=field_spec.pii,
            searchable=field_spec.searchable,
            aggregatable=field_spec.aggregatable,
            index=index_name,
            # Store the full FieldSpec for typed retrieval
            field_spec=field_spec,
        )

        # Edge: Index -> Field
        self._graph.add_edge(
            f"index:{index_name}",
            field_id,
            relation=EdgeType.HAS_FIELD,
        )

        # Edge: Nested field -> Parent field
        if parent_field:
            parent_id = f"field:{index_name}:{parent_field}"
            self._graph.add_edge(
                field_id,
                parent_id,
                relation=EdgeType.NESTED_IN,
            )

        # Edge: Field -> Concept (if mapped)
        if field_spec.maps_to:
            concept_id = f"concept:{field_spec.maps_to}"
            if self._graph.has_node(concept_id):
                self._graph.add_edge(
                    field_id,
                    concept_id,
                    relation=EdgeType.MAPS_TO,
                )
                # Update indexes
                self._concept_to_fields[field_spec.maps_to].add(field_spec.path)
                if field_spec.path not in self._field_to_concepts:
                    self._field_to_concepts[field_spec.path] = set()
                self._field_to_concepts[field_spec.path].add(field_spec.maps_to)

        # Track in index fields
        self._index_fields[index_name].add(field_spec.path)

        # Add aliases
        for alias in field_spec.aliases:
            alias_id = f"alias:{alias}"
            self._graph.add_node(
                alias_id,
                node_type=NodeType.ALIAS,
                name=alias,
                alias_of=field_spec.path,
            )
            self._graph.add_edge(
                alias_id,
                field_id,
                relation=EdgeType.ALIAS_OF,
            )
            self._alias_to_entity[alias.lower()] = field_spec.path

        # Add field-level value nodes for value_synonyms
        for canonical, synonyms in field_spec.value_synonyms.items():
            value_id = f"value:{field_spec.path}:{canonical.lower()}"
            self._graph.add_node(
                value_id,
                node_type=NodeType.VALUE,
                name=canonical,
                field_path=field_spec.path,
                index=index_name,
                synonyms=synonyms,
                source="field",
            )
            # Edge: Field -> Value
            self._graph.add_edge(
                field_id,
                value_id,
                relation=EdgeType.HAS_VALUE,
            )

            # Index canonical value for lookup
            canonical_lower = canonical.lower()
            self._value_to_concept[canonical_lower] = (field_spec.path, canonical)

            # Add synonym alias nodes
            for syn in synonyms:
                syn_alias_id = f"alias:value:{field_spec.path}:{syn.lower()}"
                if not self._graph.has_node(syn_alias_id):
                    self._graph.add_node(
                        syn_alias_id,
                        node_type=NodeType.ALIAS,
                        name=syn,
                        alias_of=canonical,
                        alias_type="field_value_synonym",
                        field_path=field_spec.path,
                    )
                self._graph.add_edge(
                    syn_alias_id,
                    value_id,
                    relation=EdgeType.SYNONYM_OF,
                )
                # Index synonym for lookup
                self._value_to_concept[syn.lower()] = (field_spec.path, canonical)

        # Add allowed_values as value nodes (if present and no value_synonyms for them)
        if field_spec.allowed_values:
            for allowed in field_spec.allowed_values:
                allowed_lower = allowed.lower()
                # Only add if not already covered by value_synonyms
                if allowed_lower not in [v.lower() for v in field_spec.value_synonyms.keys()]:
                    value_id = f"value:{field_spec.path}:{allowed_lower}"
                    if not self._graph.has_node(value_id):
                        self._graph.add_node(
                            value_id,
                            node_type=NodeType.VALUE,
                            name=allowed,
                            field_path=field_spec.path,
                            index=index_name,
                            synonyms=[],
                            source="allowed_values",
                        )
                        self._graph.add_edge(
                            field_id,
                            value_id,
                            relation=EdgeType.HAS_VALUE,
                        )
                        self._value_to_concept[allowed_lower] = (field_spec.path, allowed)

        # Recursively add nested fields
        for nested in field_spec.nested_fields:
            self._add_field_node(nested, index_name, parent_field=field_spec.path)

    def _add_endpoint_node(self, endpoint: EndpointSpec) -> None:
        """
        Add a REST API endpoint node with its parameters.
        
        Parallels _add_index_node but for REST API endpoints.
        """
        # Create unique endpoint ID using method + path
        method_str = endpoint.method.value if hasattr(endpoint.method, 'value') else str(endpoint.method)
        endpoint_id = f"endpoint:{method_str}:{endpoint.path}"
        
        self._graph.add_node(
            endpoint_id,
            node_type=NodeType.ENDPOINT,
            name=endpoint.path,
            path=endpoint.path,
            method=method_str,
            operation_id=endpoint.operation_id,
            summary=endpoint.summary,
            description=endpoint.description,
            maps_to=endpoint.maps_to,
            tags=endpoint.tags,
            auth_required=endpoint.auth_required,
            deprecated=endpoint.deprecated,
            endpoint_spec=endpoint,
        )
        
        # Initialize field set for this endpoint
        endpoint_key = f"{method_str}:{endpoint.path}"
        self._index_fields[endpoint_key] = set()
        
        # Edge: Endpoint -> Concept (if mapped)
        if endpoint.maps_to:
            concept_id = f"concept:{endpoint.maps_to}"
            if self._graph.has_node(concept_id):
                self._graph.add_edge(
                    endpoint_id,
                    concept_id,
                    relation=EdgeType.ENDPOINT_MAPS_TO,
                )
        
        # Add parameters as PARAM nodes
        for param in endpoint.parameters:
            self._add_param_node(param, endpoint_id, endpoint_key, endpoint.path)
        
        # Add response fields
        for resp_field in endpoint.response_fields:
            self._add_response_field_to_graph(resp_field, endpoint_id, endpoint_key)
        
        # Index path segments for text search
        path_segments = self._extract_path_segments(endpoint.path)
        for segment in path_segments:
            if segment not in self._path_segment_to_endpoints:
                self._path_segment_to_endpoints[segment] = set()
            self._path_segment_to_endpoints[segment].add(endpoint_key)

    def _extract_path_segments(self, path: str) -> List[str]:
        """Extract searchable segments from URL path with word splitting."""
        segments: Set[str] = set()
        
        # Split by / and remove path parameters {xxx}
        raw_segments = [s for s in path.split('/') if s and not s.startswith('{')]
        
        for segment in raw_segments:
            segment_lower = segment.lower()
            
            # Add original segment
            if len(segment_lower) > 2:
                segments.add(segment_lower)
            
            # Split camelCase
            camel_parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', segment)
            for part in camel_parts:
                if len(part) > 2:
                    segments.add(part.lower())
            
            # Split snake_case
            snake_parts = segment_lower.split('_')
            for part in snake_parts:
                if len(part) > 2:
                    segments.add(part)
        
        return list(segments)

    def _add_param_node(
        self,
        param: ParameterSpec,
        endpoint_id: str,
        endpoint_key: str,
        endpoint_path: str,
    ) -> None:
        """Add a REST API parameter node."""
        qualified_name = param.get_qualified_name() if hasattr(param, 'get_qualified_name') else param.name
        param_id = f"param:{endpoint_path}:{qualified_name}"
        
        # Get location value safely
        location_str = param.location.value if hasattr(param.location, 'value') else str(param.location)
        
        self._graph.add_node(
            param_id,
            node_type=NodeType.PARAM,
            name=param.name,
            qualified_name=qualified_name,
            param_type=param.param_type,
            location=location_str,
            description=param.description,
            business_meaning=param.business_meaning,
            maps_to=param.maps_to,
            required=param.required,
            allowed_values=param.allowed_values,
            value_synonyms=param.value_synonyms,
            endpoint_path=endpoint_path,
            param_spec=param,
        )
        
        # Edge: Endpoint -> Param
        self._graph.add_edge(
            endpoint_id,
            param_id,
            relation=EdgeType.HAS_PARAM,
        )
        
        # Edge: Param -> Concept (if mapped)
        if param.maps_to:
            concept_id = f"concept:{param.maps_to}"
            if self._graph.has_node(concept_id):
                self._graph.add_edge(
                    param_id,
                    concept_id,
                    relation=EdgeType.MAPS_TO,
                )
                # Update indexes
                if param.maps_to not in self._concept_to_fields:
                    self._concept_to_fields[param.maps_to] = set()
                self._concept_to_fields[param.maps_to].add(qualified_name)
                if qualified_name not in self._field_to_concepts:
                    self._field_to_concepts[qualified_name] = set()
                self._field_to_concepts[qualified_name].add(param.maps_to)
        
        # Track in endpoint's field set
        self._index_fields[endpoint_key].add(qualified_name)
        
        # Add value synonyms
        for canonical, synonyms in param.value_synonyms.items():
            value_id = f"value:{qualified_name}:{canonical.lower()}"
            self._graph.add_node(
                value_id,
                node_type=NodeType.VALUE,
                name=canonical,
                field_path=qualified_name,
                endpoint_path=endpoint_path,
                synonyms=synonyms,
                source="param",
            )
            self._graph.add_edge(
                param_id,
                value_id,
                relation=EdgeType.HAS_VALUE,
            )
            
            # Index canonical value
            self._value_to_concept[canonical.lower()] = (qualified_name, canonical)
            
            # Add synonym aliases
            for syn in synonyms:
                syn_alias_id = f"alias:value:{qualified_name}:{syn.lower()}"
                if not self._graph.has_node(syn_alias_id):
                    self._graph.add_node(
                        syn_alias_id,
                        node_type=NodeType.ALIAS,
                        name=syn,
                        alias_of=canonical,
                        alias_type="param_value_synonym",
                        field_path=qualified_name,
                    )
                self._graph.add_edge(
                    syn_alias_id,
                    value_id,
                    relation=EdgeType.SYNONYM_OF,
                )
                self._value_to_concept[syn.lower()] = (qualified_name, canonical)
        
        # Add allowed_values as value nodes
        if param.allowed_values:
            for allowed in param.allowed_values:
                allowed_lower = allowed.lower()
                if allowed_lower not in self._value_to_concept:
                    value_id = f"value:{qualified_name}:{allowed_lower}"
                    if not self._graph.has_node(value_id):
                        self._graph.add_node(
                            value_id,
                            node_type=NodeType.VALUE,
                            name=allowed,
                            field_path=qualified_name,
                            endpoint_path=endpoint_path,
                            synonyms=[],
                            source="allowed_values",
                        )
                        self._graph.add_edge(
                            param_id,
                            value_id,
                            relation=EdgeType.HAS_VALUE,
                        )
                        self._value_to_concept[allowed_lower] = (qualified_name, allowed)

    def _add_response_field_to_graph(
        self,
        resp_field: ResponseFieldSpec,
        endpoint_id: str,
        endpoint_key: str,
    ) -> None:
        """Add response field to graph with indexing for search."""
        field_id = f"response_field:{endpoint_key}:{resp_field.path}"
        self._graph.add_node(
            field_id,
            node_type=NodeType.RESPONSE_FIELD,
            name=resp_field.path,
            path=resp_field.path,
            field_type=resp_field.field_type,
            description=resp_field.description,
            maps_to=resp_field.maps_to,
            endpoint_key=endpoint_key,
        )
        
        # Edge: Endpoint -> Response Field
        self._graph.add_edge(
            endpoint_id,
            field_id,
            relation=EdgeType.RETURNS,
        )
        
        # Edge: Response Field -> Concept
        if resp_field.maps_to:
            concept_id = f"concept:{resp_field.maps_to}"
            if self._graph.has_node(concept_id):
                self._graph.add_edge(
                    field_id,
                    concept_id,
                    relation=EdgeType.RESPONSE_MAPS_TO,
                )
            # Index concept -> response endpoints
            if resp_field.maps_to not in self._concept_to_response_endpoints:
                self._concept_to_response_endpoints[resp_field.maps_to] = set()
            self._concept_to_response_endpoints[resp_field.maps_to].add(endpoint_key)
        
        # Index nested path segments for search
        self._index_response_path(resp_field.path, endpoint_key)
    
    def _index_response_path(self, path: str, endpoint_key: str) -> None:
        """Index all segments of a nested response field path."""
        # Remove array notation
        clean_path = path.replace('[]', '')
        
        # Split by dots
        parts = clean_path.split('.')
        
        # Index each part
        for part in parts:
            if len(part) > 2:
                part_lower = part.lower()
                if part_lower not in self._response_path_to_endpoints:
                    self._response_path_to_endpoints[part_lower] = set()
                self._response_path_to_endpoints[part_lower].add(endpoint_key)
        
        # Index full path
        full_path_lower = clean_path.lower()
        if full_path_lower not in self._response_path_to_endpoints:
            self._response_path_to_endpoints[full_path_lower] = set()
        self._response_path_to_endpoints[full_path_lower].add(endpoint_key)
        
        # Index compound suffixes
        for i in range(len(parts) - 1):
            compound = '.'.join(parts[i:]).lower()
            if compound not in self._response_path_to_endpoints:
                self._response_path_to_endpoints[compound] = set()
            self._response_path_to_endpoints[compound].add(endpoint_key)

    def _add_example_node(self, example: Any, idx: int) -> None:
        """Add a Q&A example to the graph (legacy support)."""
        example_id = f"example:{idx}"
        self._graph.add_node(
            example_id,
            node_type=NodeType.EXAMPLE,
            question=example.question,
            query=example.query,
            concepts_used=example.concepts_used,
            fields_used=example.fields_used,
            verified=example.verified,
            source=example.source,
        )

        # Link to concepts used in this example
        for concept in example.concepts_used:
            concept_id = f"concept:{concept.lower()}"
            if self._graph.has_node(concept_id):
                self._graph.add_edge(
                    example_id,
                    concept_id,
                    relation=EdgeType.DEMONSTRATES,
                )
                # Update index
                if concept.lower() not in self._concept_to_examples:
                    self._concept_to_examples[concept.lower()] = set()
                self._concept_to_examples[concept.lower()].add(example_id)

        # Link to fields used
        for field_path in example.fields_used:
            field_id = f"field:{field_path}"
            if self._graph.has_node(field_id):
                self._graph.add_edge(
                    example_id,
                    field_id,
                    relation=EdgeType.USES_FIELD,
                )
                # Update index
                if field_path not in self._field_to_examples:
                    self._field_to_examples[field_path] = set()
                self._field_to_examples[field_path].add(example_id)

    def add_example(self, example: 'ExampleSpec') -> str:
        """
        Add an ExampleSpec to the graph with all edges.

        Creates:
        - EXAMPLE node with all metadata
        - DEMONSTRATES edges to linked concepts
        - USES_FIELD edges to linked fields
        - USES_VALUE edges to linked values
        - HAS_VARIANT edges to variant keyword aliases

        Args:
            example: ExampleSpec instance

        Returns:
            Example node ID
        """
        from ..schema.example_schema import ExampleSpec as ES
        
        example_id = f"example:{example.id}"

        # 1. Create EXAMPLE node
        self._graph.add_node(
            example_id,
            node_type=NodeType.EXAMPLE,
            title=example.title,
            description=example.description,
            query=example.content.query,
            query_type=example.content.query_type,
            explanation=example.content.explanation,
            variants=example.variants,
            additional_context=example.additional_context,
            linked_concepts=example.linked_concepts,
            linked_fields=example.linked_fields,
            linked_values=example.linked_values,
            verified=example.verified,
            source=example.source,
            tags=example.tags,
            usage_count=example.usage_count,
        )

        # 2. DEMONSTRATES edges -> Concepts
        for concept in example.linked_concepts:
            concept_lower = concept.lower()
            concept_node_id = f"concept:{concept_lower}"

            if self._graph.has_node(concept_node_id):
                self._graph.add_edge(
                    example_id,
                    concept_node_id,
                    relation=EdgeType.DEMONSTRATES,
                )
            # Always update index
            if concept_lower not in self._concept_to_examples:
                self._concept_to_examples[concept_lower] = set()
            self._concept_to_examples[concept_lower].add(example_id)

        # 3. USES_FIELD edges -> Fields
        for field_path in example.linked_fields:
            field_node_id = f"field:{field_path}"

            if self._graph.has_node(field_node_id):
                self._graph.add_edge(
                    example_id,
                    field_node_id,
                    relation=EdgeType.USES_FIELD,
                )
            # Always update index
            if field_path not in self._field_to_examples:
                self._field_to_examples[field_path] = set()
            self._field_to_examples[field_path].add(example_id)

        # 4. USES_VALUE edges -> Values
        for field_path, value in example.linked_values.items():
            value_node_id = self._find_value_node(field_path, value)

            if value_node_id and self._graph.has_node(value_node_id):
                self._graph.add_edge(
                    example_id,
                    value_node_id,
                    relation=EdgeType.USES_VALUE,
                )
            # Update index
            value_key = f"{field_path}:{value.lower()}"
            if value_key not in self._value_to_examples:
                self._value_to_examples[value_key] = set()
            self._value_to_examples[value_key].add(example_id)

        # 5. HAS_VARIANT edges -> Variant keyword aliases
        variant_keywords = example.get_variant_keywords()
        for keyword in variant_keywords:
            variant_node_id = f"example_keyword:{example.id}:{keyword}"

            self._graph.add_node(
                variant_node_id,
                node_type=NodeType.ALIAS,
                name=keyword,
                alias_of=example_id,
                alias_type="example_variant",
            )
            self._graph.add_edge(
                example_id,
                variant_node_id,
                relation=EdgeType.HAS_VARIANT,
            )

            # Update index
            if keyword not in self._keyword_to_examples:
                self._keyword_to_examples[keyword] = set()
            self._keyword_to_examples[keyword].add(example_id)

        logger.info(
            f"Added example '{example.title}' to graph: "
            f"{len(example.linked_concepts)} concepts, "
            f"{len(example.linked_fields)} fields, "
            f"{len(example.linked_values)} values, "
            f"{len(variant_keywords)} keywords"
        )

        return example_id

    def _find_value_node(self, field_path: str, value: str) -> Optional[str]:
        """Find value node ID for a field:value combination."""
        value_lower = value.lower()

        # Try field-level value node first
        field_value_id = f"value:{field_path}:{value_lower}"
        if self._graph.has_node(field_value_id):
            return field_value_id

        # Try to find via concept mapping
        concepts = self._field_to_concepts.get(field_path, set())
        for concept in concepts:
            concept_value_id = f"value:{concept}:{value_lower}"
            if self._graph.has_node(concept_value_id):
                return concept_value_id

        return None

    def remove_example(self, example_id: str) -> bool:
        """
        Remove example and all its edges from graph.

        Args:
            example_id: Example ID (with or without 'example:' prefix)

        Returns:
            True if removed, False if not found
        """
        full_id = example_id if example_id.startswith("example:") else f"example:{example_id}"

        if not self._graph.has_node(full_id):
            return False

        # Get node data before removal
        node_data = self._graph.nodes[full_id]

        # Remove from concept indexes
        for concept in node_data.get('linked_concepts', []):
            self._concept_to_examples.get(concept.lower(), set()).discard(full_id)

        # Remove from field indexes
        for field_path in node_data.get('linked_fields', []):
            self._field_to_examples.get(field_path, set()).discard(full_id)

        # Remove from value indexes
        for field_path, value in node_data.get('linked_values', {}).items():
            value_key = f"{field_path}:{value.lower()}"
            self._value_to_examples.get(value_key, set()).discard(full_id)

        # Remove variant keyword nodes and update indexes
        variant_nodes = [
            n for n in self._graph.nodes()
            if n.startswith(f"example_keyword:{example_id.replace('example:', '')}:")
        ]
        for variant_node in variant_nodes:
            keyword = self._graph.nodes[variant_node].get('name')
            if keyword:
                self._keyword_to_examples.get(keyword, set()).discard(full_id)
            self._graph.remove_node(variant_node)

        # Remove example node (edges auto-removed)
        self._graph.remove_node(full_id)

        return True

    # === EXAMPLE RETRIEVAL ===

    def get_examples_for_concept(self, concept_name: str) -> List[Dict[str, Any]]:
        """Get Q&A examples that demonstrate a concept."""
        concept_lower = concept_name.lower()
        example_ids = self._concept_to_examples.get(concept_lower, set())
        return [self._get_example_data(eid) for eid in example_ids]

    def get_examples_for_concepts(
        self,
        concepts: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get examples that DEMONSTRATE any of the given concepts."""
        result = {}
        for concept in concepts:
            result[concept] = self.get_examples_for_concept(concept)
        return result

    def get_examples_for_fields(
        self,
        field_paths: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get examples that USE any of the given fields."""
        result = {}
        for field_path in field_paths:
            example_ids = self._field_to_examples.get(field_path, set())
            result[field_path] = [self._get_example_data(eid) for eid in example_ids]
        return result

    def get_examples_for_values(
        self,
        field_values: List[Tuple[str, str]]
    ) -> List[Dict[str, Any]]:
        """Get examples that USE specific field:value combinations."""
        example_ids: Set[str] = set()
        for field_path, value in field_values:
            value_key = f"{field_path}:{value.lower()}"
            example_ids.update(self._value_to_examples.get(value_key, set()))

        return [self._get_example_data(eid) for eid in example_ids]

    def get_examples_by_keywords(
        self,
        keywords: List[str]
    ) -> List[Tuple[Dict[str, Any], int]]:
        """Get examples matching variant keywords."""
        example_match_counts: Dict[str, int] = {}

        for keyword in keywords:
            keyword_lower = keyword.lower()
            matching_examples = self._keyword_to_examples.get(keyword_lower, set())
            for eid in matching_examples:
                example_match_counts[eid] = example_match_counts.get(eid, 0) + 1

        # Sort by match count
        sorted_examples = sorted(
            example_match_counts.items(),
            key=lambda x: -x[1]
        )

        return [
            (self._get_example_data(eid), count)
            for eid, count in sorted_examples
        ]

    def _get_example_data(self, example_id: str) -> Dict[str, Any]:
        """Get example node data as dictionary."""
        if not self._graph.has_node(example_id):
            return {}

        node = self._graph.nodes[example_id]
        
        # Handle both legacy and new formats
        return {
            "id": example_id.replace("example:", ""),
            "title": node.get("title") or node.get("question"),
            "description": node.get("description"),
            "query": node.get("query"),
            "query_type": node.get("query_type", "sql"),
            "explanation": node.get("explanation"),
            "variants": node.get("variants", []),
            "additional_context": node.get("additional_context"),
            "linked_concepts": node.get("linked_concepts") or node.get("concepts_used", []),
            "linked_fields": node.get("linked_fields") or node.get("fields_used", []),
            "linked_values": node.get("linked_values", {}),
            "verified": node.get("verified", False),
            "source": node.get("source"),
            "tags": node.get("tags", []),
            "usage_count": node.get("usage_count", 0),
        }

    # === GRAPH SEARCH ===

    def find_fields_by_concept(
        self,
        concept: str,
        include_related: bool = True,
        max_hops: int = 1,
    ) -> SearchResult:
        """
        Find all fields mapped to a concept.

        Args:
            concept: Concept name to search for
            include_related: Also include fields from related concepts
            max_hops: How many relationship hops to traverse

        Returns:
            SearchResult with matched and expanded fields
        """
        # Resolve alias if needed
        concept_name = self._alias_to_entity.get(concept.lower(), concept.lower())
        concept_id = f"concept:{concept_name}"

        if not self._graph.has_node(concept_id):
            return SearchResult(
                matched_concepts=[],
                matched_fields=[],
                expanded_fields=set(),
                adjacency={},
                traversal_path=[],
                hop_count=0,
            )

        # Get directly mapped fields
        matched_fields = list(self._concept_to_fields.get(concept_name, set()))
        expanded_fields = set(matched_fields)
        traversal_path = [concept_id]
        adjacency: Dict[str, List[Tuple[str, str]]] = {}

        # Record adjacency
        adjacency[concept_name] = []
        for field_path in matched_fields:
            adjacency[concept_name].append((field_path, EdgeType.MAPS_TO))

        # Expand to related concepts if requested
        if include_related and max_hops > 0:
            visited_concepts = {concept_name}
            frontier = [concept_name]

            for hop in range(max_hops):
                next_frontier = []
                for current in frontier:
                    current_id = f"concept:{current}"

                    # Get related concepts
                    for neighbor in self._graph.neighbors(current_id):
                        node_data = self._graph.nodes[neighbor]
                        if node_data.get('node_type') == NodeType.CONCEPT:
                            related_name = node_data['name']
                            if related_name not in visited_concepts:
                                visited_concepts.add(related_name)
                                next_frontier.append(related_name)
                                traversal_path.append(f"concept:{related_name}")

                                # Get fields for this related concept
                                related_fields = self._concept_to_fields.get(related_name, set())
                                expanded_fields.update(related_fields)

                                # Record adjacency
                                if current not in adjacency:
                                    adjacency[current] = []
                                adjacency[current].append((related_name, EdgeType.RELATES_TO))

                frontier = next_frontier

        return SearchResult(
            matched_concepts=[(concept_name, 1.0)],
            matched_fields=matched_fields,
            expanded_fields=expanded_fields,
            adjacency=adjacency,
            traversal_path=traversal_path,
            hop_count=max_hops if include_related else 0,
        )

    def find_related_fields(
        self,
        field_path: str,
        index_name: Optional[str] = None,
        max_hops: int = 2,
    ) -> SearchResult:
        """
        Expand from a field to related fields via concept links.

        Traversal: field -> concept -> related_concepts -> their_fields

        Args:
            field_path: Starting field path
            index_name: Optional index to scope the search
            max_hops: Maximum hops to traverse

        Returns:
            SearchResult with expanded fields
        """
        # Find the field node(s)
        field_nodes = []
        for node_id in self._graph.nodes():
            if node_id.startswith("field:"):
                node_data = self._graph.nodes[node_id]
                if node_data.get('path') == field_path:
                    if index_name is None or node_data.get('index') == index_name:
                        field_nodes.append(node_id)

        if not field_nodes:
            return SearchResult(
                matched_concepts=[],
                matched_fields=[],
                expanded_fields=set(),
                adjacency={},
                traversal_path=[],
                hop_count=0,
            )

        matched_concepts: List[Tuple[str, float]] = []
        expanded_fields: Set[str] = set()
        traversal_path: List[str] = []
        adjacency: Dict[str, List[Tuple[str, str]]] = {}

        # Start from each matching field
        for field_node in field_nodes:
            traversal_path.append(field_node)

            # Get concepts this field maps to
            for neighbor in self._graph.neighbors(field_node):
                node_data = self._graph.nodes[neighbor]
                if node_data.get('node_type') == NodeType.CONCEPT:
                    concept_name = node_data['name']
                    matched_concepts.append((concept_name, 1.0))

                    # Expand from this concept
                    result = self.find_fields_by_concept(
                        concept_name,
                        include_related=True,
                        max_hops=max_hops - 1,
                    )
                    expanded_fields.update(result.expanded_fields)
                    traversal_path.extend(result.traversal_path)

                    # Merge adjacency
                    for k, v in result.adjacency.items():
                        if k not in adjacency:
                            adjacency[k] = []
                        adjacency[k].extend(v)

        return SearchResult(
            matched_concepts=matched_concepts,
            matched_fields=[field_path],
            expanded_fields=expanded_fields,
            adjacency=adjacency,
            traversal_path=traversal_path,
            hop_count=max_hops,
        )

    def resolve_value_synonym(self, value: str) -> Optional[Tuple[str, str]]:
        """
        Resolve a value synonym to its canonical form.

        Args:
            value: Value or synonym to resolve

        Returns:
            (concept_or_field, canonical_value) or None if not found
        """
        return self._value_to_concept.get(value.lower())

    def get_canonical_values(self, concept_name: str) -> Set[str]:
        """
        Get all canonical values for a concept.

        Args:
            concept_name: Concept to get values for

        Returns:
            Set of canonical value names
        """
        return self._concept_to_values.get(concept_name, set()).copy()

    def get_field_spec(self, field_path: str, index_name: Optional[str] = None) -> Optional[FieldSpec]:
        """
        Get FieldSpec for a field path.

        Args:
            field_path: Field path to look up
            index_name: Optional index to scope the search

        Returns:
            FieldSpec or None if not found
        """
        for node_id in self._graph.nodes():
            if node_id.startswith("field:"):
                node_data = self._graph.nodes[node_id]
                if node_data.get('path') == field_path:
                    if index_name is None or node_data.get('index') == index_name:
                        return node_data.get('field_spec')
        return None

    def get_all_concepts(self) -> List[str]:
        """Get list of all concept names in the graph."""
        return list(self._concept_to_fields.keys())

    def get_all_fields(self, index_name: Optional[str] = None) -> List[str]:
        """Get list of all field paths, optionally filtered by index."""
        if index_name:
            return list(self._index_fields.get(index_name, set()))
        
        all_fields: Set[str] = set()
        for fields in self._index_fields.values():
            all_fields.update(fields)
        return list(all_fields)

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the graph."""
        node_types: Dict[str, int] = {}
        for node_id in self._graph.nodes():
            node_data = self._graph.nodes[node_id]
            node_type = node_data.get('node_type', 'unknown')
            node_types[node_type] = node_types.get(node_type, 0) + 1

        return {
            "total_nodes": self._graph.number_of_nodes(),
            "total_edges": self._graph.number_of_edges(),
            "node_types": node_types,
            "concept_count": len(self._concept_to_fields),
            "field_count": sum(len(f) for f in self._index_fields.values()),
            "index_count": len(self._index_fields),
            "value_synonym_count": len(self._value_to_concept),
            "example_count": len(self._concept_to_examples),
        }

    def __repr__(self) -> str:
        stats = self.get_graph_stats()
        return (
            f"SchemaGraph("
            f"nodes={stats['total_nodes']}, "
            f"edges={stats['total_edges']}, "
            f"concepts={stats['concept_count']}, "
            f"fields={stats['field_count']})"
        )
