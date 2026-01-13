"""
Schema Store Protocol and Implementations for ContextForge.

Provides a protocol for storing tenant schemas with versioning,
using PostgreSQL via KnowledgeNode models.

Implementations:
- SchemaStore: PostgreSQL-backed storage using KnowledgeNode
- InMemorySchemaStore: For testing

Usage:
    # Use PostgreSQL implementation
    store = SchemaStore(session)
    
    # Save schema
    version = await store.save_schema("tenant", "document", schema, created_by="admin")
    
    # Get schema
    schema = await store.get_schema("tenant", "document")
    
    # Rollback
    await store.set_active_version("tenant", "document", version=2)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from ..schema.yaml_schema import YAMLSchemaV1

logger = logging.getLogger(__name__)


@dataclass
class SchemaVersion:
    """Metadata about a schema version."""
    version: int
    created_at: datetime
    created_by: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None


@runtime_checkable
class SchemaStoreProtocol(Protocol):
    """
    Protocol for schema storage backends.
    
    Implement this protocol to create custom schema storage
    (e.g., S3, MongoDB, custom database, etc.)
    """
    
    async def get_schema(
        self, 
        tenant_id: str, 
        document_name: str,
        version: Optional[int] = None
    ) -> Optional[YAMLSchemaV1]:
        """
        Get schema for a tenant/document.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document/index name
            version: Specific version (None = active/latest)
            
        Returns:
            YAMLSchemaV1 or None if not found
        """
        ...
    
    async def save_schema(
        self,
        tenant_id: str,
        document_name: str,
        schema: YAMLSchemaV1,
        created_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """
        Save a new schema version.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document/index name
            schema: The schema to save
            created_by: Who created this version
            notes: Optional notes about this version
            
        Returns:
            The new version number
        """
        ...
    
    async def list_versions(
        self,
        tenant_id: str,
        document_name: str
    ) -> List[SchemaVersion]:
        """
        List all versions for a tenant/document.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document/index name
            
        Returns:
            List of SchemaVersion objects, newest first
        """
        ...
    
    async def set_active_version(
        self,
        tenant_id: str,
        document_name: str,
        version: int
    ) -> bool:
        """
        Set a specific version as active (rollback).
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document/index name
            version: Version to activate
            
        Returns:
            True if successful, False if version not found
        """
        ...
    
    async def delete_schema(
        self,
        tenant_id: str,
        document_name: str,
        version: Optional[int] = None
    ) -> bool:
        """
        Delete schema (specific version or all).
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document/index name
            version: Specific version to delete (None = all versions)
            
        Returns:
            True if deleted, False if not found
        """
        ...
    
    async def list_documents(self, tenant_id: str) -> List[str]:
        """
        List all documents for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of document names
        """
        ...


class BaseSchemaStore(ABC):
    """
    Abstract base class for schema stores.
    
    Provides common functionality and enforces the protocol.
    """
    
    @abstractmethod
    async def get_schema(
        self, 
        tenant_id: str, 
        document_name: str,
        version: Optional[int] = None
    ) -> Optional[YAMLSchemaV1]:
        """Get schema for a tenant/document."""
        pass
    
    @abstractmethod
    async def save_schema(
        self,
        tenant_id: str,
        document_name: str,
        schema: YAMLSchemaV1,
        created_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """Save a new schema version."""
        pass
    
    @abstractmethod
    async def list_versions(
        self,
        tenant_id: str,
        document_name: str
    ) -> List[SchemaVersion]:
        """List all versions for a tenant/document."""
        pass
    
    @abstractmethod
    async def set_active_version(
        self,
        tenant_id: str,
        document_name: str,
        version: int
    ) -> bool:
        """Set a specific version as active."""
        pass
    
    @abstractmethod
    async def delete_schema(
        self,
        tenant_id: str,
        document_name: str,
        version: Optional[int] = None
    ) -> bool:
        """Delete schema."""
        pass
    
    @abstractmethod
    async def list_documents(self, tenant_id: str) -> List[str]:
        """List all documents for a tenant."""
        pass


class InMemorySchemaStore(BaseSchemaStore):
    """
    In-memory schema store for testing.
    
    NOT for production use - data is lost on restart.
    """
    
    def __init__(self):
        # {(tenant_id, document_name): {version: (schema_yaml, metadata)}}
        self._schemas: Dict[tuple, Dict[int, tuple]] = {}
        self._active_versions: Dict[tuple, int] = {}
    
    async def get_schema(
        self, 
        tenant_id: str, 
        document_name: str,
        version: Optional[int] = None
    ) -> Optional[YAMLSchemaV1]:
        key = (tenant_id, document_name)
        
        if key not in self._schemas:
            return None
        
        if version is None:
            version = self._active_versions.get(key)
            if version is None:
                # Get latest
                version = max(self._schemas[key].keys()) if self._schemas[key] else None
        
        if version is None or version not in self._schemas[key]:
            return None
        
        schema_yaml, _ = self._schemas[key][version]
        return YAMLSchemaV1.from_yaml_string(schema_yaml)
    
    async def save_schema(
        self,
        tenant_id: str,
        document_name: str,
        schema: YAMLSchemaV1,
        created_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        key = (tenant_id, document_name)
        
        if key not in self._schemas:
            self._schemas[key] = {}
        
        # Get next version
        current_versions = self._schemas[key].keys()
        new_version = max(current_versions, default=0) + 1
        
        # Store schema
        metadata = SchemaVersion(
            version=new_version,
            created_at=datetime.utcnow(),
            created_by=created_by,
            is_active=True,
            notes=notes
        )
        self._schemas[key][new_version] = (schema.to_yaml_string(), metadata)
        self._active_versions[key] = new_version
        
        logger.info(f"Saved schema {tenant_id}/{document_name} version {new_version}")
        return new_version
    
    async def list_versions(
        self,
        tenant_id: str,
        document_name: str
    ) -> List[SchemaVersion]:
        key = (tenant_id, document_name)
        
        if key not in self._schemas:
            return []
        
        active_version = self._active_versions.get(key)
        versions = []
        
        for version, (_, metadata) in sorted(
            self._schemas[key].items(), 
            key=lambda x: x[0], 
            reverse=True
        ):
            metadata.is_active = (version == active_version)
            versions.append(metadata)
        
        return versions
    
    async def set_active_version(
        self,
        tenant_id: str,
        document_name: str,
        version: int
    ) -> bool:
        key = (tenant_id, document_name)
        
        if key not in self._schemas or version not in self._schemas[key]:
            return False
        
        self._active_versions[key] = version
        logger.info(f"Set active version {tenant_id}/{document_name} to {version}")
        return True
    
    async def delete_schema(
        self,
        tenant_id: str,
        document_name: str,
        version: Optional[int] = None
    ) -> bool:
        key = (tenant_id, document_name)
        
        if key not in self._schemas:
            return False
        
        if version is None:
            # Delete all
            del self._schemas[key]
            self._active_versions.pop(key, None)
            logger.info(f"Deleted all versions of {tenant_id}/{document_name}")
            return True
        else:
            # Delete specific version
            if version in self._schemas[key]:
                del self._schemas[key][version]
                if self._active_versions.get(key) == version:
                    # Set latest as active
                    if self._schemas[key]:
                        self._active_versions[key] = max(self._schemas[key].keys())
                    else:
                        self._active_versions.pop(key, None)
                logger.info(f"Deleted {tenant_id}/{document_name} version {version}")
                return True
            return False
    
    async def list_documents(self, tenant_id: str) -> List[str]:
        documents = set()
        for (t_id, doc_name) in self._schemas.keys():
            if t_id == tenant_id:
                documents.add(doc_name)
        return sorted(documents)


class SchemaStore(BaseSchemaStore):
    """
    PostgreSQL-backed schema store using KnowledgeNode models.
    
    Stores schemas as KnowledgeNode with node_type=SCHEMA_INDEX.
    Schema YAML is stored in the 'content' JSONB field.
    Version tracking via the 'version' field.
    
    Usage:
        store = SchemaStore(session)
        
        # Save schema
        version = await store.save_schema("acme", "orders", schema, created_by="admin")
        
        # Get schema
        schema = await store.get_schema("acme", "orders")
        
        # Rollback
        await store.set_active_version("acme", "orders", version=2)
    """
    
    def __init__(self, session: 'AsyncSession'):
        """
        Initialize PostgreSQL schema store.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def get_schema(
        self, 
        tenant_id: str, 
        document_name: str,
        version: Optional[int] = None
    ) -> Optional[YAMLSchemaV1]:
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == document_name,
            KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
        )
        
        if version is not None:
            stmt = stmt.where(KnowledgeNode.version == version)
        else:
            # Get active version (highest version with is_active metadata)
            # Order by is_active desc, version desc to get active first
            stmt = stmt.order_by(
                KnowledgeNode.version.desc()
            )
        
        stmt = stmt.limit(1)
        result = await self.session.execute(stmt)
        node = result.scalar_one_or_none()
        
        if node and node.content:
            schema_yaml = node.content.get("schema_yaml")
            if schema_yaml:
                return YAMLSchemaV1.from_yaml_string(schema_yaml)
        return None
    
    async def save_schema(
        self,
        tenant_id: str,
        document_name: str,
        schema: YAMLSchemaV1,
        created_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType, KnowledgeStatus
        from sqlalchemy import select, func
        
        # Get next version
        stmt = select(func.max(KnowledgeNode.version)).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == document_name,
            KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
        )
        result = await self.session.execute(stmt)
        current_max = result.scalar() or 0
        new_version = current_max + 1
        
        # Create content with schema YAML and metadata
        content: Dict[str, Any] = {
            "schema_yaml": schema.to_yaml_string(for_editing=False),
            "is_active": True,
            "notes": notes,
            "index_count": len(schema.indices),
            "concept_count": len(schema.concepts),
            "example_count": len(schema.examples),
        }
        
        # Build summary
        summary_parts = []
        if schema.indices:
            index_names = [idx.name for idx in schema.indices[:3]]
            summary_parts.append(f"Indices: {', '.join(index_names)}")
        if schema.concepts:
            concept_names = [c.name for c in schema.concepts[:3]]
            summary_parts.append(f"Concepts: {', '.join(concept_names)}")
        summary = "; ".join(summary_parts) or f"Schema v{new_version}"
        
        # Create new version node
        node = KnowledgeNode(
            tenant_id=tenant_id,
            node_type=NodeType.SCHEMA_INDEX,
            title=f"{document_name} Schema v{new_version}",
            summary=summary,
            content=content,
            dataset_name=document_name,
            version=new_version,
            status=KnowledgeStatus.PUBLISHED,
            source="contextforge",
            created_by=created_by,
        )
        self.session.add(node)
        await self.session.flush()
        
        logger.info(f"Saved schema {tenant_id}/{document_name} version {new_version}")
        return new_version
    
    async def list_versions(
        self,
        tenant_id: str,
        document_name: str
    ) -> List[SchemaVersion]:
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == document_name,
            KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
        ).order_by(KnowledgeNode.version.desc())
        
        result = await self.session.execute(stmt)
        nodes = result.scalars().all()
        
        # Find highest version (active)
        max_version = max((n.version for n in nodes), default=0)
        
        return [
            SchemaVersion(
                version=node.version,
                created_at=node.created_at,
                created_by=node.created_by,
                is_active=(node.version == max_version),
                notes=node.content.get("notes") if node.content else None,
            )
            for node in nodes
        ]
    
    async def set_active_version(
        self,
        tenant_id: str,
        document_name: str,
        version: int
    ) -> bool:
        """
        Set a specific version as active.
        
        Since we use version ordering (highest = active), this creates
        a new version that copies the target version's schema.
        """
        # Get the target version
        target_schema = await self.get_schema(tenant_id, document_name, version=version)
        
        if not target_schema:
            logger.warning(f"Version {version} not found for {tenant_id}/{document_name}")
            return False
        
        # Save as new version (making it active)
        await self.save_schema(
            tenant_id=tenant_id,
            document_name=document_name,
            schema=target_schema,
            notes=f"Rollback to version {version}",
        )
        
        logger.info(f"Set active version {tenant_id}/{document_name} to {version}")
        return True
    
    async def delete_schema(
        self,
        tenant_id: str,
        document_name: str,
        version: Optional[int] = None
    ) -> bool:
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import delete
        
        stmt = delete(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == document_name,
            KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
        )
        
        if version is not None:
            stmt = stmt.where(KnowledgeNode.version == version)
        
        result = await self.session.execute(stmt)
        deleted = result.rowcount > 0
        
        if deleted:
            logger.info(
                f"Deleted {tenant_id}/{document_name}" + 
                (f" version {version}" if version else " all versions")
            )
        return deleted
    
    async def list_documents(self, tenant_id: str) -> List[str]:
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select, distinct
        
        stmt = select(distinct(KnowledgeNode.dataset_name)).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
        ).order_by(KnowledgeNode.dataset_name)
        
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all() if row[0]]


def create_schema_store(session: 'AsyncSession') -> SchemaStore:
    """
    Factory function to create a SchemaStore.
    
    Args:
        session: SQLAlchemy async session
        
    Returns:
        Configured SchemaStore instance
    """
    return SchemaStore(session=session)
