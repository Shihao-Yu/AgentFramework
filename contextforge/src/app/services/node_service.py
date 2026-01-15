"""
Knowledge Verse node CRUD service.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, text

from app.models.nodes import KnowledgeNode
from app.models.enums import NodeType, KnowledgeStatus, Visibility
from app.schemas.nodes import (
    NodeCreate,
    NodeUpdate,
    NodeListParams,
    NodeResponse,
    NodeSearchResult,
)
from app.schemas.common import PaginatedResponse
from app.clients.embedding_client import EmbeddingClient
from app.utils.schema import sql

import logging

logger = logging.getLogger(__name__)


class EmbeddingClientRequiredError(RuntimeError):
    pass


class NodeService:
    def __init__(self, session: AsyncSession, embedding_client: Optional[EmbeddingClient] = None):
        self.session = session
        self.embedding_client = embedding_client
    
    def _require_embedding_client(self) -> EmbeddingClient:
        if self.embedding_client is None:
            raise EmbeddingClientRequiredError(
                "Embedding client required for this operation. "
                "Set OPENAI_API_KEY or install sentence-transformers."
            )
        return self.embedding_client
    
    async def list_nodes(
        self,
        params: NodeListParams,
        user_tenant_ids: List[str],
    ) -> PaginatedResponse[NodeResponse]:
        query = select(KnowledgeNode).where(
            KnowledgeNode.is_deleted == False,
            KnowledgeNode.tenant_id.in_(user_tenant_ids),
        )
        count_query = select(func.count(KnowledgeNode.id)).where(
            KnowledgeNode.is_deleted == False,
            KnowledgeNode.tenant_id.in_(user_tenant_ids),
        )
        
        if params.tenant_ids:
            allowed_tenants = [t for t in params.tenant_ids if t in user_tenant_ids]
            if allowed_tenants:
                query = query.where(KnowledgeNode.tenant_id.in_(allowed_tenants))
                count_query = count_query.where(KnowledgeNode.tenant_id.in_(allowed_tenants))
        
        if params.node_types:
            query = query.where(KnowledgeNode.node_type.in_(params.node_types))
            count_query = count_query.where(KnowledgeNode.node_type.in_(params.node_types))
        
        if params.status:
            query = query.where(KnowledgeNode.status == params.status)
            count_query = count_query.where(KnowledgeNode.status == params.status)
        
        if params.visibility:
            query = query.where(KnowledgeNode.visibility == params.visibility)
            count_query = count_query.where(KnowledgeNode.visibility == params.visibility)
        
        if params.tags:
            query = query.where(KnowledgeNode.tags.overlap(params.tags))
            count_query = count_query.where(KnowledgeNode.tags.overlap(params.tags))
        
        if params.dataset_name:
            query = query.where(KnowledgeNode.dataset_name == params.dataset_name)
            count_query = count_query.where(KnowledgeNode.dataset_name == params.dataset_name)
        
        if params.search:
            search_filter = or_(
                KnowledgeNode.title.ilike(f"%{params.search}%"),
                KnowledgeNode.summary.ilike(f"%{params.search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        query = query.order_by(KnowledgeNode.created_at.desc())
        offset = (params.page - 1) * params.limit
        query = query.offset(offset).limit(params.limit)
        
        result = await self.session.execute(query)
        nodes = result.scalars().all()
        
        response_items = [NodeResponse.model_validate(node) for node in nodes]
        
        return PaginatedResponse(
            data=response_items,
            total=total,
            page=params.page,
            limit=params.limit,
            total_pages=(total + params.limit - 1) // params.limit if total > 0 else 0
        )
    
    async def get_node(
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
    
    async def create_node(
        self,
        data: NodeCreate,
        user_tenant_ids: List[str],
        created_by: Optional[str] = None,
        sync_tag_edges: bool = True,
    ) -> Optional[KnowledgeNode]:
        if data.tenant_id not in user_tenant_ids:
            return None
        
        client = self._require_embedding_client()
        embed_text = self._build_embed_text(data.title, data.content, data.node_type)
        embedding = await client.embed(embed_text)
        
        node = KnowledgeNode(
            tenant_id=data.tenant_id,
            node_type=data.node_type,
            title=data.title,
            summary=data.summary,
            content=data.content,
            tags=data.tags,
            dataset_name=data.dataset_name,
            field_path=data.field_path,
            data_type=data.data_type,
            visibility=data.visibility,
            status=data.status,
            source=data.source,
            source_reference=data.source_reference,
            metadata_=data.metadata_,
            created_by=created_by,
        )
        
        self.session.add(node)
        await self.session.flush()
        
        # Convert to PostgreSQL vector format
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        
        await self.session.execute(
            text(sql("""
                UPDATE {schema}.knowledge_nodes 
                SET embedding = :embedding::vector 
                WHERE id = :id
            """)),
            {"id": node.id, "embedding": embedding_str}
        )
        
        # Sync SHARED_TAG edges if node has tags and is published
        if sync_tag_edges and data.tags and data.status == KnowledgeStatus.PUBLISHED:
            await self._sync_shared_tag_edges(
                node_id=node.id,
                node_tags=data.tags,
                tenant_id=data.tenant_id,
            )
        
        await self.session.commit()
        await self.session.refresh(node)
        
        return node
    
    async def update_node(
        self,
        node_id: int,
        data: NodeUpdate,
        user_tenant_ids: List[str],
        updated_by: Optional[str] = None,
        sync_tag_edges: bool = True,
    ) -> Optional[KnowledgeNode]:
        node = await self.get_node(node_id, user_tenant_ids)
        if not node:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        content_changed = False
        tags_changed = False
        status_changed = False
        old_tags = list(node.tags) if node.tags else []
        old_status = node.status
        
        for field, value in update_data.items():
            if field == "tags" and value != old_tags:
                tags_changed = True
            if field == "status" and value != old_status:
                status_changed = True
            setattr(node, field, value)
            if field in ("title", "content", "summary"):
                content_changed = True
        
        node.updated_by = updated_by
        node.updated_at = datetime.utcnow()
        node.version += 1
        node.graph_version += 1
        
        await self.session.flush()
        
        if content_changed:
            client = self._require_embedding_client()
            embed_text = self._build_embed_text(node.title, node.content, node.node_type)
            embedding = await client.embed(embed_text)
            
            # Convert to PostgreSQL vector format
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            
            await self.session.execute(
                text(sql("""
                    UPDATE {schema}.knowledge_nodes 
                    SET embedding = :embedding::vector 
                    WHERE id = :id
                """)),
                {"id": node.id, "embedding": embedding_str}
            )
        
        # Sync SHARED_TAG edges if tags or status changed
        if sync_tag_edges and (tags_changed or status_changed):
            if node.status == KnowledgeStatus.PUBLISHED and node.tags:
                # Node is published with tags - sync edges
                await self._sync_shared_tag_edges(
                    node_id=node.id,
                    node_tags=node.tags,
                    tenant_id=node.tenant_id,
                )
            else:
                # Node unpublished or tags cleared - remove edges
                await self._delete_shared_tag_edges(node_id=node.id)
        
        await self.session.commit()
        await self.session.refresh(node)
        
        return node
    
    async def delete_node(
        self,
        node_id: int,
        user_tenant_ids: List[str],
        deleted_by: Optional[str] = None,
    ) -> bool:
        node = await self.get_node(node_id, user_tenant_ids)
        if not node:
            return False
        
        node.is_deleted = True
        node.updated_by = deleted_by
        node.updated_at = datetime.utcnow()
        
        await self.session.commit()
        return True
    
    async def hybrid_search(
        self,
        query_text: str,
        user_tenant_ids: List[str],
        node_types: Optional[List[NodeType]] = None,
        tags: Optional[List[str]] = None,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
        limit: int = 20,
    ) -> List[NodeSearchResult]:
        if not query_text or not query_text.strip():
            return []
        
        client = self._require_embedding_client()
        query_embedding = await client.embed(query_text)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        
        result = await self.session.execute(
            text(sql("""
                SELECT * FROM {schema}.hybrid_search_nodes(
                    :query_text,
                    :query_embedding,
                    :tenant_ids,
                    :node_types,
                    :tag_filter,
                    :bm25_weight,
                    :vector_weight,
                    :result_limit
                )
            """)),
            {
                "query_text": query_text,
                "query_embedding": embedding_str,
                "tenant_ids": user_tenant_ids,
                "node_types": [nt.value for nt in node_types] if node_types else None,
                "tag_filter": tags,
                "bm25_weight": bm25_weight,
                "vector_weight": vector_weight,
                "result_limit": limit,
            }
        )
        
        rows = result.fetchall()
        results = []
        
        for row in rows:
            node_response = NodeResponse(
                id=row.id,
                tenant_id=row.tenant_id,
                node_type=NodeType(row.node_type),
                title=row.title,
                summary=row.summary,
                content=row.content,
                tags=row.tags or [],
                dataset_name=row.dataset_name,
                field_path=row.field_path,
                visibility=Visibility.INTERNAL,
                status=KnowledgeStatus.PUBLISHED,
                source="",
                version=1,
                created_at=datetime.utcnow(),
            )
            
            match_source = getattr(row, 'match_source', None)
            results.append(NodeSearchResult(
                node=node_response,
                bm25_rank=row.bm25_rank,
                vector_rank=row.vector_rank,
                bm25_score=row.bm25_score,
                vector_score=row.vector_score,
                rrf_score=row.rrf_score,
                match_source=match_source,
            ))
        
        return results
    
    async def get_nodes_by_ids(
        self,
        node_ids: List[int],
        user_tenant_ids: List[str],
    ) -> List[KnowledgeNode]:
        if not node_ids:
            return []
        
        query = select(KnowledgeNode).where(
            KnowledgeNode.id.in_(node_ids),
            KnowledgeNode.is_deleted == False,
            KnowledgeNode.tenant_id.in_(user_tenant_ids),
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def reembed_nodes(
        self,
        user_tenant_ids: List[str],
        node_types: Optional[List[NodeType]] = None,
        batch_size: int = 50,
        only_missing: bool = False,
    ) -> Dict[str, Any]:
        """
        Regenerate embeddings for nodes.
        
        Useful for:
        - Initializing embeddings for seed data
        - Updating embeddings after model change
        - Fixing nodes with missing embeddings
        
        Args:
            user_tenant_ids: Tenant IDs to process
            node_types: Optional filter for specific node types
            batch_size: Number of nodes to process per batch
            only_missing: If True, only embed nodes without embeddings
        
        Returns:
            Stats dict with processed, updated, errors counts
        """
        client = self._require_embedding_client()
        
        stats = {
            "processed": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "batches": 0,
        }
        
        # Build query for nodes to process
        query = select(KnowledgeNode).where(
            KnowledgeNode.is_deleted == False,
            KnowledgeNode.tenant_id.in_(user_tenant_ids),
        )
        
        if node_types:
            query = query.where(KnowledgeNode.node_type.in_(node_types))
        
        if only_missing:
            # Only nodes without embeddings
            query = query.where(
                text("embedding IS NULL")
            )
        
        query = query.order_by(KnowledgeNode.id)
        
        # Process in batches
        offset = 0
        while True:
            batch_query = query.offset(offset).limit(batch_size)
            result = await self.session.execute(batch_query)
            nodes = result.scalars().all()
            
            if not nodes:
                break
            
            stats["batches"] += 1
            
            for node in nodes:
                stats["processed"] += 1
                
                try:
                    # Build embedding text
                    embed_text = self._build_embed_text(
                        node.title,
                        node.content or {},
                        node.node_type,
                    )
                    
                    if not embed_text.strip():
                        stats["skipped"] += 1
                        continue
                    
                    # Generate embedding
                    embedding = await client.embed(embed_text)
                    # Convert to PostgreSQL vector format
                    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
                    
                    # Update node
                    await self.session.execute(
                        text(sql("""
                            UPDATE {schema}.knowledge_nodes 
                            SET embedding = :embedding::vector,
                                updated_at = NOW()
                            WHERE id = :id
                        """)),
                        {"id": node.id, "embedding": embedding_str}
                    )
                    
                    stats["updated"] += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to embed node {node.id}: {e}")
                    stats["errors"] += 1
            
            # Commit each batch
            await self.session.commit()
            
            offset += batch_size
            logger.info(
                f"Reembed progress: {stats['processed']} processed, "
                f"{stats['updated']} updated, {stats['errors']} errors"
            )
        
        return stats
    
    async def get_node_versions(
        self,
        node_id: int,
        user_tenant_ids: List[str],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        node = await self.get_node(node_id, user_tenant_ids)
        if not node:
            return []
        
        result = await self.session.execute(
            text(sql("""
                SELECT id, node_id, version_number, title, content, tags, 
                       change_type, changed_by, changed_at
                FROM {schema}.node_versions
                WHERE node_id = :node_id
                ORDER BY version_number DESC
                LIMIT :limit
            """)),
            {"node_id": node_id, "limit": limit}
        )
        
        return [dict(row._mapping) for row in result.fetchall()]
    
    def _build_embed_text(
        self,
        title: str,
        content: Dict[str, Any],
        node_type: NodeType,
    ) -> str:
        parts = [title]
        
        if node_type == NodeType.FAQ:
            if "answer" in content:
                parts.append(content["answer"])
        
        elif node_type == NodeType.PLAYBOOK:
            if "description" in content:
                parts.append(content["description"])
            if "steps" in content:
                for step in content["steps"]:
                    if isinstance(step, dict) and "action" in step:
                        parts.append(step["action"])
        
        elif node_type == NodeType.PERMISSION_RULE:
            if "feature" in content:
                parts.append(content["feature"])
            if "description" in content:
                parts.append(content["description"])
        
        elif node_type == NodeType.ENTITY:
            if "entity_name" in content:
                parts.append(content["entity_name"])
            if "description" in content:
                parts.append(content["description"])
            if "business_purpose" in content:
                parts.append(content["business_purpose"])
        
        elif node_type == NodeType.SCHEMA_INDEX:
            if "table_name" in content:
                parts.append(content["table_name"])
            if "description" in content:
                parts.append(content["description"])
        
        elif node_type == NodeType.SCHEMA_FIELD:
            if "description" in content:
                parts.append(content["description"])
            if "business_meaning" in content:
                parts.append(content["business_meaning"])
        
        elif node_type == NodeType.EXAMPLE:
            if "question" in content:
                parts.append(content["question"])
            if "explanation" in content:
                parts.append(content["explanation"])
        
        elif node_type == NodeType.CONCEPT:
            if "description" in content:
                parts.append(content["description"])
            if "aliases" in content and content["aliases"]:
                parts.extend(content["aliases"])
        
        else:
            for key in ["description", "body", "content", "summary", "text"]:
                if key in content and content[key]:
                    parts.append(str(content[key]))
        
        return "\n".join(parts)
    
    # =========================================================================
    # Shared Tag Edge Sync Helpers
    # =========================================================================
    
    async def _sync_shared_tag_edges(
        self,
        node_id: int,
        node_tags: List[str],
        tenant_id: str,
        min_shared_tags: int = 2,
    ) -> int:
        """
        Sync SHARED_TAG edges for a node using inline SQL.
        
        This is a lightweight version that doesn't require GraphSyncService,
        suitable for use within NodeService transactions.
        """
        if not node_tags or len(node_tags) < min_shared_tags:
            return 0
        
        try:
            # Delete existing SHARED_TAG edges for this node
            await self.session.execute(
                text(sql("""
                    DELETE FROM {schema}.knowledge_edges
                    WHERE edge_type = 'shared_tag'
                      AND is_auto_generated = TRUE
                      AND (source_id = :node_id OR target_id = :node_id)
                """)),
                {"node_id": node_id}
            )
            
            # Create edges with nodes that have overlapping tags
            result = await self.session.execute(
                text(sql("""
                    WITH overlapping_nodes AS (
                        SELECT 
                            n.id as other_id,
                            array_length(
                                ARRAY(SELECT unnest(:node_tags::text[]) INTERSECT SELECT unnest(n.tags)),
                                1
                            ) as shared_count
                        FROM {schema}.knowledge_nodes n
                        WHERE n.id != :node_id
                          AND n.tenant_id = :tenant_id
                          AND n.is_deleted = FALSE
                          AND n.status = 'published'
                          AND n.tags && :node_tags::text[]
                    )
                    INSERT INTO {schema}.knowledge_edges (source_id, target_id, edge_type, weight, is_auto_generated, created_by)
                    SELECT 
                        LEAST(:node_id, other_id),
                        GREATEST(:node_id, other_id),
                        'shared_tag',
                        LEAST(shared_count::float / 5.0, 1.0),
                        TRUE,
                        'system'
                    FROM overlapping_nodes
                    WHERE shared_count >= :min_shared_tags
                    ON CONFLICT (source_id, target_id, edge_type) DO UPDATE
                    SET weight = EXCLUDED.weight,
                        updated_at = NOW()
                    RETURNING id
                """)),
                {
                    "node_id": node_id,
                    "node_tags": node_tags,
                    "tenant_id": tenant_id,
                    "min_shared_tags": min_shared_tags,
                }
            )
            
            created = len(result.fetchall())
            logger.debug(f"Synced {created} SHARED_TAG edges for node {node_id}")
            return created
            
        except Exception as e:
            logger.warning(f"Failed to sync SHARED_TAG edges for node {node_id}: {e}")
            return 0
    
    async def _delete_shared_tag_edges(self, node_id: int) -> int:
        """Delete all SHARED_TAG edges for a node."""
        try:
            result = await self.session.execute(
                text(sql("""
                    DELETE FROM {schema}.knowledge_edges
                    WHERE edge_type = 'shared_tag'
                      AND is_auto_generated = TRUE
                      AND (source_id = :node_id OR target_id = :node_id)
                    RETURNING id
                """)),
                {"node_id": node_id}
            )
            
            deleted = len(result.fetchall())
            logger.debug(f"Deleted {deleted} SHARED_TAG edges for node {node_id}")
            return deleted
            
        except Exception as e:
            logger.warning(f"Failed to delete SHARED_TAG edges for node {node_id}: {e}")
            return 0
