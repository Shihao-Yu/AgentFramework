"""
Staging queue service for review workflow.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.staging import StagingKnowledgeItem
from app.models.knowledge import KnowledgeItem, KnowledgeVariant
from app.models.enums import (
    StagingStatus,
    StagingAction,
    KnowledgeStatus,
    Visibility,
)
from app.schemas.staging import (
    StagingListParams,
    StagingItemResponse,
    StagingCountsResponse,
    StagingListResponse,
)
from app.clients.embedding_client import EmbeddingClient


class StagingService:
    """Service for staging queue operations."""
    
    def __init__(self, session: AsyncSession, embedding_client: EmbeddingClient):
        self.session = session
        self.embedding_client = embedding_client
    
    async def list_items(
        self,
        params: StagingListParams
    ) -> StagingListResponse:
        """List staging items with filtering."""
        
        query = select(StagingKnowledgeItem)
        
        if params.status:
            query = query.where(StagingKnowledgeItem.status == params.status)
        
        if params.action:
            query = query.where(StagingKnowledgeItem.action == params.action)
        
        query = query.order_by(StagingKnowledgeItem.created_at.desc())
        offset = (params.page - 1) * params.limit
        query = query.offset(offset).limit(params.limit)
        
        result = await self.session.execute(query)
        items = result.scalars().all()
        
        # Get counts
        counts = await self.get_counts()
        
        return StagingListResponse(
            data=[StagingItemResponse.model_validate(item) for item in items],
            counts=counts
        )
    
    async def get_counts(self) -> StagingCountsResponse:
        """Get count of pending items by action type."""
        
        counts = {"new": 0, "merge": 0, "add_variant": 0}
        
        for action in StagingAction:
            query = select(func.count(StagingKnowledgeItem.id)).where(
                StagingKnowledgeItem.status == StagingStatus.PENDING,
                StagingKnowledgeItem.action == action
            )
            result = await self.session.execute(query)
            counts[action.value] = result.scalar() or 0
        
        return StagingCountsResponse(**counts)
    
    async def get_item(self, staging_id: int) -> Optional[StagingKnowledgeItem]:
        """Get a single staging item by ID."""
        return await self.session.get(StagingKnowledgeItem, staging_id)
    
    async def get_merge_target(self, staging_id: int) -> Optional[KnowledgeItem]:
        """Get the knowledge item that would be merged with."""
        
        staging = await self.get_item(staging_id)
        if not staging or not staging.merge_with_id:
            return None
        
        query = select(KnowledgeItem).where(
            KnowledgeItem.id == staging.merge_with_id,
            KnowledgeItem.is_deleted == False
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def approve(
        self,
        staging_id: int,
        reviewed_by: str,
        edits: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Approve a staging item and sync to production."""
        
        staging = await self.get_item(staging_id)
        if not staging:
            raise ValueError(f"Staging item {staging_id} not found")
        
        if staging.status != StagingStatus.PENDING:
            raise ValueError(f"Staging item {staging_id} is not pending")
        
        # Apply edits if provided
        if edits:
            if "title" in edits:
                staging.title = edits["title"]
            if "content" in edits:
                staging.content = {**staging.content, **edits["content"]}
            if "tags" in edits:
                staging.tags = edits["tags"]
        
        created_item_id = None
        
        if staging.action == StagingAction.NEW:
            created_item_id = await self._create_new_item(staging, reviewed_by)
        
        elif staging.action == StagingAction.MERGE:
            created_item_id = await self._merge_item(staging, reviewed_by)
        
        elif staging.action == StagingAction.ADD_VARIANT:
            await self._add_variant(staging, reviewed_by)
            created_item_id = staging.merge_with_id
        
        # Update staging status
        staging.status = StagingStatus.APPROVED
        staging.reviewed_by = reviewed_by
        staging.reviewed_at = datetime.utcnow()
        
        await self.session.commit()
        
        return {
            "success": True,
            "staging_id": staging_id,
            "created_item_id": created_item_id
        }
    
    async def reject(
        self,
        staging_id: int,
        reviewed_by: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reject a staging item."""
        
        staging = await self.get_item(staging_id)
        if not staging:
            raise ValueError(f"Staging item {staging_id} not found")
        
        if staging.status != StagingStatus.PENDING:
            raise ValueError(f"Staging item {staging_id} is not pending")
        
        staging.status = StagingStatus.REJECTED
        staging.reviewed_by = reviewed_by
        staging.reviewed_at = datetime.utcnow()
        staging.review_notes = reason
        
        await self.session.commit()
        
        return {"success": True, "staging_id": staging_id}
    
    async def _create_new_item(
        self,
        staging: StagingKnowledgeItem,
        created_by: str
    ) -> int:
        """Create a new knowledge item from staging."""
        
        item = KnowledgeItem(
            knowledge_type=staging.knowledge_type,
            category_id=staging.category_id,
            title=staging.title,
            summary=staging.summary,
            content=staging.content,
            tags=staging.tags,
            visibility=Visibility.INTERNAL,
            status=KnowledgeStatus.PUBLISHED,
            metadata_={
                "source_staging_id": staging.id,
                "source_ticket_id": staging.source_ticket_id,
                "promoted_at": datetime.utcnow().isoformat(),
                "promoted_by": created_by
            },
            created_by=created_by,
        )
        
        self.session.add(item)
        await self.session.flush()
        
        # Copy embedding from staging if exists
        await self.session.execute(
            text("""
                UPDATE agent.knowledge_items k
                SET embedding = s.embedding
                FROM agent.staging_knowledge_items s
                WHERE k.id = :item_id AND s.id = :staging_id
            """),
            {"item_id": item.id, "staging_id": staging.id}
        )
        
        return item.id
    
    async def _merge_item(
        self,
        staging: StagingKnowledgeItem,
        updated_by: str
    ) -> int:
        """Merge staging content into existing knowledge item."""
        
        existing = await self.session.get(KnowledgeItem, staging.merge_with_id)
        if not existing:
            raise ValueError(f"Merge target {staging.merge_with_id} not found")
        
        # Store snapshot before merge
        staging.metadata_["original_before_merge"] = {
            "id": existing.id,
            "title": existing.title,
            "content": existing.content,
            "tags": existing.tags,
            "captured_at": datetime.utcnow().isoformat()
        }
        
        # Update existing item with new content
        # The trigger will automatically create a version
        existing.content = staging.content
        existing.tags = list(set(existing.tags + staging.tags))
        existing.updated_by = updated_by
        existing.updated_at = datetime.utcnow()
        existing.graph_version += 1
        
        # Also add the question as a variant if it's an FAQ
        if staging.knowledge_type.value == "faq" and "question" in staging.content:
            await self._add_variant_direct(
                existing.id,
                staging.content["question"],
                staging.source_ticket_id,
                updated_by
            )
        
        return existing.id
    
    async def _add_variant(
        self,
        staging: StagingKnowledgeItem,
        created_by: str
    ) -> None:
        """Add a variant from staging to existing item."""
        
        variant_text = staging.content.get("question", staging.title)
        
        await self._add_variant_direct(
            staging.merge_with_id,
            variant_text,
            staging.source_ticket_id,
            created_by
        )
    
    async def _add_variant_direct(
        self,
        knowledge_item_id: int,
        variant_text: str,
        source_reference: Optional[str],
        created_by: str
    ) -> None:
        """Directly add a variant to a knowledge item."""
        
        # Check if variant already exists
        existing_query = select(KnowledgeVariant).where(
            KnowledgeVariant.knowledge_item_id == knowledge_item_id,
            KnowledgeVariant.variant_text == variant_text
        )
        existing = await self.session.execute(existing_query)
        if existing.scalar_one_or_none():
            return  # Skip duplicate
        
        # Generate embedding for variant
        embedding = await self.embedding_client.embed(variant_text)
        
        variant = KnowledgeVariant(
            knowledge_item_id=knowledge_item_id,
            variant_text=variant_text,
            source="pipeline",
            source_reference=source_reference,
            created_by=created_by,
        )
        
        self.session.add(variant)
        await self.session.flush()
        
        # Set embedding
        await self.session.execute(
            text("""
                UPDATE agent.knowledge_variants 
                SET embedding = :embedding::vector 
                WHERE id = :id
            """),
            {"id": variant.id, "embedding": embedding}
        )
