"""
PostgreSQL Data Source Implementation.

Implements the DataSource protocol for PostgreSQL,
providing DDL parsing, FK graph building, and SQL query generation.
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


@register_source(SourceType.POSTGRES)
class PostgresSource(DataSourceBase, SourceOnboardingMixin):
    """
    PostgreSQL data source.
    
    Supports:
    - DDL parsing (CREATE TABLE statements)
    - PostgreSQL SQL generation
    """
    
    source_type = SourceType.POSTGRES
    
    def __init__(self, **config):
        self.config = config
        self.connection_string = config.get("connection_string")
        self.schema_filter = config.get("schema_filter", ["public"])
    
    def parse_schema(
        self, 
        raw_schema: Union[str, Dict[str, Any]], 
        **kwargs
    ) -> Any:
        """
        Parse PostgreSQL DDL into schema model.
        
        Args:
            raw_schema: DDL string with CREATE TABLE statements
            **kwargs:
                - tenant_id: Tenant identifier
        
        Returns:
            Schema model with tables and columns
        """
        from ...schema.yaml_schema import YAMLSchemaV1, SchemaType, IndexSpec, FieldSpec
        
        tenant_id = kwargs.get("tenant_id", "default")
        
        if isinstance(raw_schema, dict):
            raise NotImplementedError("Dict schema parsing not yet implemented")
        
        schema = YAMLSchemaV1(
            tenant_id=tenant_id,
            version="1.0",
            schema_type=SchemaType.POSTGRES,
        )
        
        table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([^\s(]+)\s*\((.*?)\);?'
        
        for match in re.finditer(table_pattern, raw_schema, re.IGNORECASE | re.DOTALL):
            table_name = match.group(1).strip('`"[]')
            columns_str = match.group(2)
            
            fields = []
            for line in columns_str.split(','):
                line = line.strip()
                if not line or line.upper().startswith(('PRIMARY', 'FOREIGN', 'UNIQUE', 'INDEX', 'CONSTRAINT', 'KEY', 'CHECK')):
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    col_name = parts[0].strip('`"[]')
                    col_type = parts[1].upper()
                    
                    is_required = 'NOT NULL' in line.upper()
                    
                    fields.append(FieldSpec(
                        path=f"{table_name}.{col_name}",
                        es_type=self._pg_type_to_es_type(col_type),
                        description="",
                        is_required=is_required,
                    ))
            
            if fields:
                schema.indices.append(IndexSpec(
                    name=table_name,
                    fields=fields,
                ))
        
        return schema
    
    def _pg_type_to_es_type(self, pg_type: str) -> str:
        """Convert PostgreSQL type to normalized type."""
        pg_type = pg_type.upper()
        
        if any(t in pg_type for t in ['INT', 'SERIAL', 'BIGINT', 'SMALLINT']):
            return "long"
        elif any(t in pg_type for t in ['FLOAT', 'DOUBLE', 'DECIMAL', 'NUMERIC', 'REAL']):
            return "double"
        elif any(t in pg_type for t in ['BOOL']):
            return "boolean"
        elif any(t in pg_type for t in ['DATE', 'TIME', 'TIMESTAMP']):
            return "date"
        elif any(t in pg_type for t in ['JSON', 'JSONB']):
            return "object"
        elif any(t in pg_type for t in ['ARRAY']):
            return "nested"
        else:
            return "text"
    
    def to_unified_fields(self, schema: Any) -> List[UnifiedField]:
        """Convert PostgreSQL schema to UnifiedField format."""
        unified_fields = []
        
        for index in schema.indices:
            for field_spec in index.fields:
                unified_fields.append(UnifiedField(
                    path=field_spec.path,
                    field_type=field_spec.es_type,
                    source_type=self.source_type.value,
                    description=field_spec.description,
                    maps_to=field_spec.maps_to,
                    is_required=getattr(field_spec, 'is_required', False),
                    source_metadata={
                        "table_name": index.name,
                        "pg_type": field_spec.es_type,
                    },
                ))
        
        return unified_fields
    
    @property
    def supports_graph(self) -> bool:
        return True
    
    def build_graph(self, schema: Any) -> Optional[Any]:
        logger.warning("PostgreSQL FK graph not yet implemented")
        return None
    
    async def generate_query(
        self,
        context: RetrievalContext,
        question: str,
        llm_client: Any,
    ) -> str:
        """Generate PostgreSQL SQL query."""
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
        
        return f"""Generate a PostgreSQL SQL query for this question.

Question: {question}

Available columns:
{chr(10).join(table_info)}

Rules:
- Use PostgreSQL syntax
- Use proper JOINs when multiple tables are involved
- Use appropriate WHERE clauses for filtering

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
        """Onboard PostgreSQL schema."""
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
            logger.error(f"PostgreSQL onboarding failed: {e}", exc_info=True)
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
        return "postgres"
    
    @property
    def display_name(self) -> str:
        return "PostgreSQL"
