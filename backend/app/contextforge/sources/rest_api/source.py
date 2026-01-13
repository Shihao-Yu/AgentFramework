"""
REST API Data Source Implementation.

Implements the DataSource protocol for REST APIs via OpenAPI/Swagger specs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from ...core.protocols import (
    DataSourceBase,
    RetrievalContext,
    SourceType,
    UnifiedField,
    register_source,
)
from ..base import SourceOnboardingMixin

logger = logging.getLogger(__name__)


@register_source(SourceType.REST_API)
class RestAPISource(DataSourceBase, SourceOnboardingMixin):
    """
    REST API data source via OpenAPI/Swagger specs.
    
    Supports:
    - OpenAPI 3.x and Swagger 2.0 parsing
    - Endpoint and parameter extraction
    - REST API call generation
    """
    
    source_type = SourceType.REST_API
    
    def __init__(self, **config):
        self.config = config
        self.base_url = config.get("base_url")
    
    def parse_schema(
        self, 
        raw_schema: Union[str, Dict[str, Any]], 
        **kwargs
    ) -> Any:
        """
        Parse OpenAPI/Swagger spec into schema model.
        
        Args:
            raw_schema: OpenAPI spec (dict or JSON/YAML string)
            **kwargs:
                - tenant_id: Tenant identifier
        
        Returns:
            Parsed schema with endpoints and concepts
        """
        from .parser import OpenAPIParser
        from ...schema.yaml_schema import YAMLSchemaV1, SchemaType
        import json
        import yaml as yaml_lib
        
        spec_dict: Dict[str, Any]
        if isinstance(raw_schema, str):
            try:
                spec_dict = json.loads(raw_schema)
            except json.JSONDecodeError:
                spec_dict = yaml_lib.safe_load(raw_schema)
        elif isinstance(raw_schema, dict):
            spec_dict = raw_schema
        else:
            raise ValueError(f"raw_schema must be a dict or string, got {type(raw_schema)}")
        
        tenant_id = kwargs.get("tenant_id", "default")
        
        parser = OpenAPIParser(spec_dict)
        endpoints, concepts = parser.parse()
        api_info = parser.get_api_info()
        
        schema = YAMLSchemaV1(
            tenant_id=tenant_id,
            version="1.0",
            schema_type=SchemaType.REST_API,
            concepts=concepts,
            endpoints=endpoints,
        )
        
        return schema
    
    def to_unified_fields(self, schema: Any) -> List[UnifiedField]:
        """Convert API parameters to UnifiedField format."""
        unified_fields = []
        
        for endpoint in schema.endpoints:
            for param in endpoint.parameters:
                unified_fields.append(UnifiedField(
                    path=f"{endpoint.path}:{param.name}",
                    field_type=param.param_type,
                    source_type=self.source_type.value,
                    description=param.description,
                    maps_to=param.maps_to,
                    allowed_values=param.allowed_values,
                    value_synonyms=param.value_synonyms or {},
                    value_examples=param.value_examples,
                    is_required=param.required,
                    source_metadata={
                        "location": str(param.location),
                        "endpoint": endpoint.path,
                        "method": str(endpoint.method),
                    },
                ))
        
        return unified_fields
    
    @property
    def supports_graph(self) -> bool:
        return True
    
    def build_graph(self, schema: Any) -> Optional[Any]:
        return None
    
    async def generate_query(
        self,
        context: RetrievalContext,
        question: str,
        llm_client: Any,
    ) -> str:
        """Generate REST API call specification."""
        prompt = self._build_generation_prompt(context, question)
        messages = [{"role": "user", "content": prompt}]
        response = await llm_client.submit_prompt(messages)
        return response
    
    def _build_generation_prompt(
        self, 
        context: RetrievalContext, 
        question: str
    ) -> str:
        field_descriptions = []
        for field in context.matched_fields:
            meta = field.source_metadata or {}
            endpoint = meta.get("endpoint", "unknown")
            method = meta.get("method", "GET")
            location = meta.get("location", "query")
            
            desc = f"- {method} {endpoint} - {field.path} ({location})"
            if field.description:
                desc += f": {field.description}"
            field_descriptions.append(desc)
        
        return f"""Generate a REST API call specification for this question.

Question: {question}

Available endpoints and parameters:
{chr(10).join(field_descriptions)}

Return a JSON object with: method, path, query_params, body (if POST/PUT).
No explanation, just the JSON."""
    
    async def onboard(
        self,
        tenant_id: str,
        document_name: str,
        raw_schema: Union[str, Dict[str, Any]],
        db_session: Optional[Any] = None,
        llm_client: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Onboard REST API from OpenAPI spec."""
        logger.info(f"Onboarding REST API: {tenant_id}/{document_name}")
        
        try:
            schema = self.parse_schema(raw_schema, tenant_id=tenant_id)
            unified_fields = self.to_unified_fields(schema)
            
            return self._build_onboarding_result(
                status="success",
                tenant_id=tenant_id,
                document_name=document_name,
                source_type=self.source_type.value,
                field_count=len(unified_fields),
                entity_count=len(schema.endpoints or []),
            )
            
        except Exception as e:
            logger.error(f"REST API onboarding failed: {e}", exc_info=True)
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
        return "rest_api"
    
    @property
    def display_name(self) -> str:
        return "REST API"
