"""
Relationship management service.
"""

from datetime import datetime
from typing import List, Optional
from sqlmodel import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeItem, KnowledgeRelationship
from app.models.enums import RelationshipType
from app.schemas.knowledge import (
    RelationshipCreate,
    RelationshipResponse,
    RelatedItemResponse,
)


class RelationshipService:
    """Service for knowledge relationship operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def list_relationships(
        self,
        knowledge_item_id: int,
        include_reverse: bool = True
    ) -> List[RelationshipResponse]:
        """List all relationships for a knowledge item."""
        
        if include_reverse:
            query = select(KnowledgeRelationship).where(
                or_(
                    KnowledgeRelationship.source_id == knowledge_item_id,
                    KnowledgeRelationship.target_id == knowledge_item_id
                )
            )
        else:
            query = select(KnowledgeRelationship).where(
                KnowledgeRelationship.source_id == knowledge_item_id
            )
        
        query = query.order_by(KnowledgeRelationship.created_at.desc())
        
        result = await self.session.execute(query)
        relationships = result.scalars().all()
        
        return [RelationshipResponse.model_validate(r) for r in relationships]
    
    async def get_related_items(
        self,
        knowledge_item_id: int
    ) -> List[RelatedItemResponse]:
        """Get related knowledge items with relationship info."""
        
        # Get outgoing relationships
        query = select(
            KnowledgeRelationship,
            KnowledgeItem
        ).join(
            KnowledgeItem,
            KnowledgeItem.id == KnowledgeRelationship.target_id
        ).where(
            KnowledgeRelationship.source_id == knowledge_item_id,
            KnowledgeItem.is_deleted == False
        )
        
        result = await self.session.execute(query)
        
        related = []
        for rel, item in result.fetchall():
            related.append(RelatedItemResponse(
                id=item.id,
                knowledge_type=item.knowledge_type,
                title=item.title,
                relationship_type=rel.relationship_type,
                is_auto_generated=rel.is_auto_generated
            ))
        
        # Also get incoming bidirectional relationships
        reverse_query = select(
            KnowledgeRelationship,
            KnowledgeItem
        ).join(
            KnowledgeItem,
            KnowledgeItem.id == KnowledgeRelationship.source_id
        ).where(
            KnowledgeRelationship.target_id == knowledge_item_id,
            KnowledgeRelationship.is_bidirectional == True,
            KnowledgeItem.is_deleted == False
        )
        
        reverse_result = await self.session.execute(reverse_query)
        
        for rel, item in reverse_result.fetchall():
            # Avoid duplicates
            if not any(r.id == item.id for r in related):
                related.append(RelatedItemResponse(
                    id=item.id,
                    knowledge_type=item.knowledge_type,
                    title=item.title,
                    relationship_type=rel.relationship_type,
                    is_auto_generated=rel.is_auto_generated
                ))
        
        return related
    
    async def create_relationship(
        self,
        source_id: int,
        data: RelationshipCreate,
        created_by: Optional[str] = None
    ) -> RelationshipResponse:
        """Create a new relationship between knowledge items."""
        
        # Verify source item exists
        source = await self.session.get(KnowledgeItem, source_id)
        if not source or source.is_deleted:
            raise ValueError(f"Source item {source_id} not found")
        
        # Verify target item exists
        target = await self.session.get(KnowledgeItem, data.target_id)
        if not target or target.is_deleted:
            raise ValueError(f"Target item {data.target_id} not found")
        
        # Check for existing relationship
        existing_query = select(KnowledgeRelationship).where(
            KnowledgeRelationship.source_id == source_id,
            KnowledgeRelationship.target_id == data.target_id
        )
        existing = await self.session.execute(existing_query)
        if existing.scalar_one_or_none():
            raise ValueError("Relationship already exists")
        
        relationship = KnowledgeRelationship(
            source_id=source_id,
            target_id=data.target_id,
            relationship_type=data.relationship_type,
            weight=data.weight or 1.0,
            is_bidirectional=data.is_bidirectional or False,
            is_auto_generated=False,
            created_by=created_by,
        )
        
        self.session.add(relationship)
        
        # Update graph versions
        source.graph_version += 1
        target.graph_version += 1
        
        await self.session.commit()
        await self.session.refresh(relationship)
        
        return RelationshipResponse.model_validate(relationship)
    
    async def delete_relationship(
        self,
        relationship_id: int
    ) -> bool:
        """Delete a relationship."""
        
        relationship = await self.session.get(KnowledgeRelationship, relationship_id)
        if not relationship:
            return False
        
        # Update graph versions
        source = await self.session.get(KnowledgeItem, relationship.source_id)
        target = await self.session.get(KnowledgeItem, relationship.target_id)
        
        if source:
            source.graph_version += 1
        if target:
            target.graph_version += 1
        
        await self.session.delete(relationship)
        await self.session.commit()
        
        return True
    
    async def get_relationship(
        self,
        relationship_id: int
    ) -> Optional[KnowledgeRelationship]:
        """Get a single relationship by ID."""
        return await self.session.get(KnowledgeRelationship, relationship_id)
