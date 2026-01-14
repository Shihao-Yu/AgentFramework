"""
SQLModel database models.

Unified model using knowledge_nodes, knowledge_edges, and node_variants.
"""

from app.models.enums import (
    KnowledgeStatus,
    Visibility,
    StagingStatus,
    StagingAction,
    VariantSource,
    NodeType,
    EdgeType,
    TenantRole,
)
from app.models.base import AuditMixin, TimestampMixin
from app.models.nodes import KnowledgeNode, NodeVariant
from app.models.edges import KnowledgeEdge
from app.models.tenant import Tenant, UserTenantAccess

__all__ = [
    # Enums
    "KnowledgeStatus",
    "Visibility",
    "StagingStatus",
    "StagingAction",
    "VariantSource",
    "NodeType",
    "EdgeType",
    "TenantRole",
    # Mixins
    "AuditMixin",
    "TimestampMixin",
    # Knowledge models
    "KnowledgeNode",
    "NodeVariant",
    "KnowledgeEdge",
    # Tenants
    "Tenant",
    "UserTenantAccess",
]
