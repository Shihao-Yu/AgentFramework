"""
OpenSearch Data Source for ContextForge.

Provides schema parsing, graph-based retrieval, and DSL query generation
for OpenSearch/Elasticsearch indices.
"""

from .source import OpenSearchSource
from .parser import MappingConverter, import_mapping_from_file

__all__ = [
    "OpenSearchSource",
    "MappingConverter",
    "import_mapping_from_file",
]
