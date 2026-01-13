"""
Version history service.
"""

from datetime import datetime
from typing import List, Optional
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.knowledge import KnowledgeItem
from app.models.analytics import KnowledgeVersion
from app.schemas.knowledge import VersionResponse


class VersionService:
    """Service for knowledge version history operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def list_versions(
        self,
        knowledge_item_id: int,
        limit: int = 50
    ) -> List[VersionResponse]:
        """List version history for a knowledge item."""
        
        query = select(KnowledgeVersion).where(
            KnowledgeVersion.knowledge_item_id == knowledge_item_id
        ).order_by(
            KnowledgeVersion.version_number.desc()
        ).limit(limit)
        
        result = await self.session.execute(query)
        versions = result.scalars().all()
        
        return [VersionResponse.model_validate(v) for v in versions]
    
    async def get_version(
        self,
        knowledge_item_id: int,
        version_number: int
    ) -> Optional[VersionResponse]:
        """Get a specific version of a knowledge item."""
        
        query = select(KnowledgeVersion).where(
            KnowledgeVersion.knowledge_item_id == knowledge_item_id,
            KnowledgeVersion.version_number == version_number
        )
        
        result = await self.session.execute(query)
        version = result.scalar_one_or_none()
        
        if version:
            return VersionResponse.model_validate(version)
        return None
    
    async def rollback_to_version(
        self,
        knowledge_item_id: int,
        version_number: int,
        rolled_back_by: Optional[str] = None
    ) -> Optional[KnowledgeItem]:
        """
        Rollback a knowledge item to a previous version.
        
        This creates a new version capturing the current state,
        then restores the item to the specified version.
        """
        
        # Get the target version
        version = await self.session.execute(
            select(KnowledgeVersion).where(
                KnowledgeVersion.knowledge_item_id == knowledge_item_id,
                KnowledgeVersion.version_number == version_number
            )
        )
        target_version = version.scalar_one_or_none()
        
        if not target_version:
            raise ValueError(f"Version {version_number} not found")
        
        # Get the current item
        item = await self.session.get(KnowledgeItem, knowledge_item_id)
        if not item or item.is_deleted:
            raise ValueError(f"Knowledge item {knowledge_item_id} not found")
        
        # The update trigger will automatically save current state as a new version
        # Restore from target version
        item.title = target_version.title
        item.summary = target_version.summary
        item.content = target_version.content
        item.tags = target_version.tags or []
        item.updated_by = rolled_back_by
        item.updated_at = datetime.utcnow()
        item.graph_version += 1
        
        await self.session.commit()
        await self.session.refresh(item)
        
        # Update the newly created version to indicate it was a rollback
        await self.session.execute(
            text("""
                UPDATE agent.knowledge_versions
                SET change_type = 'restore',
                    change_reason = :reason
                WHERE knowledge_item_id = :item_id
                  AND version_number = (
                      SELECT MAX(version_number) 
                      FROM agent.knowledge_versions 
                      WHERE knowledge_item_id = :item_id
                  )
            """),
            {
                "item_id": knowledge_item_id,
                "reason": f"Rolled back to version {version_number}"
            }
        )
        
        await self.session.commit()
        
        return item
    
    async def get_latest_version_number(
        self,
        knowledge_item_id: int
    ) -> int:
        """Get the latest version number for an item."""
        
        result = await self.session.execute(
            select(func.max(KnowledgeVersion.version_number)).where(
                KnowledgeVersion.knowledge_item_id == knowledge_item_id
            )
        )
        return result.scalar() or 0
