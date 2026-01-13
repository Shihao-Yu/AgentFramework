"""
Agent context API schemas for structured context retrieval.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

from app.models.enums import NodeType, EdgeType


class ContextRequest(BaseModel):
    query: str = Field(default="")
    tenant_ids: List[str] = Field(default_factory=list)
    
    entry_types: Optional[List[NodeType]] = None
    entry_limit: int = Field(default=10, ge=1, le=100)
    
    expand: bool = True
    expansion_types: Optional[List[NodeType]] = None
    max_depth: int = Field(default=2, ge=1, le=10)
    context_limit: int = Field(default=50, ge=1, le=200)
    
    include_entities: bool = True
    include_schemas: bool = False
    include_examples: bool = False


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


class ContextResponse(BaseModel):
    entry_points: List[EntryPointResult]
    context: List[ContextNodeResult]
    entities: List[EntityResult]
    stats: ContextStats
