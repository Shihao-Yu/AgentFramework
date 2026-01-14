"""
PostgreSQL Data Source for ContextForge.

Provides DDL parsing, FK graph building, and SQL query generation.
"""

from .source import PostgresSource

__all__ = ["PostgresSource"]
