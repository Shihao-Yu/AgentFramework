"""
Knowledge Verse tenant and access control models.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text, String
from sqlalchemy.dialects.postgresql import JSONB

from app.models.enums import TenantRole


class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "agent"}
    
    id: str = Field(primary_key=True, max_length=100)
    name: str = Field(max_length=200)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    settings: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    is_active: bool = Field(default=True)
    
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)


class UserTenantAccess(SQLModel, table=True):
    __tablename__ = "user_tenant_access"
    __table_args__ = {"schema": "agent"}
    
    user_id: str = Field(primary_key=True, max_length=100)
    tenant_id: str = Field(primary_key=True, max_length=100, foreign_key="agent.tenants.id")
    role: TenantRole = Field(default=TenantRole.VIEWER, sa_column=Column(String(50)))
    
    granted_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    granted_by: Optional[str] = Field(default=None, max_length=100)
