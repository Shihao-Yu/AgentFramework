"""
OpenSearch Data Source Implementation.

Implements the DataSource protocol for OpenSearch/Elasticsearch,
providing schema parsing, graph-based retrieval, and DSL query generation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from ...core.protocols import (
    DataSourceBase,
    RetrievalContext,
    SourceType,
    UnifiedField,
    register_source,
)
from ..base import SourceOnboardingMixin

if TYPE_CHECKING:
    from ...schema.yaml_schema import YAMLSchemaV1

logger = logging.getLogger(__name__)


@register_source(SourceType.OPENSEARCH)
class OpenSearchSource(DataSourceBase, SourceOnboardingMixin):
    """
    OpenSearch/Elasticsearch data source.
    
    Supports:
    - JSON mapping parsing via MappingConverter
    - YAML schema with concepts, indices, fields
    - Graph-based retrieval
    - OpenSearch DSL query generation
    """
    
    source_type = SourceType.OPENSEARCH
    
    def __init__(self, **config):
        self.config = config
    
    def parse_schema(
        self, 
        raw_schema: Union[str, Dict[str, Any]], 
        **kwargs
    ) -> Any:
        """
        Parse OpenSearch mapping into YAMLSchemaV1.
        
        Args:
            raw_schema: JSON mapping (dict or JSON string)
            **kwargs:
                - tenant_id: Tenant identifier (required)
                - document_name: Document/index name
                - index_pattern: Index pattern (e.g., "orders-*")
                - infer_concepts: Auto-infer concepts from field patterns
        
        Returns:
            YAMLSchemaV1 schema model
        """
        from .parser import MappingConverter
        import json
        
        mapping_dict: Dict[str, Any]
        if isinstance(raw_schema, str):
            mapping_dict = json.loads(raw_schema)
        elif isinstance(raw_schema, dict):
            mapping_dict = raw_schema
        else:
            raise ValueError(f"raw_schema must be a dict or JSON string, got {type(raw_schema)}")
        
        tenant_id = kwargs.get("tenant_id", "default")
        document_name = kwargs.get("document_name")
        index_pattern: str = kwargs.get("index_pattern") or document_name or "default-*"
        infer_concepts = kwargs.get("infer_concepts", True)
        
        converter = MappingConverter(mapping_dict)
        schema = converter.to_yaml_schema(
            index_pattern=index_pattern,
            tenant_id=tenant_id,
            infer_concepts=infer_concepts,
        )
        
        return schema
    
    def to_unified_fields(self, schema: Any) -> List[UnifiedField]:
        """
        Convert YAMLSchemaV1 fields to UnifiedField format.
        """
        unified_fields = []
        
        for index in schema.indices:
            for field_spec in index.fields:
                unified_fields.append(UnifiedField(
                    path=field_spec.path,
                    field_type=field_spec.es_type,
                    source_type=self.source_type.value,
                    description=field_spec.description,
                    business_meaning=field_spec.business_meaning or "",
                    maps_to=field_spec.maps_to,
                    allowed_values=field_spec.allowed_values,
                    value_synonyms=field_spec.value_synonyms or {},
                    value_examples=field_spec.value_examples,
                    is_required=field_spec.is_required,
                    is_indexed=field_spec.is_indexed,
                    human_edited=field_spec.human_edited,
                    source_metadata={
                        "es_type": field_spec.es_type,
                        "index_name": index.name,
                    },
                ))
        
        return unified_fields
    
    @property
    def supports_graph(self) -> bool:
        return True
    
    def build_graph(self, schema: Any) -> Optional[Any]:
        """Build SchemaGraph from YAMLSchemaV1."""
        return None
    
    async def generate_query(
        self,
        context: RetrievalContext,
        question: str,
        llm_client: Any,
    ) -> str:
        """Generate OpenSearch DSL query."""
        prompt = self._build_generation_prompt(context, question)
        messages = [{"role": "user", "content": prompt}]
        response = await llm_client.submit_prompt(messages)
        return self._extract_query(response)
    
    def _build_generation_prompt(
        self, 
        context: RetrievalContext, 
        question: str
    ) -> str:
        field_descriptions = []
        for field in context.matched_fields:
            desc = f"- {field.path} ({field.field_type})"
            if field.description:
                desc += f": {field.description}"
            if field.allowed_values:
                desc += f" [Values: {', '.join(field.allowed_values[:5])}]"
            field_descriptions.append(desc)
        
        value_info = ""
        if context.value_mappings:
            mappings = [f"'{k}' -> '{v}'" for k, v in context.value_mappings.items()]
            value_info = f"\nValue mappings: {', '.join(mappings)}"
        
        return f"""Generate an OpenSearch DSL query for this question.

Question: {question}

Available fields:
{chr(10).join(field_descriptions)}
{value_info}

Return ONLY the OpenSearch DSL query as valid JSON. No explanation."""
    
    def _extract_query(self, response: str) -> str:
        import re
        import json
        
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            return json_match.group(1).strip()
        
        try:
            json.loads(response)
            return response
        except json.JSONDecodeError:
            pass
        
        return response
    
    async def onboard(
        self,
        tenant_id: str,
        document_name: str,
        raw_schema: Union[str, Dict[str, Any]],
        db_session: Optional[Any] = None,
        llm_client: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Onboard OpenSearch index/mapping."""
        logger.info(f"Onboarding OpenSearch index: {tenant_id}/{document_name}")
        
        try:
            schema = self.parse_schema(
                raw_schema, 
                tenant_id=tenant_id,
                document_name=document_name,
                index_pattern=kwargs.get("index_pattern"),
            )
            
            unified_fields = self.to_unified_fields(schema)
            
            enable_enrichment = kwargs.get("enable_enrichment", False)
            if enable_enrichment and llm_client:
                unified_fields = await self._run_enrichment(
                    unified_fields=unified_fields,
                    llm_client=llm_client,
                    tenant_id=tenant_id,
                    document_name=document_name,
                )
            
            node_count = 0
            if db_session:
                node_count = await self._store_to_knowledge_nodes(
                    schema=schema,
                    tenant_id=tenant_id,
                    dataset_name=document_name,
                    db_session=db_session,
                )
            
            return self._build_onboarding_result(
                status="success",
                tenant_id=tenant_id,
                document_name=document_name,
                source_type=self.source_type.value,
                field_count=len(unified_fields),
                entity_count=len(schema.indices or []),
                enrichment_performed=enable_enrichment and llm_client is not None,
                has_graph=False,
            )
            
        except Exception as e:
            logger.error(f"OpenSearch onboarding failed: {e}", exc_info=True)
            return self._build_onboarding_result(
                status="failed",
                tenant_id=tenant_id,
                document_name=document_name,
                source_type=self.source_type.value,
                field_count=0,
                issues=[str(e)],
            )
    
    @property
    def prompt_template_key(self) -> str:
        return "opensearch"
    
    @property
    def display_name(self) -> str:
        return "OpenSearch"
