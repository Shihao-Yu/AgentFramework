"""
ContextForge Data Sources.

This module provides a plugin-like architecture for data sources.
Each source (OpenSearch, PostgreSQL, REST API, etc.) implements the
DataSource protocol and registers itself with the registry.

Usage:
    from app.contextforge.sources import get_source, list_sources
    
    # Get a source instance
    source = get_source("opensearch")
    
    # Parse schema
    schema = source.parse_schema(raw_mapping, tenant_id="acme")
    
    # Generate query
    query = await source.generate_query(context, question, llm_client)
    
    # List available sources
    print(list_sources())  # ["opensearch", "rest_api", "postgres", ...]

Available Sources:
    - opensearch: OpenSearch/Elasticsearch indices
    - rest_api: REST APIs via OpenAPI/Swagger specs
    - postgres: PostgreSQL databases
    - clickhouse: ClickHouse databases
"""

from ..core.protocols import (
    DataSource,
    DataSourceBase,
    SourceType,
    UnifiedField,
    UnifiedSchema,
    ConceptInfo,
    RetrievalContext,
    register_source,
    get_source,
    list_sources,
    is_source_registered,
)

from . import opensearch
from . import rest_api
from . import postgres
from . import clickhouse

__all__ = [
    "DataSource",
    "DataSourceBase",
    "SourceType",
    "UnifiedField",
    "UnifiedSchema",
    "ConceptInfo",
    "RetrievalContext",
    "register_source",
    "get_source",
    "list_sources",
    "is_source_registered",
]
