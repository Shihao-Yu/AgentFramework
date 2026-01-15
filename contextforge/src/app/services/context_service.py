"""
Agent context service for structured context retrieval.

Provides the primary API for AI agents to retrieve relevant knowledge
from the Knowledge Verse graph.
"""

import json
from typing import List, Optional, Dict, Any, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.enums import NodeType, EdgeType
from app.schemas.context import (
    ContextRequest,
    ContextResponse,
    EntryPointResult,
    ContextNodeResult,
    EntityResult,
    ContextStats,
)
from app.services.node_service import NodeService
from app.services.graph_service import GraphService
from app.clients.embedding_client import EmbeddingClient
from app.utils.tokens import TokenCounter
from app.utils.schema import sql as schema_sql


class ContextService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_client: EmbeddingClient,
    ):
        self.session = session
        self.embedding_client = embedding_client
        self.node_service = NodeService(session, embedding_client)
        self.graph_service = GraphService(session)
        self.token_counter = TokenCounter()
    
    async def get_context(
        self,
        request: ContextRequest,
    ) -> ContextResponse:
        entry_points = await self._find_entry_points(request)
        
        context_nodes: List[ContextNodeResult] = []
        entities: List[EntityResult] = []
        max_depth_reached = 0
        nodes_expanded = 0
        
        if request.expand and entry_points:
            context_nodes, max_depth_reached, nodes_expanded = await self._expand_context(
                entry_points=entry_points,
                request=request,
            )
        
        if request.include_entities:
            entities = await self._collect_entities(
                entry_points=entry_points,
                context_nodes=context_nodes,
                tenant_ids=request.tenant_ids,
            )
        
        # Apply token budget if specified
        tokens_used: Optional[Dict[str, int]] = None
        total_tokens: Optional[int] = None
        
        if request.max_tokens:
            entry_points, context_nodes, entities, tokens_used = self._apply_token_budget(
                entry_points=entry_points,
                context_nodes=context_nodes,
                entities=entities,
                max_tokens=request.max_tokens,
                model=request.token_model,
            )
            total_tokens = sum(tokens_used.values())
        
        stats = ContextStats(
            nodes_searched=len(entry_points) * 10,
            nodes_expanded=nodes_expanded,
            max_depth_reached=max_depth_reached,
            entry_points_found=len(entry_points),
            context_nodes_found=len(context_nodes),
            total_tokens=total_tokens,
            tokens_used=tokens_used,
        )
        
        return ContextResponse(
            entry_points=entry_points,
            context=context_nodes,
            entities=entities,
            stats=stats,
        )
    
    def _apply_token_budget(
        self,
        entry_points: List[EntryPointResult],
        context_nodes: List[ContextNodeResult],
        entities: List[EntityResult],
        max_tokens: int,
        model: str = "gpt-4",
    ) -> Tuple[List[EntryPointResult], List[ContextNodeResult], List[EntityResult], Dict[str, int]]:
        """
        Apply token budget to context results.
        
        Budget allocation:
        - Entry points: 60% of budget
        - Context nodes: 30% of budget
        - Entities: 10% of budget
        
        Returns filtered lists and token counts by category.
        """
        entry_budget = int(max_tokens * 0.60)
        context_budget = int(max_tokens * 0.30)
        entity_budget = int(max_tokens * 0.10)
        
        tokens_used = {
            "entry_points": 0,
            "context_nodes": 0,
            "entities": 0,
        }
        
        # Filter entry points
        filtered_entry_points: List[EntryPointResult] = []
        for ep in entry_points:
            text = self._node_to_text(ep.title, ep.summary, ep.content)
            tokens = self.token_counter.count(text, model)
            
            if tokens_used["entry_points"] + tokens <= entry_budget:
                filtered_entry_points.append(ep)
                tokens_used["entry_points"] += tokens
            else:
                break
        
        # Filter context nodes
        filtered_context_nodes: List[ContextNodeResult] = []
        for cn in context_nodes:
            text = self._node_to_text(cn.title, cn.summary, cn.content)
            tokens = self.token_counter.count(text, model)
            
            if tokens_used["context_nodes"] + tokens <= context_budget:
                filtered_context_nodes.append(cn)
                tokens_used["context_nodes"] += tokens
            else:
                break
        
        # Filter entities
        filtered_entities: List[EntityResult] = []
        for entity in entities:
            text = f"{entity.title} {entity.entity_path} {' '.join(entity.related_schemas)}"
            tokens = self.token_counter.count(text, model)
            
            if tokens_used["entities"] + tokens <= entity_budget:
                filtered_entities.append(entity)
                tokens_used["entities"] += tokens
            else:
                break
        
        return filtered_entry_points, filtered_context_nodes, filtered_entities, tokens_used
    
    def _node_to_text(self, title: str, summary: Optional[str], content: Dict[str, Any]) -> str:
        """Convert node data to text for token counting."""
        parts = [title]
        if summary:
            parts.append(summary)
        if content:
            # Serialize content to string
            parts.append(json.dumps(content))
        return "\n".join(parts)
    
    async def _find_entry_points(
        self,
        request: ContextRequest,
    ) -> List[EntryPointResult]:
        node_types = request.entry_types
        if node_types is None:
            node_types = [
                NodeType.FAQ,
                NodeType.PLAYBOOK,
                NodeType.PERMISSION_RULE,
                NodeType.CONCEPT,
            ]
            if request.include_schemas:
                node_types.extend([NodeType.SCHEMA_INDEX, NodeType.SCHEMA_FIELD])
            if request.include_examples:
                node_types.append(NodeType.EXAMPLE)
        
        bm25_weight, vector_weight = self._resolve_search_weights(request)
        
        search_results = await self.node_service.hybrid_search(
            query_text=request.query,
            user_tenant_ids=request.tenant_ids,
            node_types=node_types,
            tags=request.tags,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
            limit=request.entry_limit,
        )
        
        entry_points = []
        for result in search_results:
            if request.min_score is not None and result.rrf_score < request.min_score:
                continue
            
            match_source = "hybrid"
            if result.bm25_score and result.bm25_score > 0 and (not result.vector_score or result.vector_score == 0):
                match_source = "bm25"
            elif result.vector_score and result.vector_score > 0 and (not result.bm25_score or result.bm25_score == 0):
                match_source = "vector"
            
            entry_points.append(EntryPointResult(
                id=result.node.id,
                node_type=result.node.node_type,
                title=result.node.title,
                summary=result.node.summary,
                content=result.node.content,
                tags=result.node.tags,
                score=result.rrf_score,
                match_source=match_source,
            ))
        
        return entry_points
    
    def _resolve_search_weights(self, request: ContextRequest) -> Tuple[float, float]:
        if request.search_method == "bm25":
            return 1.0, 0.0
        elif request.search_method == "vector":
            return 0.0, 1.0
        return request.bm25_weight, request.vector_weight
    
    async def _expand_context(
        self,
        entry_points: List[EntryPointResult],
        request: ContextRequest,
    ) -> Tuple[List[ContextNodeResult], int, int]:
        await self.graph_service.load_graph(request.tenant_ids)
        
        entry_ids = {ep.id for ep in entry_points}
        visited: Set[int] = set(entry_ids)
        context_nodes: List[ContextNodeResult] = []
        max_depth_reached = 0
        nodes_expanded = 0
        
        paths: Dict[int, List[int]] = {ep.id: [ep.id] for ep in entry_points}
        edge_types_used: Dict[int, Optional[EdgeType]] = {ep.id: None for ep in entry_points}
        
        expansion_types = request.expansion_types
        if expansion_types is None:
            expansion_types = list(NodeType)
            if not request.include_schemas:
                expansion_types = [t for t in expansion_types if t not in (NodeType.SCHEMA_INDEX, NodeType.SCHEMA_FIELD)]
            if not request.include_examples:
                expansion_types = [t for t in expansion_types if t != NodeType.EXAMPLE]
        
        expansion_type_values = [t.value for t in expansion_types]
        
        current_level = set(entry_ids)
        
        for depth in range(1, request.max_depth + 1):
            if len(context_nodes) >= request.context_limit:
                break
            
            next_level: Set[int] = set()
            
            for node_id in current_level:
                if node_id not in self.graph_service.graph:
                    continue
                
                nodes_expanded += 1
                
                successors = set(self.graph_service.graph.successors(node_id))
                predecessors = set(self.graph_service.graph.predecessors(node_id))
                neighbors = (successors | predecessors) - visited
                
                for neighbor_id in neighbors:
                    if len(context_nodes) >= request.context_limit:
                        break
                    
                    node_data = self.graph_service.graph.nodes.get(neighbor_id, {})
                    neighbor_type = node_data.get("node_type")
                    
                    if neighbor_type not in expansion_type_values:
                        continue
                    
                    edge_data = self.graph_service.graph.get_edge_data(node_id, neighbor_id)
                    if not edge_data:
                        edge_data = self.graph_service.graph.get_edge_data(neighbor_id, node_id)
                    
                    edge_type = None
                    if edge_data:
                        try:
                            edge_type = EdgeType(edge_data.get("edge_type"))
                        except ValueError:
                            pass
                    
                    path = paths[node_id] + [neighbor_id]
                    
                    node_detail = await self._get_node_detail(neighbor_id, request.tenant_ids)
                    if node_detail:
                        base_score = 1.0 / (depth + 1)
                        edge_weight = edge_data.get("weight", 1.0) if edge_data else 1.0
                        score = base_score * edge_weight
                        
                        context_nodes.append(ContextNodeResult(
                            id=neighbor_id,
                            node_type=NodeType(node_detail["node_type"]),
                            title=node_detail["title"],
                            summary=node_detail.get("summary"),
                            content=node_detail["content"],
                            tags=node_detail.get("tags", []),
                            score=score,
                            distance=depth,
                            path=path,
                            edge_type=edge_type,
                        ))
                        
                        paths[neighbor_id] = path
                        edge_types_used[neighbor_id] = edge_type
                        visited.add(neighbor_id)
                        next_level.add(neighbor_id)
                        max_depth_reached = max(max_depth_reached, depth)
            
            current_level = next_level
            if not current_level:
                break
        
        context_nodes.sort(key=lambda x: (-x.score, x.distance))
        
        return context_nodes[:request.context_limit], max_depth_reached, nodes_expanded
    
    async def _get_node_detail(
        self,
        node_id: int,
        tenant_ids: List[str],
    ) -> Optional[Dict[str, Any]]:
        result = await self.session.execute(
            text(schema_sql("""
                SELECT id, tenant_id, node_type, title, summary, content, tags
                FROM {schema}.knowledge_nodes
                WHERE id = :node_id 
                  AND tenant_id = ANY(:tenant_ids)
                  AND is_deleted = FALSE
                  AND status = 'published'
            """)),
            {"node_id": node_id, "tenant_ids": tenant_ids}
        )
        row = result.fetchone()
        if not row:
            return None
        
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "node_type": row.node_type,
            "title": row.title,
            "summary": row.summary,
            "content": row.content,
            "tags": row.tags or [],
        }
    
    async def _collect_entities(
        self,
        entry_points: List[EntryPointResult],
        context_nodes: List[ContextNodeResult],
        tenant_ids: List[str],
    ) -> List[EntityResult]:
        all_node_ids = [ep.id for ep in entry_points] + [cn.id for cn in context_nodes]
        
        result = await self.session.execute(
            text(schema_sql("""
                SELECT DISTINCT n.id, n.title, n.content
                FROM {schema}.knowledge_nodes n
                WHERE n.node_type = 'entity'
                  AND n.tenant_id = ANY(:tenant_ids)
                  AND n.is_deleted = FALSE
                  AND n.status = 'published'
                  AND (
                    n.id = ANY(:node_ids)
                    OR EXISTS (
                      SELECT 1 FROM {schema}.knowledge_edges e
                      WHERE (e.source_id = n.id AND e.target_id = ANY(:node_ids))
                         OR (e.target_id = n.id AND e.source_id = ANY(:node_ids))
                    )
                  )
                LIMIT 10
            """)),
            {"node_ids": all_node_ids, "tenant_ids": tenant_ids}
        )
        
        entities = []
        for row in result.fetchall():
            content = row.content or {}
            entity_path = content.get("entity_path", "")
            
            related_schemas = await self._get_related_schemas(row.id, tenant_ids)
            
            entities.append(EntityResult(
                id=row.id,
                title=row.title,
                entity_path=entity_path,
                related_schemas=related_schemas,
            ))
        
        return entities
    
    async def _get_related_schemas(
        self,
        entity_id: int,
        tenant_ids: List[str],
    ) -> List[str]:
        result = await self.session.execute(
            text(schema_sql("""
                SELECT DISTINCT n.dataset_name
                FROM {schema}.knowledge_nodes n
                JOIN {schema}.knowledge_edges e ON 
                    (e.source_id = :entity_id AND e.target_id = n.id)
                    OR (e.target_id = :entity_id AND e.source_id = n.id)
                WHERE n.node_type IN ('schema_index', 'schema_field')
                  AND n.dataset_name IS NOT NULL
                  AND n.tenant_id = ANY(:tenant_ids)
                  AND n.is_deleted = FALSE
                LIMIT 10
            """)),
            {"entity_id": entity_id, "tenant_ids": tenant_ids}
        )
        
        return [row.dataset_name for row in result.fetchall()]
