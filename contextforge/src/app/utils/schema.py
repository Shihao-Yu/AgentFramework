"""
Database schema utilities.

Provides helpers for schema-aware SQL queries.
"""

import re
from functools import lru_cache

from app.core.config import settings


@lru_cache(maxsize=1)
def get_schema() -> str:
    """Get the configured database schema name."""
    return settings.DB_SCHEMA


def sql(query: str) -> str:
    """
    Replace {schema} placeholder with configured schema name.
    
    Usage:
        from app.utils.schema import sql
        
        query = sql('''
            SELECT * FROM {schema}.knowledge_nodes
            WHERE tenant_id = :tenant_id
        ''')
    
    Args:
        query: SQL query with {schema} placeholders
        
    Returns:
        Query with schema name substituted
    """
    return query.replace("{schema}", get_schema())


def table(name: str) -> str:
    """
    Get fully qualified table name with schema.
    
    Usage:
        from app.utils.schema import table
        
        query = f"SELECT * FROM {table('knowledge_nodes')}"
    
    Args:
        name: Table name without schema
        
    Returns:
        Fully qualified table name (e.g., "agent.knowledge_nodes")
    """
    return f"{get_schema()}.{name}"
