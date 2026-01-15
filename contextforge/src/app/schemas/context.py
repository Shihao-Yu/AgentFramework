"""
Agent context API schemas for structured context retrieval.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

from app.models.enums import NodeType, EdgeType


class ContextRequest(BaseModel):
    """
    Request schema for context retrieval from the knowledge graph.
    
    Supports filtering by node types, tags, search method tuning,
    graph expansion control, and token budget management.
    """
    query: str = Field(default="")
    tenant_ids: List[str] = Field(default_factory=list)
    
    entry_types: Optional[List[NodeType]] = Field(
        default=None,
        description="Node types to include as entry points (None = default types)",
    )
    entry_limit: int = Field(default=10, ge=1, le=100)
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter entry points by tags (AND logic)",
    )
    
    search_method: Literal["hybrid", "bm25", "vector"] = Field(
        default="hybrid",
        description="Search method: hybrid (default), bm25 (keyword), or vector (semantic)",
    )
    bm25_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Weight for BM25 keyword search (hybrid mode)",
    )
    vector_weight: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Weight for vector semantic search (hybrid mode)",
    )
    min_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum score threshold for entry points (None = no threshold)",
    )
    
    expand: bool = True
    expansion_types: Optional[List[NodeType]] = Field(
        default=None,
        description="Node types to include in graph expansion (None = all types)",
    )
    max_depth: int = Field(default=2, ge=1, le=10)
    context_limit: int = Field(default=50, ge=1, le=200)
    
    include_entities: bool = True
    include_schemas: bool = False
    include_examples: bool = False
    max_tokens: Optional[int] = Field(
        default=None,
        ge=100,
        le=128000,
        description="Maximum tokens for context (None = no limit)",
    )
    token_model: str = Field(
        default="gpt-4",
        description="Model to use for token counting",
    )


class EntryPointResult(BaseModel):
    id: int
    node_type: NodeType
    title: str
    summary: Optional[str] = None
    content: Dict[str, Any]
    tags: List[str]
    score: float
    match_source: Literal["bm25", "vector", "hybrid"]


class ContextNodeResult(BaseModel):
    id: int
    node_type: NodeType
    title: str
    summary: Optional[str] = None
    content: Dict[str, Any]
    tags: List[str]
    score: float
    distance: int
    path: List[int]
    edge_type: Optional[EdgeType] = None


class EntityResult(BaseModel):
    id: int
    title: str
    entity_path: str
    related_schemas: List[str]


class ContextStats(BaseModel):
    nodes_searched: int
    nodes_expanded: int
    max_depth_reached: int
    entry_points_found: int
    context_nodes_found: int
    total_tokens: Optional[int] = None
    tokens_used: Optional[Dict[str, int]] = None  # Breakdown by category


class ContextResponse(BaseModel):
    entry_points: List[EntryPointResult]
    context: List[ContextNodeResult]
    entities: List[EntityResult]
    stats: ContextStats
