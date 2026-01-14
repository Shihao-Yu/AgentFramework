"""
Search request/response schemas.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.models.enums import NodeType, KnowledgeStatus, Visibility


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: Optional[int] = Field(10, ge=1, le=100)
    bm25_weight: Optional[float] = Field(None, ge=0, le=1)
    vector_weight: Optional[float] = Field(None, ge=0, le=1)
    node_types: Optional[List[NodeType]] = None
    tags: Optional[List[str]] = None
    visibility: Optional[Visibility] = Visibility.INTERNAL
    status: Optional[KnowledgeStatus] = KnowledgeStatus.PUBLISHED


class SearchResult(BaseModel):
    id: int
    node_type: str
    title: str
    summary: Optional[str] = None
    content: Dict[str, Any]
    tags: List[str]
    hybrid_score: float
    match_sources: List[str]


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int


class ContextSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    entry_types: Optional[List[NodeType]] = None
    entry_limit: int = Field(3, ge=1, le=10)
    expand_graph: bool = True
    context_types: Optional[List[NodeType]] = None
    max_hops: int = Field(2, ge=1, le=3)
    context_limit: int = Field(5, ge=1, le=20)
    filter_tags: Optional[List[str]] = None
    visibility: Optional[Visibility] = Visibility.INTERNAL


class ContextItem(BaseModel):
    id: int
    node_type: str
    title: str
    summary: Optional[str] = None
    content: Dict[str, Any]
    score: float
    distance: int
    edge_type: str
    from_entry: int


class ContextSearchResponse(BaseModel):
    query: str
    entry_points: List[SearchResult]
    context: List[ContextItem]
    graph_stats: Dict[str, Any]
