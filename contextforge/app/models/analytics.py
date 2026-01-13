"""
Analytics and tracking models.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text, String
from sqlalchemy.dialects.postgresql import JSONB, ARRAY


class KnowledgeHit(SQLModel, table=True):
    """
    Record of knowledge item retrieval.
    
    Used for analytics and measuring FAQ effectiveness.
    """
    
    __tablename__ = "knowledge_hits"
    __table_args__ = {"schema": "agent"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    knowledge_item_id: Optional[int] = Field(
        default=None, 
        foreign_key="agent.knowledge_items.id"
    )
    variant_id: Optional[int] = Field(
        default=None, 
        foreign_key="agent.knowledge_variants.id"
    )
    
    # Query Info
    query_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    similarity_score: Optional[float] = Field(default=None)
    
    # Retrieval Method
    retrieval_method: Optional[str] = Field(default=None, max_length=30)
    match_source: Optional[str] = Field(default=None, max_length=50)
    
    # Session
    session_id: Optional[str] = Field(default=None, max_length=100)
    user_id: Optional[str] = Field(default=None, max_length=100)
    
    # Timestamp
    hit_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class KnowledgeVersion(SQLModel, table=True):
    """
    Version history for knowledge items.
    
    Automatically created by database trigger on content changes.
    Retained for 90 days by default.
    """
    
    __tablename__ = "knowledge_versions"
    __table_args__ = {"schema": "agent"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    knowledge_item_id: int = Field(foreign_key="agent.knowledge_items.id")
    version_number: int
    
    # Snapshot of content
    title: str = Field(max_length=500)
    summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    content: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(ARRAY(Text)))
    
    # Change Info
    change_type: Optional[str] = Field(default=None, max_length=20)
    change_reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    changed_by: Optional[str] = Field(default=None, max_length=100)
    changed_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
