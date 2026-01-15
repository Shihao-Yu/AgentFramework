from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class StagingItemResponse(BaseModel):
    id: int
    tenant_id: str
    node_type: str
    title: str
    content: Dict[str, Any]
    tags: List[str]
    status: str
    action: str
    merge_with_id: Optional[int] = Field(None, alias="target_node_id")
    similarity: Optional[float] = None
    source: Optional[str] = None
    source_reference: Optional[str] = None
    confidence: Optional[float] = None
    created_at: datetime
    created_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True


class StagingListResponse(BaseModel):
    items: List[StagingItemResponse]
    total: int
    page: int
    limit: int


class StagingApproveRequest(BaseModel):
    edits: Optional[Dict[str, Any]] = None


class StagingRejectRequest(BaseModel):
    reason: Optional[str] = None


class StagingReviewResponse(BaseModel):
    success: bool
    staging_id: int
    created_item_id: Optional[int] = None
    message: str


class StagingCountsResponse(BaseModel):
    new: int
    merge: int
    add_variant: int
    total: int
