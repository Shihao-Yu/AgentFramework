"""
SQLModel database models.
"""

from app.models.enums import (
    KnowledgeType,
    KnowledgeStatus,
    Visibility,
    StagingStatus,
    StagingAction,
    RelationshipType,
    VariantSource,
    NodeType,
    EdgeType,
    TenantRole,
)
from app.models.base import AuditMixin, TimestampMixin
from app.models.knowledge import (
    KnowledgeItem,
    KnowledgeVariant,
    KnowledgeRelationship,
    KnowledgeCategory,
)
from app.models.staging import StagingKnowledgeItem
from app.models.analytics import KnowledgeHit, KnowledgeVersion
from app.models.nodes import KnowledgeNode
from app.models.edges import KnowledgeEdge
from app.models.tenant import Tenant, UserTenantAccess

__all__ = [
    # Enums (legacy)
    "KnowledgeType",
    "KnowledgeStatus",
    "Visibility",
    "StagingStatus",
    "StagingAction",
    "RelationshipType",
    "VariantSource",
    # Enums (Knowledge Verse)
    "NodeType",
    "EdgeType",
    "TenantRole",
    # Mixins
    "AuditMixin",
    "TimestampMixin",
    # Knowledge models (legacy)
    "KnowledgeItem",
    "KnowledgeVariant",
    "KnowledgeRelationship",
    "KnowledgeCategory",
    # Staging (legacy)
    "StagingKnowledgeItem",
    # Analytics
    "KnowledgeHit",
    "KnowledgeVersion",
    # Knowledge Verse models
    "KnowledgeNode",
    "KnowledgeEdge",
    "Tenant",
    "UserTenantAccess",
]
