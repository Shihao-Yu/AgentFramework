"""
Node variant management service.
"""

from datetime import datetime
from typing import List, Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.nodes import KnowledgeNode, NodeVariant
from app.models.enums import VariantSource
from app.clients.embedding_client import EmbeddingClient
from app.utils.schema import sql


class VariantCreate:
    def __init__(
        self,
        variant_text: str,
        source: VariantSource = VariantSource.MANUAL,
        source_reference: Optional[str] = None,
    ):
        self.variant_text = variant_text
        self.source = source
        self.source_reference = source_reference


class VariantResponse:
    def __init__(
        self,
        id: int,
        node_id: int,
        variant_text: str,
        source: VariantSource,
        source_reference: Optional[str],
        created_by: Optional[str],
        created_at: datetime,
    ):
        self.id = id
        self.node_id = node_id
        self.variant_text = variant_text
        self.source = source
        self.source_reference = source_reference
        self.created_by = created_by
        self.created_at = created_at

    @classmethod
    def from_model(cls, variant: NodeVariant) -> "VariantResponse":
        return cls(
            id=variant.id,
            node_id=variant.node_id,
            variant_text=variant.variant_text,
            source=variant.source,
            source_reference=variant.source_reference,
            created_by=variant.created_by,
            created_at=variant.created_at,
        )


class VariantService:
    def __init__(self, session: AsyncSession, embedding_client: EmbeddingClient):
        self.session = session
        self.embedding_client = embedding_client

    async def list_variants(
        self,
        node_id: int,
        user_tenant_ids: List[str],
    ) -> List[VariantResponse]:
        node = await self._get_node(node_id, user_tenant_ids)
        if not node:
            return []

        query = select(NodeVariant).where(
            NodeVariant.node_id == node_id
        ).order_by(NodeVariant.created_at.desc())

        result = await self.session.execute(query)
        variants = result.scalars().all()

        return [VariantResponse.from_model(v) for v in variants]

    async def create_variant(
        self,
        node_id: int,
        data: VariantCreate,
        user_tenant_ids: List[str],
        created_by: Optional[str] = None,
    ) -> Optional[VariantResponse]:
        node = await self._get_node(node_id, user_tenant_ids)
        if not node:
            return None

        existing_query = select(NodeVariant).where(
            NodeVariant.node_id == node_id,
            NodeVariant.variant_text == data.variant_text,
        )
        existing = await self.session.execute(existing_query)
        if existing.scalar_one_or_none():
            raise ValueError("Variant with this text already exists")

        embedding = await self.embedding_client.embed(data.variant_text)
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        variant = NodeVariant(
            node_id=node_id,
            variant_text=data.variant_text,
            source=data.source,
            source_reference=data.source_reference,
            created_by=created_by,
        )

        self.session.add(variant)
        await self.session.flush()

        await self.session.execute(
            text(sql("""
                UPDATE {schema}.node_variants 
                SET embedding = :embedding::vector 
                WHERE id = :id
            """)),
            {"id": variant.id, "embedding": embedding_str}
        )

        node.graph_version += 1

        await self.session.commit()
        await self.session.refresh(variant)

        return VariantResponse.from_model(variant)

    async def delete_variant(
        self,
        variant_id: int,
        user_tenant_ids: List[str],
    ) -> bool:
        variant = await self.session.get(NodeVariant, variant_id)
        if not variant:
            return False

        node = await self._get_node(variant.node_id, user_tenant_ids)
        if not node:
            return False

        node.graph_version += 1

        await self.session.delete(variant)
        await self.session.commit()

        return True

    async def get_variant(
        self,
        variant_id: int,
        user_tenant_ids: List[str],
    ) -> Optional[VariantResponse]:
        variant = await self.session.get(NodeVariant, variant_id)
        if not variant:
            return None

        node = await self._get_node(variant.node_id, user_tenant_ids)
        if not node:
            return None

        return VariantResponse.from_model(variant)

    async def _get_node(
        self,
        node_id: int,
        user_tenant_ids: List[str],
    ) -> Optional[KnowledgeNode]:
        query = select(KnowledgeNode).where(
            KnowledgeNode.id == node_id,
            KnowledgeNode.is_deleted == False,
            KnowledgeNode.tenant_id.in_(user_tenant_ids),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
