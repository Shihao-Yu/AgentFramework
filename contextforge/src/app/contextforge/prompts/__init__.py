"""
ContextForge Prompt Management Module.

Provides prompt template management with:
- PostgreSQL storage via KnowledgeNode
- In-memory caching for performance
- File-based fallback prompts
- Optional Langfuse sync for versioning

Usage:
    >>> from app.contextforge.prompts import PromptManager, PromptTemplate
    >>> 
    >>> manager = PromptManager(tenant_id="my_tenant")
    >>> template = await manager.get_prompt(session, "query_generation", PromptDialect.POSTGRES)
    >>> rendered = template.render(schema=schema, question=question)
"""

from .models import (
    PromptCategory,
    PromptConfig,
    PromptDialect,
    PromptLookupKey,
    PromptTemplate,
    PromptVersion,
)
from .store import PostgresPromptStore
from .manager import PromptManager, get_prompt_manager
from .langfuse_sync import LangfusePromptSync, create_langfuse_sync

__all__ = [
    # Models
    "PromptTemplate",
    "PromptVersion",
    "PromptConfig",
    "PromptCategory",
    "PromptDialect",
    "PromptLookupKey",
    # Storage
    "PostgresPromptStore",
    # Manager
    "PromptManager",
    "get_prompt_manager",
    # Langfuse
    "LangfusePromptSync",
    "create_langfuse_sync",
]
