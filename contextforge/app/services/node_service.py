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


class NodeService:
    def __init__(self, session: AsyncSession, embedding_client: EmbeddingClient):
        self.session = session
        self.embedding_client = embedding_client
    
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
    ) -> Optional[KnowledgeNode]:
        if data.tenant_id not in user_tenant_ids:
            return None
        
        embed_text = self._build_embed_text(data.title, data.content, data.node_type)
        embedding = await self.embedding_client.embed(embed_text)
        
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
            created_by=created_by,
        )
        
        self.session.add(node)
        await self.session.flush()
        
        await self.session.execute(
            text("""
                UPDATE agent.knowledge_nodes 
                SET embedding = :embedding::vector 
                WHERE id = :id
            """),
            {"id": node.id, "embedding": embedding}
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
    ) -> Optional[KnowledgeNode]:
        node = await self.get_node(node_id, user_tenant_ids)
        if not node:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        content_changed = False
        
        for field, value in update_data.items():
            setattr(node, field, value)
            if field in ("title", "content", "summary"):
                content_changed = True
        
        node.updated_by = updated_by
        node.updated_at = datetime.utcnow()
        node.version += 1
        node.graph_version += 1
        
        await self.session.flush()
        
        if content_changed:
            embed_text = self._build_embed_text(node.title, node.content, node.node_type)
            embedding = await self.embedding_client.embed(embed_text)
            
            await self.session.execute(
                text("""
                    UPDATE agent.knowledge_nodes 
                    SET embedding = :embedding::vector 
                    WHERE id = :id
                """),
                {"id": node.id, "embedding": embedding}
            )
        
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
        query_embedding = await self.embedding_client.embed(query_text)
        
        result = await self.session.execute(
            text("""
                SELECT * FROM agent.hybrid_search_nodes(
                    :query_text,
                    :query_embedding::vector,
                    :tenant_ids,
                    :node_types,
                    :tag_filter,
                    :bm25_weight,
                    :vector_weight,
                    :result_limit
                )
            """),
            {
                "query_text": query_text,
                "query_embedding": query_embedding,
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
            
            results.append(NodeSearchResult(
                node=node_response,
                bm25_rank=row.bm25_rank,
                vector_rank=row.vector_rank,
                bm25_score=row.bm25_score,
                vector_score=row.vector_score,
                rrf_score=row.rrf_score,
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
            text("""
                SELECT id, node_id, version_number, title, content, tags, 
                       change_type, changed_by, changed_at
                FROM agent.node_versions
                WHERE node_id = :node_id
                ORDER BY version_number DESC
                LIMIT :limit
            """),
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
            if "question" in content:
                parts.append(content["question"])
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
