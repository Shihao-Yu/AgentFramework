"""
Search request/response schemas.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.models.enums import KnowledgeType, KnowledgeStatus, Visibility


class SearchRequest(BaseModel):
    """Request schema for knowledge search."""
    
    query: str = Field(..., min_length=1, description="Search query text")
    
    # Search parameters
    limit: Optional[int] = Field(10, ge=1, le=100)
    bm25_weight: Optional[float] = Field(None, ge=0, le=1)
    vector_weight: Optional[float] = Field(None, ge=0, le=1)
    
    # Filters
    knowledge_types: Optional[List[KnowledgeType]] = None
    tags: Optional[List[str]] = None
    visibility: Optional[Visibility] = Visibility.INTERNAL
    status: Optional[KnowledgeStatus] = KnowledgeStatus.PUBLISHED
    category_id: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "how to create purchase order",
                "limit": 10,
                "knowledge_types": ["faq"],
                "tags": ["purchasing"]
            }
        }


class SearchResult(BaseModel):
    """Single search result."""
    
    id: int
    knowledge_type: KnowledgeType
    title: str
    summary: Optional[str] = None
    content: Dict[str, Any]
    tags: List[str]
    hybrid_score: float
    match_sources: List[str]


class SearchResponse(BaseModel):
    """Response schema for search results."""
    
    query: str
    results: List[SearchResult]
    total: int


# ==================== Context Search (Graph-Enhanced) ====================

class ContextSearchRequest(BaseModel):
    """Request schema for graph-enhanced contextual search."""
    
    query: str = Field(..., min_length=1)
    
    # Entry point search
    entry_types: Optional[List[KnowledgeType]] = Field(
        default=["faq", "troubleshooting"],
        description="Knowledge types to use as entry points"
    )
    entry_limit: int = Field(3, ge=1, le=10)
    
    # Graph expansion
    expand_graph: bool = True
    context_types: Optional[List[KnowledgeType]] = Field(
        default=["business_rule", "policy", "permission", "context"],
        description="Knowledge types to include as context"
    )
    max_hops: int = Field(2, ge=1, le=3)
    context_limit: int = Field(5, ge=1, le=20)
    
    # Filters
    filter_tags: Optional[List[str]] = None
    visibility: Optional[Visibility] = Visibility.INTERNAL


class ContextItem(BaseModel):
    """Context item from graph expansion."""
    
    id: int
    knowledge_type: KnowledgeType
    title: str
    summary: Optional[str] = None
    content: Dict[str, Any]
    score: float
    distance: int  # Hops from entry point
    edge_type: str  # Type of relationship
    from_entry: int  # Entry point ID this was reached from


class ContextSearchResponse(BaseModel):
    """Response schema for context search."""
    
    query: str
    entry_points: List[SearchResult]
    context: List[ContextItem]
    graph_stats: Dict[str, Any]
