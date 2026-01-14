"""
Knowledge Verse edge CRUD service.
"""

from datetime import datetime
from typing import List, Optional, Tuple
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from app.models.edges import KnowledgeEdge
from app.models.nodes import KnowledgeNode
from app.models.enums import EdgeType
from app.schemas.edges import (
    EdgeCreate,
    EdgeUpdate,
    EdgeListParams,
    EdgeResponse,
)
from app.utils.schema import sql as schema_sql


class EdgeService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def list_edges(
        self,
        params: EdgeListParams,
        user_tenant_ids: List[str],
    ) -> Tuple[List[EdgeResponse], int]:
        base_query = schema_sql("""
            SELECT e.id, e.source_id, e.target_id, e.edge_type, e.weight,
                   e.is_auto_generated, e.metadata_, e.created_by, e.created_at,
                   sn.title as source_title, tn.title as target_title,
                   sn.node_type as source_node_type, tn.node_type as target_node_type
            FROM {schema}.knowledge_edges e
            JOIN {schema}.knowledge_nodes sn ON e.source_id = sn.id AND sn.is_deleted = FALSE
            JOIN {schema}.knowledge_nodes tn ON e.target_id = tn.id AND tn.is_deleted = FALSE
            WHERE (sn.tenant_id = ANY(:tenant_ids) OR tn.tenant_id = ANY(:tenant_ids))
        """)
        
        count_query = schema_sql("""
            SELECT COUNT(*)
            FROM {schema}.knowledge_edges e
            JOIN {schema}.knowledge_nodes sn ON e.source_id = sn.id AND sn.is_deleted = FALSE
            JOIN {schema}.knowledge_nodes tn ON e.target_id = tn.id AND tn.is_deleted = FALSE
            WHERE (sn.tenant_id = ANY(:tenant_ids) OR tn.tenant_id = ANY(:tenant_ids))
        """)
        
        filters = []
        bind_params = {"tenant_ids": user_tenant_ids}
        
        if params.node_id:
            if params.direction == "incoming":
                filters.append("e.target_id = :node_id")
            elif params.direction == "outgoing":
                filters.append("e.source_id = :node_id")
            else:
                filters.append("(e.source_id = :node_id OR e.target_id = :node_id)")
            bind_params["node_id"] = params.node_id
        
        if params.edge_types:
            filters.append("e.edge_type = ANY(:edge_types)")
            bind_params["edge_types"] = [et.value for et in params.edge_types]
        
        if not params.include_auto_generated:
            filters.append("e.is_auto_generated = FALSE")
        
        if filters:
            filter_clause = " AND " + " AND ".join(filters)
            base_query += filter_clause
            count_query += filter_clause
        
        count_result = await self.session.execute(text(count_query), bind_params)
        total = count_result.scalar() or 0
        
        offset = (params.page - 1) * params.limit
        base_query += f" ORDER BY e.created_at DESC LIMIT :limit OFFSET :offset"
        bind_params["limit"] = params.limit
        bind_params["offset"] = offset
        
        result = await self.session.execute(text(base_query), bind_params)
        rows = result.fetchall()
        
        edges = []
        for row in rows:
            edges.append(EdgeResponse(
                id=row.id,
                source_id=row.source_id,
                target_id=row.target_id,
                edge_type=EdgeType(row.edge_type),
                weight=row.weight,
                is_auto_generated=row.is_auto_generated,
                metadata_=row.metadata_ or {},
                created_by=row.created_by,
                created_at=row.created_at,
                source_title=row.source_title,
                target_title=row.target_title,
                source_node_type=row.source_node_type,
                target_node_type=row.target_node_type,
            ))
        
        return edges, total
    
    async def get_edge(
        self,
        edge_id: int,
        user_tenant_ids: List[str],
    ) -> Optional[EdgeResponse]:
        result = await self.session.execute(
            text(schema_sql("""
                SELECT e.id, e.source_id, e.target_id, e.edge_type, e.weight,
                       e.is_auto_generated, e.metadata_, e.created_by, e.created_at,
                       sn.title as source_title, tn.title as target_title,
                       sn.node_type as source_node_type, tn.node_type as target_node_type
                FROM {schema}.knowledge_edges e
                JOIN {schema}.knowledge_nodes sn ON e.source_id = sn.id AND sn.is_deleted = FALSE
                JOIN {schema}.knowledge_nodes tn ON e.target_id = tn.id AND tn.is_deleted = FALSE
                WHERE e.id = :edge_id
                  AND (sn.tenant_id = ANY(:tenant_ids) OR tn.tenant_id = ANY(:tenant_ids))
            """)),
            {"edge_id": edge_id, "tenant_ids": user_tenant_ids}
        )
        
        row = result.fetchone()
        if not row:
            return None
        
        return EdgeResponse(
            id=row.id,
            source_id=row.source_id,
            target_id=row.target_id,
            edge_type=EdgeType(row.edge_type),
            weight=row.weight,
            is_auto_generated=row.is_auto_generated,
            metadata_=row.metadata_ or {},
            created_by=row.created_by,
            created_at=row.created_at,
            source_title=row.source_title,
            target_title=row.target_title,
            source_node_type=row.source_node_type,
            target_node_type=row.target_node_type,
        )
    
    async def create_edge(
        self,
        data: EdgeCreate,
        user_tenant_ids: List[str],
        created_by: Optional[str] = None,
    ) -> Optional[KnowledgeEdge]:
        nodes_result = await self.session.execute(
            text(schema_sql("""
                SELECT id, tenant_id FROM {schema}.knowledge_nodes 
                WHERE id IN (:source_id, :target_id) AND is_deleted = FALSE
            """)),
            {"source_id": data.source_id, "target_id": data.target_id}
        )
        nodes = {row.id: row.tenant_id for row in nodes_result.fetchall()}
        
        if data.source_id not in nodes or data.target_id not in nodes:
            return None
        
        source_tenant = nodes[data.source_id]
        target_tenant = nodes[data.target_id]
        if source_tenant not in user_tenant_ids and target_tenant not in user_tenant_ids:
            return None
        
        existing = await self.session.execute(
            text(schema_sql("""
                SELECT id FROM {schema}.knowledge_edges
                WHERE source_id = :source_id 
                  AND target_id = :target_id 
                  AND edge_type = :edge_type
            """)),
            {
                "source_id": data.source_id,
                "target_id": data.target_id,
                "edge_type": data.edge_type.value,
            }
        )
        if existing.fetchone():
            raise ValueError("Edge already exists")
        
        edge = KnowledgeEdge(
            source_id=data.source_id,
            target_id=data.target_id,
            edge_type=data.edge_type,
            weight=data.weight,
            is_auto_generated=False,
            metadata_=data.metadata_,
            created_by=created_by,
        )
        
        self.session.add(edge)
        try:
            await self.session.commit()
            await self.session.refresh(edge)
        except IntegrityError:
            await self.session.rollback()
            raise ValueError("Edge already exists")
        
        return edge
    
    async def create_edges_bulk(
        self,
        edges: List[EdgeCreate],
        user_tenant_ids: List[str],
        created_by: Optional[str] = None,
    ) -> List[KnowledgeEdge]:
        all_node_ids = set()
        for e in edges:
            all_node_ids.add(e.source_id)
            all_node_ids.add(e.target_id)
        
        nodes_result = await self.session.execute(
            text(schema_sql("""
                SELECT id, tenant_id FROM {schema}.knowledge_nodes 
                WHERE id = ANY(:node_ids) AND is_deleted = FALSE
            """)),
            {"node_ids": list(all_node_ids)}
        )
        node_tenants = {row.id: row.tenant_id for row in nodes_result.fetchall()}
        
        created_edges = []
        for data in edges:
            if data.source_id not in node_tenants or data.target_id not in node_tenants:
                continue
            
            source_tenant = node_tenants[data.source_id]
            target_tenant = node_tenants[data.target_id]
            if source_tenant not in user_tenant_ids and target_tenant not in user_tenant_ids:
                continue
            
            edge = KnowledgeEdge(
                source_id=data.source_id,
                target_id=data.target_id,
                edge_type=data.edge_type,
                weight=data.weight,
                is_auto_generated=False,
                metadata_=data.metadata_,
                created_by=created_by,
            )
            self.session.add(edge)
            created_edges.append(edge)
        
        if created_edges:
            await self.session.commit()
            for edge in created_edges:
                await self.session.refresh(edge)
        
        return created_edges
    
    async def update_edge(
        self,
        edge_id: int,
        data: EdgeUpdate,
        user_tenant_ids: List[str],
    ) -> Optional[KnowledgeEdge]:
        query = select(KnowledgeEdge).where(KnowledgeEdge.id == edge_id)
        result = await self.session.execute(query)
        edge = result.scalar_one_or_none()
        
        if not edge:
            return None
        
        nodes_result = await self.session.execute(
            text(schema_sql("""
                SELECT id, tenant_id FROM {schema}.knowledge_nodes 
                WHERE id IN (:source_id, :target_id) AND is_deleted = FALSE
            """)),
            {"source_id": edge.source_id, "target_id": edge.target_id}
        )
        nodes = {row.id: row.tenant_id for row in nodes_result.fetchall()}
        
        source_tenant = nodes.get(edge.source_id)
        target_tenant = nodes.get(edge.target_id)
        if source_tenant not in user_tenant_ids and target_tenant not in user_tenant_ids:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(edge, field, value)
        
        await self.session.commit()
        await self.session.refresh(edge)
        
        return edge
    
    async def delete_edge(
        self,
        edge_id: int,
        user_tenant_ids: List[str],
    ) -> bool:
        query = select(KnowledgeEdge).where(KnowledgeEdge.id == edge_id)
        result = await self.session.execute(query)
        edge = result.scalar_one_or_none()
        
        if not edge:
            return False
        
        nodes_result = await self.session.execute(
            text(schema_sql("""
                SELECT id, tenant_id FROM {schema}.knowledge_nodes 
                WHERE id IN (:source_id, :target_id) AND is_deleted = FALSE
            """)),
            {"source_id": edge.source_id, "target_id": edge.target_id}
        )
        nodes = {row.id: row.tenant_id for row in nodes_result.fetchall()}
        
        source_tenant = nodes.get(edge.source_id)
        target_tenant = nodes.get(edge.target_id)
        if source_tenant not in user_tenant_ids and target_tenant not in user_tenant_ids:
            return False
        
        await self.session.delete(edge)
        await self.session.commit()
        
        return True
    
    async def get_node_edges(
        self,
        node_id: int,
        user_tenant_ids: List[str],
        direction: str = "both",
    ) -> Tuple[List[EdgeResponse], List[EdgeResponse]]:
        incoming = []
        outgoing = []
        
        if direction in ("both", "incoming"):
            params = EdgeListParams(node_id=node_id, direction="incoming", limit=100)
            incoming, _ = await self.list_edges(params, user_tenant_ids)
        
        if direction in ("both", "outgoing"):
            params = EdgeListParams(node_id=node_id, direction="outgoing", limit=100)
            outgoing, _ = await self.list_edges(params, user_tenant_ids)
        
        return incoming, outgoing
