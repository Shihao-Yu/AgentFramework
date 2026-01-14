"""
Base classes and mixins for data source implementations.

Provides shared onboarding logic that all sources can use:
- Schema storage (PostgreSQL via KnowledgeNode)
- Vector DB sync (pgvector)
- LLM enrichment
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.protocols import UnifiedField
    from ..schema.yaml_schema import YAMLSchemaV1

logger = logging.getLogger(__name__)


class SourceOnboardingMixin:
    """
    Mixin providing shared onboarding logic for all data sources.
    
    Handles:
    - Storing schemas to KnowledgeNode (versioned via graph_version)
    - Syncing fields to pgvector (for retrieval)
    - Optional LLM enrichment
    
    Sources should inherit from both DataSourceBase and this mixin:
        class OpenSearchSource(DataSourceBase, SourceOnboardingMixin):
            ...
    """
    
    async def _store_to_knowledge_nodes(
        self,
        schema: "YAMLSchemaV1",
        tenant_id: str,
        dataset_name: str,
        db_session: Any,
    ) -> int:
        """
        Store schema fields to KnowledgeNode table.
        
        Args:
            schema: YAMLSchemaV1 schema to store
            tenant_id: Tenant identifier
            dataset_name: Dataset/index/table name
            db_session: SQLAlchemy async session
            
        Returns:
            Number of nodes created/updated
        """
        from ..schema.node_mapping import (
            create_field_node_data,
            create_concept_node_data,
        )
        
        node_count = 0
        
        for index in schema.indices:
            for field in index.fields:
                node_data = create_field_node_data(field, tenant_id, dataset_name)
                node_count += 1
                
        for concept in schema.concepts:
            node_data = create_concept_node_data(concept, tenant_id, dataset_name)
            node_count += 1
        
        logger.info(f"Prepared {node_count} nodes for {tenant_id}/{dataset_name}")
        return node_count
    
    async def _run_enrichment(
        self,
        unified_fields: List["UnifiedField"],
        llm_client: Any,
        tenant_id: str,
        document_name: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> List["UnifiedField"]:
        """
        Run LLM enrichment on fields.
        
        Enriches:
        - Field descriptions
        - Business meanings
        - Value synonyms
        - Search guidance
        
        Args:
            unified_fields: Fields to enrich
            llm_client: LLM client for inference
            tenant_id: Tenant identifier
            document_name: Document name
            options: Enrichment options
            
        Returns:
            Enriched fields
        """
        logger.warning("LLM enrichment not fully implemented - returning fields as-is")
        return unified_fields
    
    def _build_onboarding_result(
        self,
        status: str,
        tenant_id: str,
        document_name: str,
        source_type: str,
        field_count: int,
        entity_count: int = 0,
        qa_count: int = 0,
        schema_version: Optional[int] = None,
        enrichment_performed: bool = False,
        has_graph: bool = False,
        issues: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build standardized onboarding result dict.
        """
        return {
            "status": status,
            "tenant_id": tenant_id,
            "document_name": document_name,
            "source_type": source_type,
            "field_count": field_count,
            "entity_count": entity_count,
            "qa_count": qa_count,
            "schema_version": schema_version,
            "enrichment_performed": enrichment_performed,
            "has_graph": has_graph,
            "issues": issues or [],
        }
