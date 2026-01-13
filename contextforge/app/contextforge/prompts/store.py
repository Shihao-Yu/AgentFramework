"""
PostgreSQL-backed Prompt Store for ContextForge.

Stores prompt templates as KnowledgeNode with node_type=PROMPT_TEMPLATE.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import KnowledgeStatus, NodeType, Visibility

from .models import (
    PromptCategory,
    PromptDialect,
    PromptTemplate,
    PromptVersion,
)

logger = logging.getLogger(__name__)


def _template_to_node_content(template: PromptTemplate) -> Dict[str, Any]:
    """Convert PromptTemplate to KnowledgeNode content JSON."""
    return {
        "_type": "prompt_template",
        "_version": "1.0",
        "template_id": template.id,
        "name": template.name,
        "category": template.category,
        "dialect": template.dialect,
        "content": template.content,
        "variables": template.variables,
        "description": template.description,
        "version": template.version,
        "is_active": template.is_active,
        "metadata": template.metadata,
        "created_by": template.created_by,
    }


def _node_content_to_template(
    content: Dict[str, Any],
    node_id: int,
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None,
) -> PromptTemplate:
    """Reconstruct PromptTemplate from KnowledgeNode content."""
    return PromptTemplate(
        id=content.get("template_id") or str(node_id),
        name=content["name"],
        category=PromptCategory(content["category"]),
        dialect=PromptDialect(content.get("dialect", "default")),
        content=content["content"],
        variables=content.get("variables", []),
        description=content.get("description"),
        version=content.get("version", 1),
        is_active=content.get("is_active", True),
        metadata=content.get("metadata", {}),
        created_at=created_at,
        updated_at=updated_at,
        created_by=content.get("created_by"),
    )


class PostgresPromptStore:
    """
    PostgreSQL-backed store for prompt templates.
    
    Stores prompts as KnowledgeNode with node_type=PROMPT_TEMPLATE.
    Supports versioning and dialect-specific templates.
    """
    
    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id
        self._dataset_name = "prompt_templates"
    
    async def save_template(
        self,
        session: AsyncSession,
        template: PromptTemplate,
        create_version: bool = True,
    ) -> PromptTemplate:
        """
        Save or update a prompt template.
        
        Args:
            session: Async database session
            template: Template to save
            create_version: Whether to create a version history entry
            
        Returns:
            Saved template with updated fields
        """
        from app.models.nodes import KnowledgeNode
        
        storage_key = f"{template.name}_{template.dialect}"
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == self.tenant_id,
            KnowledgeNode.dataset_name == self._dataset_name,
            KnowledgeNode.source_reference == storage_key,
            KnowledgeNode.node_type == NodeType.PROMPT_TEMPLATE,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        now = datetime.utcnow()
        
        if existing:
            old_version = existing.content.get("version", 1)
            new_version = old_version + 1 if create_version else old_version
            
            template.version = new_version
            template.updated_at = now
            
            existing.content = _template_to_node_content(template)
            existing.updated_at = now
            existing.version = new_version
            
            await session.flush()
            
            if create_version:
                await self._create_version_entry(
                    session, template, old_version, existing.content.get("content", "")
                )
            
            template.id = template.id or str(existing.id)
            return template
        
        template.id = template.id or str(uuid4())
        template.version = 1
        template.created_at = now
        template.updated_at = now
        
        node = KnowledgeNode(
            tenant_id=self.tenant_id,
            node_type=NodeType.PROMPT_TEMPLATE,
            title=f"Prompt: {template.name} ({template.dialect})",
            summary=template.description,
            content=_template_to_node_content(template),
            tags=[template.category, template.dialect],
            dataset_name=self._dataset_name,
            source_reference=storage_key,
            visibility=Visibility.INTERNAL,
            status=KnowledgeStatus.PUBLISHED,
            source="contextforge",
            version=1,
        )
        
        session.add(node)
        await session.flush()
        
        return template
    
    async def _create_version_entry(
        self,
        session: AsyncSession,
        template: PromptTemplate,
        old_version: int,
        old_content: str,
    ) -> None:
        """Create a version history entry for audit trail."""
        from app.models.nodes import KnowledgeNode
        
        version_key = f"{template.name}_{template.dialect}_v{old_version}"
        
        version_content = {
            "_type": "prompt_version",
            "template_id": template.id,
            "template_name": template.name,
            "version": old_version,
            "content": old_content,
            "variables": template.variables,
            "is_active": False,
            "created_by": template.created_by,
        }
        
        node = KnowledgeNode(
            tenant_id=self.tenant_id,
            node_type=NodeType.PROMPT_TEMPLATE,
            title=f"Prompt Version: {template.name} v{old_version}",
            summary=f"Version {old_version} of {template.name}",
            content=version_content,
            tags=[template.category, template.dialect, "version_history"],
            dataset_name=self._dataset_name,
            source_reference=version_key,
            visibility=Visibility.INTERNAL,
            status=KnowledgeStatus.ARCHIVED,
            source="contextforge",
            version=old_version,
        )
        
        session.add(node)
    
    async def get_template(
        self,
        session: AsyncSession,
        name: str,
        dialect: PromptDialect = PromptDialect.DEFAULT,
        version: Optional[int] = None,
    ) -> Optional[PromptTemplate]:
        """
        Get a prompt template by name and dialect.
        
        Args:
            session: Async database session
            name: Template name
            dialect: Target dialect
            version: Specific version (None = latest active)
            
        Returns:
            PromptTemplate if found, None otherwise
        """
        from app.models.nodes import KnowledgeNode
        
        storage_key = f"{name}_{dialect}"
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == self.tenant_id,
            KnowledgeNode.dataset_name == self._dataset_name,
            KnowledgeNode.source_reference == storage_key,
            KnowledgeNode.node_type == NodeType.PROMPT_TEMPLATE,
        )
        
        if version is not None:
            stmt = stmt.where(KnowledgeNode.version == version)
        
        result = await session.execute(stmt)
        node = result.scalar_one_or_none()
        
        if not node:
            return None
        
        return _node_content_to_template(
            node.content,
            node.id,
            node.created_at,
            node.updated_at,
        )
    
    async def get_template_with_fallback(
        self,
        session: AsyncSession,
        name: str,
        dialect: PromptDialect,
    ) -> Optional[PromptTemplate]:
        """
        Get template with dialect fallback.
        
        Tries: specific dialect -> default dialect -> None
        """
        template = await self.get_template(session, name, dialect)
        if template:
            return template
        
        if dialect != PromptDialect.DEFAULT:
            return await self.get_template(session, name, PromptDialect.DEFAULT)
        
        return None
    
    async def list_templates(
        self,
        session: AsyncSession,
        category: Optional[PromptCategory] = None,
        dialect: Optional[PromptDialect] = None,
        active_only: bool = True,
    ) -> List[PromptTemplate]:
        """
        List all templates with optional filtering.
        
        Args:
            session: Async database session
            category: Filter by category
            dialect: Filter by dialect
            active_only: Only return active (non-archived) templates
            
        Returns:
            List of matching templates
        """
        from app.models.nodes import KnowledgeNode
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == self.tenant_id,
            KnowledgeNode.dataset_name == self._dataset_name,
            KnowledgeNode.node_type == NodeType.PROMPT_TEMPLATE,
        )
        
        if active_only:
            stmt = stmt.where(KnowledgeNode.status == KnowledgeStatus.PUBLISHED)
        
        if category:
            stmt = stmt.where(KnowledgeNode.tags.contains([category]))
        
        if dialect:
            stmt = stmt.where(KnowledgeNode.tags.contains([dialect]))
        
        result = await session.execute(stmt)
        nodes = result.scalars().all()
        
        templates = []
        for node in nodes:
            content = node.content
            if content.get("_type") != "prompt_template":
                continue
            templates.append(
                _node_content_to_template(
                    content, node.id, node.created_at, node.updated_at
                )
            )
        
        return templates
    
    async def delete_template(
        self,
        session: AsyncSession,
        name: str,
        dialect: PromptDialect = PromptDialect.DEFAULT,
        delete_versions: bool = False,
    ) -> bool:
        """
        Delete a prompt template.
        
        Args:
            session: Async database session
            name: Template name
            dialect: Template dialect
            delete_versions: Also delete version history
            
        Returns:
            True if deleted, False if not found
        """
        from app.models.nodes import KnowledgeNode
        
        storage_key = f"{name}_{dialect}"
        
        stmt = delete(KnowledgeNode).where(
            KnowledgeNode.tenant_id == self.tenant_id,
            KnowledgeNode.dataset_name == self._dataset_name,
            KnowledgeNode.source_reference == storage_key,
            KnowledgeNode.node_type == NodeType.PROMPT_TEMPLATE,
        )
        
        result = await session.execute(stmt)
        deleted = result.rowcount > 0
        
        if deleted and delete_versions:
            version_pattern = f"{name}_{dialect}_v%"
            stmt = delete(KnowledgeNode).where(
                KnowledgeNode.tenant_id == self.tenant_id,
                KnowledgeNode.dataset_name == self._dataset_name,
                KnowledgeNode.source_reference.like(version_pattern),
                KnowledgeNode.node_type == NodeType.PROMPT_TEMPLATE,
            )
            await session.execute(stmt)
        
        return deleted
    
    async def get_version_history(
        self,
        session: AsyncSession,
        name: str,
        dialect: PromptDialect = PromptDialect.DEFAULT,
        limit: int = 10,
    ) -> List[PromptVersion]:
        """
        Get version history for a template.
        
        Args:
            session: Async database session
            name: Template name
            dialect: Template dialect
            limit: Max versions to return
            
        Returns:
            List of PromptVersion entries, newest first
        """
        from app.models.nodes import KnowledgeNode
        
        version_pattern = f"{name}_{dialect}_v%"
        
        stmt = (
            select(KnowledgeNode)
            .where(
                KnowledgeNode.tenant_id == self.tenant_id,
                KnowledgeNode.dataset_name == self._dataset_name,
                KnowledgeNode.source_reference.like(version_pattern),
                KnowledgeNode.node_type == NodeType.PROMPT_TEMPLATE,
            )
            .order_by(KnowledgeNode.version.desc())
            .limit(limit)
        )
        
        result = await session.execute(stmt)
        nodes = result.scalars().all()
        
        versions = []
        for node in nodes:
            content = node.content
            if content.get("_type") != "prompt_version":
                continue
            
            versions.append(
                PromptVersion(
                    id=str(node.id),
                    template_id=content.get("template_id", ""),
                    template_name=content.get("template_name", name),
                    version=content.get("version", node.version),
                    content=content.get("content", ""),
                    variables=content.get("variables", []),
                    is_active=False,
                    created_at=node.created_at or datetime.utcnow(),
                    created_by=content.get("created_by"),
                )
            )
        
        return versions
    
    async def bulk_save_templates(
        self,
        session: AsyncSession,
        templates: List[PromptTemplate],
        create_versions: bool = False,
    ) -> int:
        """
        Bulk save multiple templates.
        
        Args:
            session: Async database session
            templates: Templates to save
            create_versions: Whether to create version history
            
        Returns:
            Number of templates saved
        """
        saved = 0
        for template in templates:
            try:
                await self.save_template(session, template, create_versions)
                saved += 1
            except Exception as e:
                logger.warning(f"Failed to save template {template.name}: {e}")
        
        return saved
