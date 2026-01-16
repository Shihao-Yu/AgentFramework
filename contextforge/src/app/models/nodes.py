"""
Knowledge Verse node models.

Includes:
- KnowledgeNode: Main knowledge entry in the graph
- NodeVariant: Alternative phrasings for improved search matching
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Text, String, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from app.models.base import AuditMixin
from app.models.enums import NodeType, KnowledgeStatus, Visibility, VariantSource
from app.utils.schema import get_schema

_SCHEMA = get_schema()


class KnowledgeNode(AuditMixin, SQLModel, table=True):
    """
    Main knowledge node in the graph.
    
    Supports multiple node types with flexible JSONB content.
    Multi-tenant by design with tenant_id.
    """
    
    __tablename__ = "knowledge_nodes"
    __table_args__ = {"schema": _SCHEMA}
    
    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    tenant_id: str = Field(max_length=100)
    node_type: NodeType = Field(sa_column=Column(String(50), nullable=False))
    
    title: str = Field(max_length=500)
    summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    content: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB, nullable=False))
    
    tags: List[str] = Field(default=[], sa_column=Column(ARRAY(Text)))
    
    # Schema-specific fields (for SCHEMA_INDEX, SCHEMA_FIELD node types)
    dataset_name: Optional[str] = Field(default=None, max_length=100)
    field_path: Optional[str] = Field(default=None, max_length=500)
    data_type: Optional[str] = Field(default=None, max_length=50)
    
    visibility: Visibility = Field(default=Visibility.INTERNAL, sa_column=Column(String(20)))
    status: KnowledgeStatus = Field(default=KnowledgeStatus.PUBLISHED, sa_column=Column(String(20)))
    source: str = Field(default="manual", max_length=50)
    source_reference: Optional[str] = Field(default=None, max_length=500)
    
    version: int = Field(default=1)
    graph_version: int = Field(default=0, sa_column=Column(BigInteger))
    
    node_metadata: Dict[str, Any] = Field(default={}, sa_column=Column("metadata", JSONB, nullable=False, default={}))
    
    # Relationships
    variants: List["NodeVariant"] = Relationship(back_populates="node")


class NodeVariant(SQLModel, table=True):
    """
    Alternative phrasing for a knowledge node.
    
    Supports 1:N relationship - one node can have many variants.
    Each variant has its own embedding for improved search matching.
    """
    
    __tablename__ = "node_variants"
    __table_args__ = {"schema": _SCHEMA}
    
    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    node_id: int = Field(sa_column=Column(BigInteger, ForeignKey(f"{_SCHEMA}.knowledge_nodes.id"), nullable=False))
    
    # Variant content
    variant_text: str = Field(sa_column=Column(Text, nullable=False))
    # Note: embedding column handled by PostgreSQL migration (vector type)
    
    # Source tracking
    source: VariantSource = Field(default=VariantSource.MANUAL, sa_column=Column(String(30)))
    source_reference: Optional[str] = Field(default=None, max_length=500)
    
    # Audit
    created_by: Optional[str] = Field(default=None, max_length=100)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    # Graph sync version
    graph_version: int = Field(default=0, sa_column=Column(BigInteger))
    
    # Relationships
    node: Optional[KnowledgeNode] = Relationship(back_populates="variants")
