"""High-level knowledge retriever for sub-agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from agentcore.knowledge.client import KnowledgeClient
from agentcore.knowledge.models import KnowledgeBundle, KnowledgeNode, KnowledgeType

if TYPE_CHECKING:
    from agentcore.auth.context import RequestContext


class KnowledgeRetriever:
    """High-level retriever for sub-agents.
    
    Provides specialized retrieval methods optimized for different
    sub-agent use cases (planning, research, analysis).
    """

    def __init__(self, client: KnowledgeClient):
        self._client = client

    async def retrieve_for_planning(
        self,
        ctx: "RequestContext",
        query: str,
        tenant: Optional[str] = None,
    ) -> KnowledgeBundle:
        """Retrieve knowledge for the Planner sub-agent.
        
        Focuses on playbooks and high-level concepts that help
        with task decomposition and planning.
        
        Args:
            ctx: Request context
            query: User query or task description
            tenant: Optional tenant filter
            
        Returns:
            KnowledgeBundle with planning-relevant knowledge
        """
        # Get playbooks and concepts
        bundle = await self._client.get_bundle(ctx, query, limit=15, tenant=tenant)
        
        # If no playbooks found, try searching specifically for playbooks
        if not bundle.playbooks:
            results = await self._client.search(
                ctx,
                query=f"how to {query}",
                types=[KnowledgeType.PLAYBOOK, KnowledgeType.CONCEPT],
                limit=5,
                tenant=tenant,
            )
            if results.results:
                # Merge into bundle
                new_playbooks = [r.node for r in results.results if r.node.type == KnowledgeType.PLAYBOOK]
                new_concepts = [r.node for r in results.results if r.node.type == KnowledgeType.CONCEPT]
                bundle = bundle.model_copy(update={
                    "playbooks": bundle.playbooks + new_playbooks,
                    "concepts": bundle.concepts + new_concepts,
                })
        
        return bundle

    async def retrieve_for_research(
        self,
        ctx: "RequestContext",
        query: str,
        tenant: Optional[str] = None,
    ) -> KnowledgeBundle:
        """Retrieve knowledge for the Researcher sub-agent.
        
        Focuses on schemas, FAQs, and entity definitions that help
        with information gathering.
        
        Args:
            ctx: Request context
            query: Research query
            tenant: Optional tenant filter
            
        Returns:
            KnowledgeBundle with research-relevant knowledge
        """
        bundle = await self._client.get_bundle(ctx, query, limit=20, tenant=tenant)
        return bundle

    async def retrieve_for_analysis(
        self,
        ctx: "RequestContext",
        query: str,
        entity_names: Optional[list[str]] = None,
        tenant: Optional[str] = None,
    ) -> KnowledgeBundle:
        """Retrieve knowledge for the Analyzer sub-agent.
        
        Focuses on schemas and entity definitions needed for
        data analysis and comparison.
        
        Args:
            ctx: Request context
            query: Analysis query
            entity_names: Specific entities to get schemas for
            tenant: Optional tenant filter
            
        Returns:
            KnowledgeBundle with analysis-relevant knowledge
        """
        bundle = await self._client.get_bundle(ctx, query, limit=15, tenant=tenant)
        
        # Also fetch specific schemas if entity names provided
        if entity_names:
            for entity_name in entity_names:
                schema = await self._client.get_schema(ctx, entity_name)
                if schema and schema not in bundle.schemas:
                    bundle = bundle.model_copy(update={
                        "schemas": bundle.schemas + [schema],
                    })
        
        return bundle

    async def retrieve_schema(
        self,
        ctx: "RequestContext",
        entity_name: str,
    ) -> Optional[KnowledgeNode]:
        """Get schema definition for a specific entity.
        
        Args:
            ctx: Request context
            entity_name: Entity name (e.g., "PurchaseOrder")
            
        Returns:
            Schema KnowledgeNode or None
        """
        return await self._client.get_schema(ctx, entity_name)

    async def retrieve_related(
        self,
        ctx: "RequestContext",
        node_id: str,
        limit: int = 10,
    ) -> list[KnowledgeNode]:
        """Get knowledge related to a specific node.
        
        Uses graph edges to find connected information.
        
        Args:
            ctx: Request context
            node_id: Source node ID
            limit: Max related nodes
            
        Returns:
            List of related KnowledgeNodes
        """
        return await self._client.get_related(ctx, node_id, limit=limit)

    async def get_context_for_llm(
        self,
        ctx: "RequestContext",
        query: str,
        max_chars: int = 8000,
        tenant: Optional[str] = None,
    ) -> str:
        """Get formatted knowledge context for LLM prompts.
        
        Convenience method that retrieves and formats knowledge
        in a single call.
        
        Args:
            ctx: Request context
            query: User query
            max_chars: Maximum characters for context
            tenant: Optional tenant filter
            
        Returns:
            Formatted text suitable for LLM prompt
        """
        bundle = await self._client.get_bundle(ctx, query, limit=15, tenant=tenant)
        return bundle.to_prompt_context(max_chars=max_chars)
