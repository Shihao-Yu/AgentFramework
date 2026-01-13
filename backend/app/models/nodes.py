"""
Knowledge Verse node models.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text, String, BigInteger
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from app.models.base import AuditMixin
from app.models.enums import NodeType, KnowledgeStatus, Visibility


class KnowledgeNode(AuditMixin, SQLModel, table=True):
    __tablename__ = "knowledge_nodes"
    __table_args__ = {"schema": "agent"}
    
    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    tenant_id: str = Field(max_length=100)
    node_type: NodeType = Field(sa_column=Column(String(50), nullable=False))
    
    title: str = Field(max_length=500)
    summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    content: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB, nullable=False))
    
    tags: List[str] = Field(default=[], sa_column=Column(ARRAY(Text)))
    
    dataset_name: Optional[str] = Field(default=None, max_length=100)
    field_path: Optional[str] = Field(default=None, max_length=500)
    data_type: Optional[str] = Field(default=None, max_length=50)
    
    visibility: Visibility = Field(default=Visibility.INTERNAL, sa_column=Column(String(20)))
    status: KnowledgeStatus = Field(default=KnowledgeStatus.PUBLISHED, sa_column=Column(String(20)))
    source: str = Field(default="manual", max_length=50)
    source_reference: Optional[str] = Field(default=None, max_length=500)
    
    version: int = Field(default=1)
    graph_version: int = Field(default=0, sa_column=Column(BigInteger))
