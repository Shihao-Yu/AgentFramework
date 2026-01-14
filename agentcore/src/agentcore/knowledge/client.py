"""Knowledge client for ContextForge integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

import httpx

from agentcore.knowledge.models import (
    KnowledgeBundle,
    KnowledgeNode,
    KnowledgeType,
    SearchResult,
    SearchResults,
)
from agentcore.settings.knowledge import KnowledgeSettings
from agentcore.tracing.decorators import trace_knowledge

if TYPE_CHECKING:
    from agentcore.auth.context import RequestContext

logger = logging.getLogger(__name__)


class KnowledgeClient:
    """Client for ContextForge knowledge retrieval.
    
    Provides methods to search, retrieve, and bundle knowledge
    from the ContextForge backend.
    """

    def __init__(self, settings: Optional[KnowledgeSettings] = None):
        self._settings = settings or KnowledgeSettings()
        self._client = httpx.AsyncClient(
            base_url=self._settings.base_url,
            timeout=self._settings.timeout_seconds,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "KnowledgeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @trace_knowledge
    async def search(
        self,
        ctx: "RequestContext",
        query: str,
        types: Optional[list[KnowledgeType]] = None,
        limit: Optional[int] = None,
        tenant: Optional[str] = None,
    ) -> SearchResults:
        """Search for knowledge nodes.
        
        Args:
            ctx: Request context with user info
            query: Search query
            types: Optional filter by knowledge types
            limit: Max results to return
            tenant: Optional tenant/domain filter
            
        Returns:
            SearchResults with matching nodes
        """
        limit = min(limit or self._settings.default_limit, self._settings.max_limit)
        
        # Build search params
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
        }
        
        if types:
            params["types"] = [t.value for t in types]
        
        if tenant:
            params["tenant"] = tenant
        
        if self._settings.hybrid_search_enabled:
            params["hybrid"] = True
            params["bm25_weight"] = self._settings.bm25_weight
            params["vector_weight"] = self._settings.vector_weight
        
        try:
            response = await self._client.get(
                "/api/v1/knowledge/search",
                params=params,
                headers=self._get_headers(ctx),
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse response
            results = []
            for item in data.get("results", []):
                node = self._parse_node(item)
                score = item.get("score", 0.0)
                results.append(SearchResult(node=node, score=score))
            
            return SearchResults(
                results=results,
                total_count=data.get("total_count", len(results)),
                query=query,
            )
        except httpx.HTTPError as e:
            logger.error(f"Knowledge search failed: {e}")
            return SearchResults(query=query)

    @trace_knowledge
    async def get_bundle(
        self,
        ctx: "RequestContext",
        query: str,
        limit: int = 20,
        tenant: Optional[str] = None,
    ) -> KnowledgeBundle:
        """Get a bundle of knowledge for a query.
        
        Retrieves and organizes knowledge by type for easy use in agent prompts.
        
        Args:
            ctx: Request context
            query: Search query
            limit: Max total results
            tenant: Optional tenant filter
            
        Returns:
            KnowledgeBundle organized by knowledge type
        """
        results = await self.search(ctx, query, limit=limit, tenant=tenant)
        return KnowledgeBundle.from_search_results(query, results)

    @trace_knowledge
    async def get_node(
        self,
        ctx: "RequestContext",
        node_id: str,
    ) -> Optional[KnowledgeNode]:
        """Get a specific knowledge node by ID.
        
        Args:
            ctx: Request context
            node_id: Node identifier
            
        Returns:
            KnowledgeNode or None if not found
        """
        try:
            response = await self._client.get(
                f"/api/v1/knowledge/{node_id}",
                headers=self._get_headers(ctx),
            )
            response.raise_for_status()
            return self._parse_node(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Failed to get node {node_id}: {e}")
            return None
        except httpx.HTTPError as e:
            logger.error(f"Failed to get node {node_id}: {e}")
            return None

    @trace_knowledge
    async def get_related(
        self,
        ctx: "RequestContext",
        node_id: str,
        limit: int = 10,
    ) -> list[KnowledgeNode]:
        """Get nodes related to a given node.
        
        Uses graph edges to find connected knowledge.
        
        Args:
            ctx: Request context
            node_id: Source node ID
            limit: Max related nodes to return
            
        Returns:
            List of related KnowledgeNodes
        """
        try:
            response = await self._client.get(
                f"/api/v1/knowledge/{node_id}/related",
                params={"limit": limit},
                headers=self._get_headers(ctx),
            )
            response.raise_for_status()
            data = response.json()
            
            return [self._parse_node(item) for item in data.get("related", [])]
        except httpx.HTTPError as e:
            logger.error(f"Failed to get related nodes for {node_id}: {e}")
            return []

    @trace_knowledge
    async def get_schema(
        self,
        ctx: "RequestContext",
        entity_name: str,
    ) -> Optional[KnowledgeNode]:
        """Get schema definition for an entity.
        
        Args:
            ctx: Request context
            entity_name: Name of the entity (e.g., "PurchaseOrder")
            
        Returns:
            Schema KnowledgeNode or None
        """
        results = await self.search(
            ctx,
            query=entity_name,
            types=[KnowledgeType.SCHEMA],
            limit=5,
        )
        
        # Find best match
        entity_lower = entity_name.lower()
        for result in results.results:
            if entity_lower in result.node.title.lower():
                return result.node
        
        # Return top result if any
        return results.results[0].node if results.results else None

    def _get_headers(self, ctx: "RequestContext") -> dict[str, str]:
        """Get headers for API requests."""
        headers = {
            "X-Request-ID": ctx.request_id,
            "X-Session-ID": ctx.session_id,
        }
        if ctx.user.token:
            headers["Authorization"] = f"Bearer {ctx.user.token}"
        return headers

    def _parse_node(self, data: dict[str, Any]) -> KnowledgeNode:
        """Parse API response to KnowledgeNode."""
        # Map ContextForge fields to KnowledgeNode
        node_type = KnowledgeType(data.get("type", "concept"))
        
        return KnowledgeNode(
            id=str(data.get("id", "")),
            type=node_type,
            title=data.get("title", data.get("name", "")),
            content=data.get("content", data.get("description", "")),
            summary=data.get("summary"),
            metadata=data.get("metadata", {}),
            score=data.get("score"),
            edges=[str(e) for e in data.get("edges", data.get("related_ids", []))],
            tenant=data.get("tenant", data.get("domain")),
        )


class MockKnowledgeClient(KnowledgeClient):
    """Mock knowledge client for testing.
    
    Returns predefined knowledge nodes without calling ContextForge.
    """

    def __init__(self, nodes: Optional[list[KnowledgeNode]] = None):
        self._settings = KnowledgeSettings()
        self._nodes = nodes or []
        self._node_map: dict[str, KnowledgeNode] = {n.id: n for n in self._nodes}

    async def close(self) -> None:
        pass

    def add_node(self, node: KnowledgeNode) -> None:
        """Add a node to the mock data."""
        self._nodes.append(node)
        self._node_map[node.id] = node

    def add_nodes(self, nodes: list[KnowledgeNode]) -> None:
        """Add multiple nodes to the mock data."""
        for node in nodes:
            self.add_node(node)

    async def search(
        self,
        ctx: "RequestContext",
        query: str,
        types: Optional[list[KnowledgeType]] = None,
        limit: Optional[int] = None,
        tenant: Optional[str] = None,
    ) -> SearchResults:
        """Mock search - simple keyword matching."""
        limit = limit or self._settings.default_limit
        query_lower = query.lower()
        
        results = []
        for node in self._nodes:
            # Filter by type
            if types and node.type not in types:
                continue
            
            # Filter by tenant
            if tenant and node.tenant != tenant:
                continue
            
            # Simple keyword matching
            score = 0.0
            if query_lower in node.title.lower():
                score += 0.5
            if query_lower in node.content.lower():
                score += 0.3
            if node.summary and query_lower in node.summary.lower():
                score += 0.2
            
            if score > 0:
                results.append(SearchResult(node=node, score=min(score, 1.0)))
        
        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        results = results[:limit]
        
        return SearchResults(
            results=results,
            total_count=len(results),
            query=query,
        )

    async def get_bundle(
        self,
        ctx: "RequestContext",
        query: str,
        limit: int = 20,
        tenant: Optional[str] = None,
    ) -> KnowledgeBundle:
        """Mock bundle retrieval."""
        results = await self.search(ctx, query, limit=limit, tenant=tenant)
        return KnowledgeBundle.from_search_results(query, results)

    async def get_node(
        self,
        ctx: "RequestContext",
        node_id: str,
    ) -> Optional[KnowledgeNode]:
        """Mock node retrieval."""
        return self._node_map.get(node_id)

    async def get_related(
        self,
        ctx: "RequestContext",
        node_id: str,
        limit: int = 10,
    ) -> list[KnowledgeNode]:
        """Mock related nodes retrieval."""
        node = self._node_map.get(node_id)
        if not node:
            return []
        
        related = []
        for edge_id in node.edges[:limit]:
            if edge_id in self._node_map:
                related.append(self._node_map[edge_id])
        
        return related

    async def get_schema(
        self,
        ctx: "RequestContext",
        entity_name: str,
    ) -> Optional[KnowledgeNode]:
        """Mock schema retrieval."""
        entity_lower = entity_name.lower()
        for node in self._nodes:
            if node.type == KnowledgeType.SCHEMA and entity_lower in node.title.lower():
                return node
        return None

    def clear(self) -> None:
        """Clear all mock data."""
        self._nodes.clear()
        self._node_map.clear()
