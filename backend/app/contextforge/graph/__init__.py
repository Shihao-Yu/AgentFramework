"""
ContextForge Graph Layer

NetworkX-based schema graph for concept/field relationships with hybrid search.

Components:
- SchemaGraph: NetworkX DiGraph for schema structure with semantic search
- BM25FieldIndex: BM25 ranking for text-based field discovery
- ValueSynonymIndex: Fast lookup for value synonyms and pronouns

The graph layer enables:
- Concept-based field discovery
- Value synonym resolution
- Multi-hop relationship traversal
- Hybrid search (vector + BM25 + graph)

Example:
    >>> from contextforge.graph import SchemaGraph, BM25FieldIndex, ValueSynonymIndex
    >>>
    >>> # Build graph from YAML schema
    >>> graph = SchemaGraph()
    >>> graph.load_from_yaml(Path("schema.yaml"))
    >>>
    >>> # Find fields by concept
    >>> result = graph.find_fields_by_concept("order_status")
    >>> print(result.matched_fields)
    ['Status', 'PurchaseOrder.Status']
    >>>
    >>> # BM25 text search
    >>> bm25 = BM25FieldIndex()
    >>> bm25.build_from_schema(graph.schema)
    >>> results = bm25.search("pending orders", top_k=5)
    >>>
    >>> # Value synonym lookup
    >>> value_index = ValueSynonymIndex()
    >>> value_index.build_from_schema(graph.schema)
    >>> matches = value_index.lookup_value("waiting")  # -> "pending"
"""

from .schema_graph import (
    SchemaGraph,
    GraphNode,
    SearchResult,
    NodeType,
    EdgeType,
)
from .bm25_index import (
    BM25FieldIndex,
    BM25Config,
    BM25Document,
    BM25SearchResult,
)
from .value_index import (
    ValueSynonymIndex,
    ValueMatch,
)

__all__ = [
    # Schema Graph
    "SchemaGraph",
    "GraphNode",
    "SearchResult",
    "NodeType",
    "EdgeType",
    # BM25 Index
    "BM25FieldIndex",
    "BM25Config",
    "BM25Document",
    "BM25SearchResult",
    # Value Index
    "ValueSynonymIndex",
    "ValueMatch",
]
