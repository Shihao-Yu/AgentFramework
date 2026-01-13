"""
Knowledge Verse tenant schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.models.enums import TenantRole


class TenantCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9_-]+$")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    settings: Dict[str, Any] = Field(default={})


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class TenantResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    settings: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    node_count: Optional[int] = None
    user_count: Optional[int] = None
    
    class Config:
        from_attributes = True


class TenantListResponse(BaseModel):
    tenants: List[TenantResponse]
    total: int


class UserTenantAccessCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    tenant_id: str = Field(..., min_length=1, max_length=100)
    role: TenantRole = TenantRole.VIEWER


class UserTenantAccessUpdate(BaseModel):
    role: TenantRole


class UserTenantAccessResponse(BaseModel):
    user_id: str
    tenant_id: str
    role: TenantRole
    granted_at: datetime
    granted_by: Optional[str] = None
    
    tenant_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserTenantsResponse(BaseModel):
    user_id: str
    tenants: List[UserTenantAccessResponse]
