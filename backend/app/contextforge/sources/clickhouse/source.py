"""
ClickHouse Data Source Implementation.

Implements the DataSource protocol for ClickHouse,
providing DDL parsing and ClickHouse SQL query generation.
"""

from __future__ import annotations

import logging
import re
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


@register_source(SourceType.CLICKHOUSE)
class ClickHouseSource(DataSourceBase, SourceOnboardingMixin):
    """
    ClickHouse data source.
    
    Supports:
    - DDL parsing (CREATE TABLE statements)
    - ClickHouse SQL generation
    """
    
    source_type = SourceType.CLICKHOUSE
    
    def __init__(self, **config):
        self.config = config
        self.connection_string = config.get("connection_string")
    
    def parse_schema(
        self, 
        raw_schema: Union[str, Dict[str, Any]], 
        **kwargs
    ) -> Any:
        """
        Parse ClickHouse DDL into schema model.
        """
        from ...schema.yaml_schema import YAMLSchemaV1, SchemaType, IndexSpec, FieldSpec
        
        tenant_id = kwargs.get("tenant_id", "default")
        
        if isinstance(raw_schema, dict):
            raise NotImplementedError("Dict schema parsing not yet implemented")
        
        schema = YAMLSchemaV1(
            tenant_id=tenant_id,
            version="1.0",
            schema_type=SchemaType.CLICKHOUSE,
        )
        
        table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([^\s(]+)\s*\((.*?)\)\s*ENGINE'
        
        for match in re.finditer(table_pattern, raw_schema, re.IGNORECASE | re.DOTALL):
            table_name = match.group(1).strip('`"')
            columns_str = match.group(2)
            
            fields = []
            for line in columns_str.split(','):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    col_name = parts[0].strip('`"')
                    col_type = parts[1]
                    
                    fields.append(FieldSpec(
                        path=f"{table_name}.{col_name}",
                        es_type=self._ch_type_to_es_type(col_type),
                        description="",
                    ))
            
            if fields:
                schema.indices.append(IndexSpec(
                    name=table_name,
                    fields=fields,
                ))
        
        return schema
    
    def _ch_type_to_es_type(self, ch_type: str) -> str:
        """Convert ClickHouse type to normalized type."""
        ch_type_lower = ch_type.lower()
        
        if any(t in ch_type_lower for t in ['int', 'uint']):
            return "long"
        elif any(t in ch_type_lower for t in ['float', 'double', 'decimal']):
            return "double"
        elif 'bool' in ch_type_lower:
            return "boolean"
        elif any(t in ch_type_lower for t in ['date', 'datetime']):
            return "date"
        elif 'array' in ch_type_lower:
            return "nested"
        elif any(t in ch_type_lower for t in ['map', 'tuple', 'nested']):
            return "object"
        else:
            return "text"
    
    def to_unified_fields(self, schema: Any) -> List[UnifiedField]:
        """Convert ClickHouse schema to UnifiedField format."""
        unified_fields = []
        
        for index in schema.indices:
            for field_spec in index.fields:
                unified_fields.append(UnifiedField(
                    path=field_spec.path,
                    field_type=field_spec.es_type,
                    source_type=self.source_type.value,
                    description=field_spec.description,
                    maps_to=field_spec.maps_to,
                    source_metadata={
                        "table_name": index.name,
                    },
                ))
        
        return unified_fields
    
    @property
    def supports_graph(self) -> bool:
        return False
    
    def build_graph(self, schema: Any) -> Optional[Any]:
        return None
    
    async def generate_query(
        self,
        context: RetrievalContext,
        question: str,
        llm_client: Any,
    ) -> str:
        """Generate ClickHouse SQL query."""
        prompt = self._build_generation_prompt(context, question)
        messages = [{"role": "user", "content": prompt}]
        response = await llm_client.submit_prompt(messages)
        return self._extract_sql(response)
    
    def _build_generation_prompt(
        self, 
        context: RetrievalContext, 
        question: str
    ) -> str:
        table_info = []
        for field in context.matched_fields:
            table_name = field.source_metadata.get("table_name", "unknown")
            col_name = field.path.split(".")[-1] if "." in field.path else field.path
            desc = f"- {table_name}.{col_name} ({field.field_type})"
            if field.description:
                desc += f": {field.description}"
            table_info.append(desc)
        
        return f"""Generate a ClickHouse SQL query for this question.

Question: {question}

Available columns:
{chr(10).join(table_info)}

Rules:
- Use ClickHouse SQL syntax
- Prefer FINAL for ReplacingMergeTree tables
- Use appropriate aggregation functions

Return ONLY the SQL query. No explanation."""
    
    def _extract_sql(self, response: str) -> str:
        import re
        
        sql_match = re.search(r'```(?:sql)?\s*([\s\S]*?)```', response)
        if sql_match:
            return sql_match.group(1).strip()
        
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
        """Onboard ClickHouse schema."""
        try:
            schema = self.parse_schema(raw_schema, tenant_id=tenant_id, **kwargs)
            unified_fields = self.to_unified_fields(schema)
            
            return self._build_onboarding_result(
                status="success",
                tenant_id=tenant_id,
                document_name=document_name,
                source_type=self.source_type.value,
                field_count=len(unified_fields),
                entity_count=len(schema.indices),
            )
            
        except Exception as e:
            logger.error(f"ClickHouse onboarding failed: {e}", exc_info=True)
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
        return "clickhouse"
    
    @property
    def display_name(self) -> str:
        return "ClickHouse"
