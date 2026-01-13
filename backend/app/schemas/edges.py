"""
Knowledge Verse edge schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.models.enums import EdgeType


class EdgeCreate(BaseModel):
    source_id: int
    target_id: int
    edge_type: EdgeType
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata_: Dict[str, Any] = Field(default={})


class EdgeBulkCreate(BaseModel):
    edges: List[EdgeCreate] = Field(..., min_length=1, max_length=100)


class EdgeUpdate(BaseModel):
    weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    metadata_: Optional[Dict[str, Any]] = None


class EdgeResponse(BaseModel):
    id: int
    source_id: int
    target_id: int
    edge_type: EdgeType
    weight: float
    is_auto_generated: bool
    metadata_: Dict[str, Any]
    created_by: Optional[str] = None
    created_at: datetime
    
    source_title: Optional[str] = None
    target_title: Optional[str] = None
    source_node_type: Optional[str] = None
    target_node_type: Optional[str] = None
    
    class Config:
        from_attributes = True


class EdgeListParams(BaseModel):
    node_id: Optional[int] = None
    edge_types: Optional[List[EdgeType]] = None
    include_auto_generated: bool = True
    direction: Optional[str] = Field(None, pattern="^(incoming|outgoing|both)$")
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=200)


class EdgeListResponse(BaseModel):
    edges: List[EdgeResponse]
    total: int
    page: int
    limit: int
