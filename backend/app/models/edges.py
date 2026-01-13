"""
Knowledge Verse edge models.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, String, BigInteger
from sqlalchemy.dialects.postgresql import JSONB

from app.models.enums import EdgeType


class KnowledgeEdge(SQLModel, table=True):
    __tablename__ = "knowledge_edges"
    __table_args__ = {"schema": "agent"}
    
    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    source_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    target_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    edge_type: EdgeType = Field(sa_column=Column(String(50), nullable=False))
    
    weight: float = Field(default=1.0)
    is_auto_generated: bool = Field(default=False)
    metadata_: Dict[str, Any] = Field(default={}, sa_column=Column("metadata_", JSONB))
    
    created_by: Optional[str] = Field(default=None, max_length=100)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
