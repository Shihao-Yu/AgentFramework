"""
ContextForge Retrieval Layer

Provides retrieval pipeline components for context-aware query generation:
- RetrievalContext: Container for retrieved fields, examples, and endpoints
- GraphContextRetriever: Graph-based fusion retrieval (preferred)
- HybridExampleRetriever: Hybrid example retrieval (graph + keyword + vector)
- ContextFormatter: Format context for LLM prompts
- DatasetRouter: Multi-dataset routing

Example:
    >>> from contextforge.retrieval import GraphContextRetriever, RetrievalContext
    >>> from contextforge.graph import SchemaGraph
    >>>
    >>> graph = SchemaGraph()
    >>> graph.load_from_yaml(Path("schema.yaml"))
    >>> retriever = GraphContextRetriever(graph)
    >>> context = retriever.retrieve("Show me orders from last week")
    >>> print(f"Found {context.field_count} fields, {context.example_count} examples")
"""

from .context import (
    RetrievalContext,
    ContextFormatter,
)
from .graph_retriever import (
    GraphContextRetriever,
    GraphRetrievalConfig,
    RetrievalStrategy,
    ScoringConfig,
    EndpointScoringConfig,
    EndpointMatch,
    create_graph_retriever,
)
from .example_retriever import (
    HybridExampleRetriever,
    ExampleRetrievalConfig,
    ExampleMatch,
)

__all__ = [
    # Context
    "RetrievalContext",
    "ContextFormatter",
    # Graph Retriever (preferred)
    "GraphContextRetriever",
    "GraphRetrievalConfig",
    "RetrievalStrategy",
    "ScoringConfig",
    "EndpointScoringConfig",
    "EndpointMatch",
    "create_graph_retriever",
    # Example Retriever
    "HybridExampleRetriever",
    "ExampleRetrievalConfig",
    "ExampleMatch",
]
