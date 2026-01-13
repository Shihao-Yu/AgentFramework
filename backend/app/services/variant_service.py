"""
Variant management service.
"""

from datetime import datetime
from typing import List, Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.knowledge import KnowledgeItem, KnowledgeVariant
from app.schemas.knowledge import VariantCreate, VariantResponse
from app.clients.embedding_client import EmbeddingClient


class VariantService:
    """Service for knowledge variant operations."""
    
    def __init__(self, session: AsyncSession, embedding_client: EmbeddingClient):
        self.session = session
        self.embedding_client = embedding_client
    
    async def list_variants(
        self,
        knowledge_item_id: int
    ) -> List[VariantResponse]:
        """List all variants for a knowledge item."""
        
        query = select(KnowledgeVariant).where(
            KnowledgeVariant.knowledge_item_id == knowledge_item_id
        ).order_by(KnowledgeVariant.created_at.desc())
        
        result = await self.session.execute(query)
        variants = result.scalars().all()
        
        return [VariantResponse.model_validate(v) for v in variants]
    
    async def create_variant(
        self,
        knowledge_item_id: int,
        data: VariantCreate,
        created_by: Optional[str] = None
    ) -> VariantResponse:
        """Create a new variant for a knowledge item."""
        
        # Verify knowledge item exists
        item = await self.session.get(KnowledgeItem, knowledge_item_id)
        if not item or item.is_deleted:
            raise ValueError(f"Knowledge item {knowledge_item_id} not found")
        
        # Check for duplicate
        existing_query = select(KnowledgeVariant).where(
            KnowledgeVariant.knowledge_item_id == knowledge_item_id,
            KnowledgeVariant.variant_text == data.variant_text
        )
        existing = await self.session.execute(existing_query)
        if existing.scalar_one_or_none():
            raise ValueError("Variant with this text already exists")
        
        # Generate embedding
        embedding = await self.embedding_client.embed(data.variant_text)
        
        variant = KnowledgeVariant(
            knowledge_item_id=knowledge_item_id,
            variant_text=data.variant_text,
            source=data.source or "manual",
            source_reference=data.source_reference,
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
        
        # Update parent item's graph version
        item.graph_version += 1
        
        await self.session.commit()
        await self.session.refresh(variant)
        
        return VariantResponse.model_validate(variant)
    
    async def delete_variant(
        self,
        variant_id: int
    ) -> bool:
        """Delete a variant."""
        
        variant = await self.session.get(KnowledgeVariant, variant_id)
        if not variant:
            return False
        
        # Update parent item's graph version
        item = await self.session.get(KnowledgeItem, variant.knowledge_item_id)
        if item:
            item.graph_version += 1
        
        await self.session.delete(variant)
        await self.session.commit()
        
        return True
    
    async def get_variant(self, variant_id: int) -> Optional[KnowledgeVariant]:
        """Get a single variant by ID."""
        return await self.session.get(KnowledgeVariant, variant_id)
