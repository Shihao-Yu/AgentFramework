"""
Staging models for pipeline-generated content.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text, String
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from app.models.enums import KnowledgeType, StagingStatus, StagingAction


class StagingKnowledgeItem(SQLModel, table=True):
    """
    Staging entry for content pending human review.
    
    Created by the pipeline when processing tickets.
    Requires human approval before promotion to production.
    """
    
    __tablename__ = "staging_knowledge_items"
    __table_args__ = {"schema": "agent"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Type & Classification
    knowledge_type: KnowledgeType = Field(sa_column=Column(String(30), nullable=False))
    category_id: Optional[int] = Field(default=None)
    
    # Content
    title: str = Field(max_length=500)
    summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    content: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB, nullable=False))
    
    # Note: embedding handled by PostgreSQL
    
    # Metadata
    tags: List[str] = Field(default=[], sa_column=Column(ARRAY(Text)))
    
    # Pipeline Metadata
    source_ticket_id: Optional[str] = Field(default=None, max_length=100)
    source_type: str = Field(default="ticket", max_length=30)
    confidence: Optional[float] = Field(default=None)
    
    # Action & Status
    status: StagingStatus = Field(
        default=StagingStatus.PENDING, 
        sa_column=Column(String(20))
    )
    action: StagingAction = Field(sa_column=Column(String(20), nullable=False))
    
    # Merge Info (when action='merge')
    merge_with_id: Optional[int] = Field(
        default=None, 
        foreign_key="agent.knowledge_items.id"
    )
    similarity: Optional[float] = Field(default=None)
    
    # Review Info
    reviewed_by: Optional[str] = Field(default=None, max_length=100)
    reviewed_at: Optional[datetime] = Field(default=None)
    review_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Audit
    created_by: Optional[str] = Field(default=None, max_length=100)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    metadata_: Dict[str, Any] = Field(
        default={}, 
        sa_column=Column("metadata", JSONB)
    )
