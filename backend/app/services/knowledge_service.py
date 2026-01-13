"""
Knowledge item CRUD service.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlmodel import select, func, col
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, text

from app.models.knowledge import KnowledgeItem, KnowledgeVariant
from app.models.enums import KnowledgeType, KnowledgeStatus, Visibility
from app.schemas.knowledge import (
    KnowledgeItemCreate,
    KnowledgeItemUpdate,
    KnowledgeListParams,
    KnowledgeItemResponse,
)
from app.schemas.common import PaginatedResponse
from app.clients.embedding_client import EmbeddingClient


class KnowledgeService:
    """Service for knowledge item CRUD operations."""
    
    def __init__(self, session: AsyncSession, embedding_client: EmbeddingClient):
        self.session = session
        self.embedding_client = embedding_client
    
    async def list_items(
        self,
        params: KnowledgeListParams
    ) -> PaginatedResponse[KnowledgeItemResponse]:
        """List knowledge items with filtering and pagination."""
        
        # Base query
        query = select(KnowledgeItem).where(KnowledgeItem.is_deleted == False)
        count_query = select(func.count(KnowledgeItem.id)).where(
            KnowledgeItem.is_deleted == False
        )
        
        # Apply filters
        if params.knowledge_type:
            query = query.where(KnowledgeItem.knowledge_type == params.knowledge_type)
            count_query = count_query.where(
                KnowledgeItem.knowledge_type == params.knowledge_type
            )
        
        if params.status:
            query = query.where(KnowledgeItem.status == params.status)
            count_query = count_query.where(KnowledgeItem.status == params.status)
        
        if params.visibility:
            query = query.where(KnowledgeItem.visibility == params.visibility)
            count_query = count_query.where(KnowledgeItem.visibility == params.visibility)
        
        if params.tags:
            query = query.where(KnowledgeItem.tags.overlap(params.tags))
            count_query = count_query.where(KnowledgeItem.tags.overlap(params.tags))
        
        if params.category_id:
            query = query.where(KnowledgeItem.category_id == params.category_id)
            count_query = count_query.where(
                KnowledgeItem.category_id == params.category_id
            )
        
        if params.search:
            search_filter = or_(
                KnowledgeItem.title.ilike(f"%{params.search}%"),
                KnowledgeItem.summary.ilike(f"%{params.search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Get total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination and ordering
        query = query.order_by(KnowledgeItem.created_at.desc())
        offset = (params.page - 1) * params.limit
        query = query.offset(offset).limit(params.limit)
        
        # Execute
        result = await self.session.execute(query)
        items = result.scalars().all()
        
        # Convert to response models
        response_items = [
            KnowledgeItemResponse.model_validate(item) for item in items
        ]
        
        return PaginatedResponse(
            data=response_items,
            total=total,
            page=params.page,
            limit=params.limit,
            total_pages=(total + params.limit - 1) // params.limit if total > 0 else 0
        )
    
    async def get_item(self, item_id: int) -> Optional[KnowledgeItem]:
        """Get a single knowledge item by ID."""
        query = select(KnowledgeItem).where(
            KnowledgeItem.id == item_id,
            KnowledgeItem.is_deleted == False
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def create_item(
        self,
        data: KnowledgeItemCreate,
        created_by: Optional[str] = None
    ) -> KnowledgeItem:
        """Create a new knowledge item with embedding."""
        
        # Generate embedding from title + content
        embed_text = self._get_embed_text(data.title, data.content, data.knowledge_type)
        embedding = await self.embedding_client.embed(embed_text)
        
        item = KnowledgeItem(
            knowledge_type=data.knowledge_type,
            category_id=data.category_id,
            title=data.title,
            summary=data.summary,
            content=data.content,
            tags=data.tags or [],
            visibility=data.visibility or Visibility.INTERNAL,
            status=data.status or KnowledgeStatus.DRAFT,
            metadata_=data.metadata_ or {},
            created_by=created_by,
        )
        
        self.session.add(item)
        await self.session.flush()
        
        # Set embedding via raw SQL (pgvector)
        await self.session.execute(
            text("""
                UPDATE agent.knowledge_items 
                SET embedding = :embedding::vector 
                WHERE id = :id
            """),
            {"id": item.id, "embedding": embedding}
        )
        
        await self.session.commit()
        await self.session.refresh(item)
        
        return item
    
    async def update_item(
        self,
        item_id: int,
        data: KnowledgeItemUpdate,
        updated_by: Optional[str] = None
    ) -> Optional[KnowledgeItem]:
        """Update a knowledge item."""
        
        item = await self.get_item(item_id)
        if not item:
            return None
        
        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        content_changed = False
        
        for field, value in update_data.items():
            if field == "metadata_":
                setattr(item, "metadata_", value)
            else:
                setattr(item, field, value)
            
            if field in ("title", "content", "summary"):
                content_changed = True
        
        item.updated_by = updated_by
        item.updated_at = datetime.utcnow()
        item.graph_version += 1
        
        await self.session.flush()
        
        # Regenerate embedding if content changed
        if content_changed:
            embed_text = self._get_embed_text(
                item.title, item.content, item.knowledge_type
            )
            embedding = await self.embedding_client.embed(embed_text)
            
            await self.session.execute(
                text("""
                    UPDATE agent.knowledge_items 
                    SET embedding = :embedding::vector 
                    WHERE id = :id
                """),
                {"id": item.id, "embedding": embedding}
            )
        
        await self.session.commit()
        await self.session.refresh(item)
        
        return item
    
    async def delete_item(
        self,
        item_id: int,
        deleted_by: Optional[str] = None
    ) -> bool:
        """Soft delete a knowledge item."""
        
        item = await self.get_item(item_id)
        if not item:
            return False
        
        item.is_deleted = True
        item.updated_by = deleted_by
        item.updated_at = datetime.utcnow()
        
        await self.session.commit()
        return True
    
    def _get_embed_text(
        self,
        title: str,
        content: Dict[str, Any],
        knowledge_type: KnowledgeType
    ) -> str:
        """Construct text for embedding based on knowledge type."""
        
        parts = [title]
        
        if knowledge_type == KnowledgeType.FAQ:
            if "question" in content:
                parts.append(content["question"])
            if "answer" in content:
                parts.append(content["answer"])
        
        elif knowledge_type == KnowledgeType.BUSINESS_RULE:
            if "condition" in content:
                parts.append(content["condition"])
            if "action" in content:
                parts.append(content["action"])
        
        elif knowledge_type == KnowledgeType.PROCEDURE:
            if "steps" in content:
                for step in content["steps"]:
                    if isinstance(step, dict) and "action" in step:
                        parts.append(step["action"])
        
        elif knowledge_type == KnowledgeType.POLICY:
            if "body" in content:
                parts.append(content["body"])
        
        elif knowledge_type == KnowledgeType.CONTEXT:
            if "description" in content:
                parts.append(content["description"])
        
        else:
            # Generic handling for other types
            for key in ["description", "body", "content", "summary", "text"]:
                if key in content and content[key]:
                    parts.append(str(content[key]))
        
        return "\n".join(parts)
