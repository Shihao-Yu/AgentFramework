"""
Knowledge base models.

Includes:
- KnowledgeItem: Main knowledge entry
- KnowledgeVariant: Alternative question phrasings
- KnowledgeRelationship: Links between items
- KnowledgeCategory: Hierarchical organization
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Text, String
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from app.models.base import AuditMixin
from app.models.enums import KnowledgeType, KnowledgeStatus, Visibility, RelationshipType

if TYPE_CHECKING:
    from app.models.analytics import KnowledgeHit


class KnowledgeCategory(SQLModel, table=True):
    """Hierarchical category for organizing knowledge items."""
    
    __tablename__ = "knowledge_categories"
    __table_args__ = {"schema": "agent"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    slug: str = Field(max_length=100, unique=True)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    parent_id: Optional[int] = Field(
        default=None, 
        foreign_key="agent.knowledge_categories.id"
    )
    
    # Defaults
    default_visibility: str = Field(default="internal", max_length=20)
    sort_order: int = Field(default=0)
    
    # Audit
    created_by: Optional[str] = Field(default=None, max_length=100)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    is_deleted: bool = Field(default=False)
    
    # Relationships
    items: List["KnowledgeItem"] = Relationship(back_populates="category")


class KnowledgeItem(AuditMixin, SQLModel, table=True):
    """
    Main knowledge base entry.
    
    Supports multiple knowledge types with flexible JSONB content.
    """
    
    __tablename__ = "knowledge_items"
    __table_args__ = {"schema": "agent"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Type & Classification
    knowledge_type: KnowledgeType = Field(sa_column=Column(String(30), nullable=False))
    category_id: Optional[int] = Field(
        default=None, 
        foreign_key="agent.knowledge_categories.id"
    )
    
    # Content
    title: str = Field(max_length=500)
    summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    content: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB, nullable=False))
    
    # Search & Retrieval
    # Note: embedding and search_vector are handled by PostgreSQL
    # We don't define them as SQLModel fields since pgvector needs special handling
    
    # Metadata
    tags: List[str] = Field(default=[], sa_column=Column(ARRAY(Text)))
    visibility: Visibility = Field(
        default=Visibility.INTERNAL, 
        sa_column=Column(String(20))
    )
    status: KnowledgeStatus = Field(
        default=KnowledgeStatus.DRAFT, 
        sa_column=Column(String(20))
    )
    metadata_: Dict[str, Any] = Field(
        default={}, 
        sa_column=Column("metadata", JSONB)
    )
    
    # Graph sync version
    graph_version: int = Field(default=0)
    
    # Relationships
    category: Optional[KnowledgeCategory] = Relationship(back_populates="items")
    variants: List["KnowledgeVariant"] = Relationship(back_populates="knowledge_item")


class KnowledgeVariant(SQLModel, table=True):
    """
    Alternative question phrasing for a knowledge item.
    
    Supports 1:N relationship - one knowledge item can have many variants.
    Each variant has its own embedding for search.
    """
    
    __tablename__ = "knowledge_variants"
    __table_args__ = {"schema": "agent"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    knowledge_item_id: int = Field(foreign_key="agent.knowledge_items.id")
    
    # Variant Content
    variant_text: str = Field(sa_column=Column(Text, nullable=False))
    # Note: embedding handled by PostgreSQL
    
    # Source
    source: str = Field(default="manual", max_length=30)
    source_reference: Optional[str] = Field(default=None, max_length=100)
    
    # Audit
    created_by: Optional[str] = Field(default=None, max_length=100)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    # Graph sync
    graph_version: int = Field(default=0)
    
    # Relationships
    knowledge_item: Optional[KnowledgeItem] = Relationship(back_populates="variants")


class KnowledgeRelationship(SQLModel, table=True):
    """
    Explicit relationship between knowledge items.
    
    Used for graph-based retrieval and navigation.
    """
    
    __tablename__ = "knowledge_relationships"
    __table_args__ = {"schema": "agent"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="agent.knowledge_items.id")
    target_id: int = Field(foreign_key="agent.knowledge_items.id")
    
    # Relationship Info
    relationship_type: RelationshipType = Field(sa_column=Column(String(30), nullable=False))
    weight: float = Field(default=1.0)
    is_bidirectional: bool = Field(default=False)
    is_auto_generated: bool = Field(default=False)
    
    # Audit
    created_by: Optional[str] = Field(default=None, max_length=100)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
