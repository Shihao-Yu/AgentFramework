from datetime import datetime
from typing import List, Optional, Dict, Any, Set
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.utils.schema import sql as schema_sql
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    from networkx.readwrite import json_graph
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    json_graph = None


class GraphService:
    def __init__(self, session: AsyncSession, redis_client=None):
        self.session = session
        self.redis_client = redis_client
        self._graph: Optional["nx.DiGraph"] = None
        self._last_sync: Optional[datetime] = None
        self._graph_version: int = 0
    
    @property
    def graph(self) -> "nx.DiGraph":
        if not HAS_NETWORKX:
            raise ImportError("networkx is required for graph operations")
        if self._graph is None:
            self._graph = nx.DiGraph()
        return self._graph
    
    def _cache_key(self, tenant_ids: List[str]) -> str:
        sorted_ids = sorted(tenant_ids)
        return f"{settings.GRAPH_CACHE_KEY_PREFIX}:{':'.join(sorted_ids)}"
    
    async def _get_cached_graph(self, tenant_ids: List[str]) -> Optional["nx.DiGraph"]:
        if not self.redis_client or not self.redis_client.is_connected:
            return None
        
        if not HAS_NETWORKX or json_graph is None:
            return None
        
        try:
            key = self._cache_key(tenant_ids)
            data = await self.redis_client.get(key)
            if data:
                # Use JSON serialization instead of pickle for security
                graph_data = json.loads(data.decode("utf-8"))
                graph = json_graph.node_link_graph(graph_data, directed=True)
                logger.debug(f"Graph cache hit for tenants {tenant_ids}")
                return graph
        except Exception as e:
            logger.warning(f"Failed to load graph from cache: {e}")
        return None
    
    async def _set_cached_graph(self, tenant_ids: List[str], graph: "nx.DiGraph"):
        if not self.redis_client or not self.redis_client.is_connected:
            return
        
        if not HAS_NETWORKX or json_graph is None:
            return
        
        try:
            key = self._cache_key(tenant_ids)
            # Use JSON serialization instead of pickle for security
            graph_data = json_graph.node_link_data(graph)
            data = json.dumps(graph_data).encode("utf-8")
            await self.redis_client.set(key, data, ttl=settings.GRAPH_CACHE_TTL)
            logger.debug(f"Graph cached for tenants {tenant_ids}")
        except Exception as e:
            logger.warning(f"Failed to cache graph: {e}")
    
    async def invalidate_cache(self, tenant_ids: Optional[List[str]] = None):
        if not self.redis_client or not self.redis_client.is_connected:
            return
        
        try:
            if tenant_ids:
                key = self._cache_key(tenant_ids)
                await self.redis_client.delete(key)
                logger.info(f"Invalidated graph cache for tenants {tenant_ids}")
            else:
                pattern = f"{settings.GRAPH_CACHE_KEY_PREFIX}:*"
                deleted = await self.redis_client.delete_pattern(pattern)
                logger.info(f"Invalidated {deleted} graph cache entries")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
    
    async def load_graph(
        self,
        tenant_ids: List[str],
        force_reload: bool = False,
    ) -> "nx.DiGraph":
        if not HAS_NETWORKX:
            raise ImportError("networkx is required for graph operations")
        
        if self._graph is not None and not force_reload:
            return self._graph
        
        if not force_reload:
            cached = await self._get_cached_graph(tenant_ids)
            if cached:
                self._graph = cached
                self._last_sync = datetime.utcnow()
                return self._graph
        
        self._graph = nx.DiGraph()
        
        nodes_result = await self.session.execute(
            text(schema_sql("""
                SELECT id, tenant_id, node_type, title, tags, dataset_name, 
                       field_path, status, graph_version
                FROM {schema}.knowledge_nodes
                WHERE tenant_id = ANY(:tenant_ids) 
                  AND is_deleted = FALSE 
                  AND status = 'published'
            """)),
            {"tenant_ids": tenant_ids}
        )
        
        for row in nodes_result.fetchall():
            self._graph.add_node(
                row.id,
                tenant_id=row.tenant_id,
                node_type=row.node_type,
                title=row.title,
                tags=row.tags or [],
                dataset_name=row.dataset_name,
                field_path=row.field_path,
            )
        
        node_ids = list(self._graph.nodes())
        if not node_ids:
            return self._graph
        
        edges_result = await self.session.execute(
            text(schema_sql("""
                SELECT id, source_id, target_id, edge_type, weight, is_auto_generated
                FROM {schema}.knowledge_edges
                WHERE source_id = ANY(:node_ids) AND target_id = ANY(:node_ids)
            """)),
            {"node_ids": node_ids}
        )
        
        for row in edges_result.fetchall():
            self._graph.add_edge(
                row.source_id,
                row.target_id,
                edge_id=row.id,
                edge_type=row.edge_type,
                weight=row.weight,
                is_auto_generated=row.is_auto_generated,
            )
        
        self._last_sync = datetime.utcnow()
        
        await self._set_cached_graph(tenant_ids, self._graph)
        
        return self._graph
    
    async def get_neighbors(
        self,
        node_id: int,
        tenant_ids: List[str],
        depth: int = 1,
        edge_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        await self.load_graph(tenant_ids)
        
        if node_id not in self.graph:
            return []
        
        visited: Set[int] = {node_id}
        current_level = {node_id}
        all_neighbors = []
        
        for d in range(depth):
            next_level: Set[int] = set()
            
            for nid in current_level:
                successors = set(self.graph.successors(nid))
                predecessors = set(self.graph.predecessors(nid))
                neighbors = (successors | predecessors) - visited
                
                if edge_types:
                    filtered = set()
                    for neighbor in neighbors:
                        edge_data = self.graph.get_edge_data(nid, neighbor)
                        if edge_data and edge_data.get("edge_type") in edge_types:
                            filtered.add(neighbor)
                        edge_data = self.graph.get_edge_data(neighbor, nid)
                        if edge_data and edge_data.get("edge_type") in edge_types:
                            filtered.add(neighbor)
                    neighbors = filtered
                
                for neighbor in neighbors:
                    node_data = self.graph.nodes[neighbor]
                    all_neighbors.append({
                        "id": neighbor,
                        "depth": d + 1,
                        **node_data,
                    })
                
                next_level |= neighbors
                visited |= neighbors
            
            current_level = next_level
            if not current_level:
                break
        
        return all_neighbors
    
    async def find_paths(
        self,
        source_id: int,
        target_id: int,
        tenant_ids: List[str],
        max_depth: int = 5,
    ) -> List[List[int]]:
        await self.load_graph(tenant_ids)
        
        if source_id not in self.graph or target_id not in self.graph:
            return []
        
        undirected = self.graph.to_undirected()
        
        try:
            paths = list(nx.all_simple_paths(
                undirected, source_id, target_id, cutoff=max_depth
            ))
            return paths[:10]
        except nx.NetworkXNoPath:
            return []
    
    async def get_connected_component(
        self,
        node_id: int,
        tenant_ids: List[str],
    ) -> List[int]:
        await self.load_graph(tenant_ids)
        
        if node_id not in self.graph:
            return []
        
        undirected = self.graph.to_undirected()
        
        for component in nx.connected_components(undirected):
            if node_id in component:
                return list(component)
        
        return [node_id]
    
    async def get_graph_stats(
        self,
        tenant_ids: List[str],
    ) -> Dict[str, Any]:
        await self.load_graph(tenant_ids)
        
        node_count = self.graph.number_of_nodes()
        edge_count = self.graph.number_of_edges()
        
        if node_count == 0:
            return {
                "node_count": 0,
                "edge_count": 0,
                "density": 0,
                "connected_components": 0,
                "avg_degree": 0,
                "orphan_nodes": 0,
                "node_types": {},
                "edge_types": {},
                "cache_enabled": self.redis_client is not None and self.redis_client.is_connected,
            }
        
        undirected = self.graph.to_undirected()
        connected_components = nx.number_connected_components(undirected)
        
        degrees = [d for _, d in self.graph.degree()]
        avg_degree = sum(degrees) / len(degrees) if degrees else 0
        orphan_nodes = sum(1 for d in degrees if d == 0)
        
        node_types: Dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            nt = data.get("node_type", "unknown")
            node_types[nt] = node_types.get(nt, 0) + 1
        
        edge_types: Dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            et = data.get("edge_type", "unknown")
            edge_types[et] = edge_types.get(et, 0) + 1
        
        density = nx.density(self.graph)
        
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "density": density,
            "connected_components": connected_components,
            "avg_degree": round(avg_degree, 2),
            "orphan_nodes": orphan_nodes,
            "node_types": node_types,
            "edge_types": edge_types,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "cache_enabled": self.redis_client is not None and self.redis_client.is_connected,
        }
    
    async def find_orphan_nodes(
        self,
        tenant_ids: List[str],
    ) -> List[Dict[str, Any]]:
        await self.load_graph(tenant_ids)
        
        orphans = []
        for node_id, data in self.graph.nodes(data=True):
            if self.graph.degree(node_id) == 0:
                orphans.append({
                    "id": node_id,
                    **data,
                })
        
        return orphans
    
    async def suggest_connections(
        self,
        node_id: int,
        tenant_ids: List[str],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        await self.load_graph(tenant_ids)
        
        if node_id not in self.graph:
            return []
        
        node_data = self.graph.nodes[node_id]
        node_tags = set(node_data.get("tags", []))
        node_type = node_data.get("node_type")
        
        existing_neighbors = set(self.graph.successors(node_id)) | set(self.graph.predecessors(node_id))
        existing_neighbors.add(node_id)
        
        suggestions = []
        
        for other_id, other_data in self.graph.nodes(data=True):
            if other_id in existing_neighbors:
                continue
            
            score = 0.0
            
            other_tags = set(other_data.get("tags", []))
            common_tags = node_tags & other_tags
            if common_tags:
                score += len(common_tags) * 0.5
            
            if node_type in ("schema_index", "schema_field", "entity", "example"):
                if other_data.get("dataset_name") == node_data.get("dataset_name"):
                    score += 1.0
            
            if score > 0:
                suggestions.append({
                    "id": other_id,
                    "score": score,
                    "reason": f"shared_tags:{len(common_tags)}" if common_tags else "same_dataset",
                    **other_data,
                })
        
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        return suggestions[:limit]
    
    def clear_cache(self):
        self._graph = None
        self._last_sync = None
        self._graph_version = 0
