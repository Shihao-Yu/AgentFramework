"""
Base model mixins and utilities.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class AuditMixin(SQLModel):
    """
    Mixin providing standard audit fields.
    
    Automatically tracks:
    - Who created/updated the record
    - When it was created/updated
    - Soft delete status
    """
    
    created_by: Optional[str] = Field(default=None, max_length=100)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = Field(default=None, max_length=100)
    updated_at: Optional[datetime] = Field(default=None)
    is_deleted: bool = Field(default=False)


class TimestampMixin(SQLModel):
    """
    Mixin providing only timestamp fields (no user tracking).
    """
    
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
