"""
ContextForge - Context Assembly and NL-to-Structured Text Generation

A unified system for:
1. Admin Screen - Manage knowledge nodes (FAQs, playbooks, permissions)
2. Context Management - Graph-based retrieval with hybrid search
3. NL to Structured Text - Text-to-SQL, Text-to-DSL, Text-to-API generation

This package consolidates the AgenticSearch/QueryForge framework into
Knowledge Verse, using PostgreSQL + pgvector instead of ChromaDB.
"""

__version__ = "0.1.0"

from . import core
from . import schema
from . import sources
from . import graph
from . import retrieval
from . import storage
from . import generation
from . import prompts
from . import cli
from . import learning

__all__ = [
    "core",
    "schema",
    "sources",
    "graph",
    "retrieval",
    "storage",
    "generation",
    "prompts",
    "cli",
    "learning",
]
