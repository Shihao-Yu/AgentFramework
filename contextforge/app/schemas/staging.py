"""
Staging queue request/response schemas.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.models.enums import KnowledgeType, StagingStatus, StagingAction


# ==================== List/Filter Parameters ====================

class StagingListParams(BaseModel):
    """Parameters for listing staging items."""
    
    status: Optional[StagingStatus] = StagingStatus.PENDING
    action: Optional[StagingAction] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


# ==================== Request Schemas ====================

class StagingReviewRequest(BaseModel):
    """Request schema for reviewing a staging item."""
    
    # For approve with edits
    edits: Optional[Dict[str, Any]] = None
    
    # For reject
    reason: Optional[str] = None


class StagingEditRequest(BaseModel):
    """Request schema for editing a staging item before review."""
    
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


# ==================== Response Schemas ====================

class StagingItemResponse(BaseModel):
    """Response schema for a staging item."""
    
    id: int
    knowledge_type: KnowledgeType
    category_id: Optional[int] = None
    title: str
    summary: Optional[str] = None
    content: Dict[str, Any]
    tags: List[str]
    
    # Pipeline info
    source_ticket_id: Optional[str] = None
    source_type: str
    confidence: Optional[float] = None
    
    # Status
    status: StagingStatus
    action: StagingAction
    
    # Merge info
    merge_with_id: Optional[int] = None
    similarity: Optional[float] = None
    
    # Review info
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    
    # Audit
    created_by: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class StagingCountsResponse(BaseModel):
    """Response schema for staging counts by action type."""
    
    new: int
    merge: int
    add_variant: int


class StagingListResponse(BaseModel):
    """Response schema for listing staging items."""
    
    data: List[StagingItemResponse]
    counts: StagingCountsResponse


class StagingReviewResponse(BaseModel):
    """Response schema for staging review action."""
    
    success: bool
    staging_id: int
    created_item_id: Optional[int] = None
    message: Optional[str] = None
