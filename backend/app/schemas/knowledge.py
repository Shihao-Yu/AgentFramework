"""
Knowledge item request/response schemas.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.models.enums import KnowledgeType, KnowledgeStatus, Visibility


# ==================== List/Filter Parameters ====================

class KnowledgeListParams(BaseModel):
    """Parameters for listing knowledge items."""
    
    knowledge_type: Optional[KnowledgeType] = None
    status: Optional[KnowledgeStatus] = None
    visibility: Optional[Visibility] = None
    tags: Optional[List[str]] = None
    category_id: Optional[int] = None
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


# ==================== Request Schemas ====================

class KnowledgeItemCreate(BaseModel):
    """Request schema for creating a knowledge item."""
    
    knowledge_type: KnowledgeType
    category_id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=500)
    summary: Optional[str] = None
    content: Dict[str, Any]
    tags: Optional[List[str]] = None
    visibility: Optional[Visibility] = Visibility.INTERNAL
    status: Optional[KnowledgeStatus] = KnowledgeStatus.DRAFT
    metadata_: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "knowledge_type": "faq",
                "title": "How to create a purchase order",
                "content": {
                    "question": "How do I create a new purchase order?",
                    "answer": "Navigate to Purchasing > Create PO..."
                },
                "tags": ["purchasing", "how-to"],
                "visibility": "internal",
                "status": "draft"
            }
        }


class KnowledgeItemUpdate(BaseModel):
    """Request schema for updating a knowledge item."""
    
    category_id: Optional[int] = None
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    summary: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    visibility: Optional[Visibility] = None
    status: Optional[KnowledgeStatus] = None
    metadata_: Optional[Dict[str, Any]] = None


# ==================== Response Schemas ====================

class KnowledgeItemResponse(BaseModel):
    """Response schema for a knowledge item."""
    
    id: int
    knowledge_type: KnowledgeType
    category_id: Optional[int] = None
    title: str
    summary: Optional[str] = None
    content: Dict[str, Any]
    tags: List[str]
    visibility: Visibility
    status: KnowledgeStatus
    metadata_: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    
    # Extended info (populated on demand)
    variants_count: Optional[int] = None
    relationships_count: Optional[int] = None
    
    class Config:
        from_attributes = True


class KnowledgeItemDetailResponse(KnowledgeItemResponse):
    """Detailed response including variants and relationships."""
    
    variants: Optional[List["VariantResponse"]] = None
    related_items: Optional[List["RelatedItemResponse"]] = None


# ==================== Variant Schemas ====================

class VariantCreate(BaseModel):
    """Request schema for creating a variant."""
    
    variant_text: str = Field(..., min_length=1)
    source: Optional[str] = "manual"
    source_reference: Optional[str] = None


class VariantResponse(BaseModel):
    """Response schema for a variant."""
    
    id: int
    knowledge_item_id: int
    variant_text: str
    source: str
    source_reference: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Relationship Schemas ====================

class RelationshipCreate(BaseModel):
    """Request schema for creating a relationship."""
    
    target_id: int
    relationship_type: str
    weight: Optional[float] = 1.0
    is_bidirectional: Optional[bool] = False


class RelationshipResponse(BaseModel):
    """Response schema for a relationship."""
    
    id: int
    source_id: int
    target_id: int
    relationship_type: str
    weight: float
    is_bidirectional: bool
    is_auto_generated: bool
    created_by: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class RelatedItemResponse(BaseModel):
    """Response schema for related items (includes relationship info)."""
    
    id: int
    knowledge_type: KnowledgeType
    title: str
    relationship_type: str
    is_auto_generated: bool


# ==================== Category Schemas ====================

class CategoryCreate(BaseModel):
    """Request schema for creating a category."""
    
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None
    parent_id: Optional[int] = None
    default_visibility: Optional[str] = "internal"
    sort_order: Optional[int] = 0


class CategoryUpdate(BaseModel):
    """Request schema for updating a category."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    default_visibility: Optional[str] = None
    sort_order: Optional[int] = None


class CategoryResponse(BaseModel):
    """Response schema for a category."""
    
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    default_visibility: str
    sort_order: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class CategoryTreeResponse(CategoryResponse):
    """Response schema for category with children."""
    
    children: Optional[List["CategoryTreeResponse"]] = None


# ==================== Version Schemas ====================

class VersionResponse(BaseModel):
    """Response schema for a version."""
    
    id: int
    knowledge_item_id: int
    version_number: int
    title: str
    summary: Optional[str] = None
    content: Dict[str, Any]
    tags: Optional[List[str]] = None
    change_type: Optional[str] = None
    change_reason: Optional[str] = None
    changed_by: Optional[str] = None
    changed_at: datetime
    
    class Config:
        from_attributes = True


# Forward references
KnowledgeItemDetailResponse.model_rebuild()
CategoryTreeResponse.model_rebuild()
