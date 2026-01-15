from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import String, Text, BigInteger, Float, ARRAY
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from app.models.enums import NodeType, StagingStatus, StagingAction


class StagingNode(SQLModel, table=True):
    __tablename__ = "staging_nodes"
    __table_args__ = {"schema": "faq"}

    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    tenant_id: str = Field(sa_column=Column(String(100), nullable=False))
    node_type: str = Field(sa_column=Column(String(50), nullable=False))
    title: str = Field(sa_column=Column(String(500), nullable=False))
    content: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB, nullable=False))
    tags: List[str] = Field(default=[], sa_column=Column(ARRAY(Text)))
    
    dataset_name: Optional[str] = Field(default=None, sa_column=Column(String(100)))
    field_path: Optional[str] = Field(default=None, sa_column=Column(String(500)))
    
    status: str = Field(default="pending", sa_column=Column(String(20)))
    action: str = Field(sa_column=Column(String(20), nullable=False))
    target_node_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    similarity: Optional[float] = Field(default=None, sa_column=Column(Float))
    
    source: Optional[str] = Field(default=None, sa_column=Column(String(50)))
    source_reference: Optional[str] = Field(default=None, sa_column=Column(String(500)))
    confidence: Optional[float] = Field(default=None, sa_column=Column(Float))
    
    reviewed_by: Optional[str] = Field(default=None, sa_column=Column(String(100)))
    reviewed_at: Optional[datetime] = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True)))
    review_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    created_by: Optional[str] = Field(default=None, sa_column=Column(String(100)))
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(TIMESTAMP(timezone=True)))
