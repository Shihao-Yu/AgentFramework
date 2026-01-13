"""
Prompt Manager for ContextForge.

Provides unified interface for prompt retrieval with:
- Database-backed prompts (via PostgresPromptStore)
- File-based fallback prompts (from generation/prompt_templates.py)
- In-memory caching for performance
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .models import PromptCategory, PromptConfig, PromptDialect, PromptTemplate
from .store import PostgresPromptStore

logger = logging.getLogger(__name__)


class CacheEntry:
    """Cache entry with TTL tracking."""
    
    def __init__(self, template: PromptTemplate, ttl_seconds: int):
        self.template = template
        self.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


class PromptManager:
    """
    Unified prompt management with caching and fallbacks.
    
    Lookup order:
    1. In-memory cache (if enabled)
    2. PostgreSQL database (via PostgresPromptStore)
    3. File-based fallback prompts (from FALLBACK_PROMPTS)
    
    Example:
        >>> manager = PromptManager(config=PromptConfig())
        >>> template = await manager.get_prompt(
        ...     session, "query_generation", PromptDialect.POSTGRES
        ... )
        >>> rendered = template.render(schema=schema, question=question)
    """
    
    def __init__(
        self,
        config: Optional[PromptConfig] = None,
        tenant_id: str = "default",
    ):
        self.config = config or PromptConfig()
        self.tenant_id = tenant_id
        self._store = PostgresPromptStore(tenant_id=tenant_id)
        self._cache: Dict[str, CacheEntry] = {}
    
    def _cache_key(self, name: str, dialect: PromptDialect) -> str:
        """Generate cache key for a prompt lookup."""
        return f"{name}_{dialect}"
    
    def _get_from_cache(self, name: str, dialect: PromptDialect) -> Optional[PromptTemplate]:
        """Get prompt from cache if valid."""
        if not self.config.cache_enabled:
            return None
        
        key = self._cache_key(name, dialect)
        entry = self._cache.get(key)
        
        if entry is None:
            return None
        
        if entry.is_expired:
            del self._cache[key]
            return None
        
        return entry.template
    
    def _put_in_cache(self, name: str, dialect: PromptDialect, template: PromptTemplate) -> None:
        """Store prompt in cache."""
        if not self.config.cache_enabled:
            return
        
        key = self._cache_key(name, dialect)
        self._cache[key] = CacheEntry(template, self.config.cache_ttl_seconds)
    
    def clear_cache(self) -> None:
        """Clear all cached prompts."""
        self._cache.clear()
    
    def invalidate(self, name: str, dialect: Optional[PromptDialect] = None) -> None:
        """Invalidate specific cache entries."""
        if dialect:
            key = self._cache_key(name, dialect)
            self._cache.pop(key, None)
        else:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{name}_")]
            for key in keys_to_remove:
                del self._cache[key]
    
    async def get_prompt(
        self,
        session: AsyncSession,
        name: str,
        dialect: PromptDialect = PromptDialect.DEFAULT,
        category: Optional[PromptCategory] = None,
    ) -> Optional[PromptTemplate]:
        """
        Get a prompt template with fallback logic.
        
        Lookup order:
        1. Cache (if enabled)
        2. Database (specific dialect)
        3. Database (default dialect)
        4. File-based fallback
        
        Args:
            session: Async database session
            name: Template name (e.g., "query_generation")
            dialect: Target dialect
            category: Optional category filter
            
        Returns:
            PromptTemplate if found, None otherwise
        """
        cached = self._get_from_cache(name, dialect)
        if cached:
            return cached
        
        template = await self._store.get_template_with_fallback(session, name, dialect)
        
        if template:
            self._put_in_cache(name, dialect, template)
            return template
        
        if self.config.fallback_enabled:
            template = self._get_file_fallback(name, dialect, category)
            if template:
                self._put_in_cache(name, dialect, template)
                return template
        
        return None
    
    def _get_file_fallback(
        self,
        name: str,
        dialect: PromptDialect,
        category: Optional[PromptCategory] = None,
    ) -> Optional[PromptTemplate]:
        """
        Get prompt from file-based fallbacks.
        
        Maps name to the appropriate prompt dictionary from
        generation/prompt_templates.py.
        """
        from ..generation.prompt_templates import FALLBACK_PROMPTS
        
        category_key = category.value if category else self._infer_category(name)
        if not category_key:
            return None
        
        prompts_dict = FALLBACK_PROMPTS.get(category_key)
        if not prompts_dict:
            return None
        
        dialect_key = dialect.value if dialect else "default"
        content = prompts_dict.get(dialect_key)
        
        if not content and dialect_key != "default":
            content = prompts_dict.get("default")
        
        if not content:
            return None
        
        return PromptTemplate(
            id=f"fallback_{name}_{dialect_key}",
            name=name,
            category=PromptCategory(category_key) if category_key in [c.value for c in PromptCategory] else PromptCategory.QUERY_GENERATION,
            dialect=dialect,
            content=content,
            variables=self._extract_variables(content),
            description=f"Fallback template for {name}",
            version=0,
            is_active=True,
            metadata={"source": "fallback"},
        )
    
    def _infer_category(self, name: str) -> Optional[str]:
        """Infer category from template name."""
        name_lower = name.lower()
        
        if "schema" in name_lower and "analysis" in name_lower:
            return "schema_analysis"
        if "field" in name_lower and "inference" in name_lower:
            return "field_inference"
        if "qa" in name_lower or "example" in name_lower:
            return "qa_generation"
        if "query" in name_lower:
            return "query_generation"
        if "disambig" in name_lower:
            return "disambiguation"
        if "valid" in name_lower:
            return "validation"
        if "plan" in name_lower:
            return "planning"
        
        return "query_generation"
    
    def _extract_variables(self, content: str) -> list:
        """Extract placeholder variable names from template content."""
        import re
        pattern = r"\{(\w+)\}"
        return list(set(re.findall(pattern, content)))
    
    async def render_prompt(
        self,
        session: AsyncSession,
        name: str,
        dialect: PromptDialect,
        variables: Dict[str, Any],
        category: Optional[PromptCategory] = None,
    ) -> Optional[str]:
        """
        Get and render a prompt in one call.
        
        Args:
            session: Async database session
            name: Template name
            dialect: Target dialect
            variables: Variables to substitute
            category: Optional category filter
            
        Returns:
            Rendered prompt string, or None if template not found
        """
        template = await self.get_prompt(session, name, dialect, category)
        if not template:
            return None
        
        try:
            return template.render(**variables)
        except KeyError as e:
            logger.warning(f"Missing variable {e} for template {name}")
            return template.render_safe(**variables)
    
    async def save_prompt(
        self,
        session: AsyncSession,
        template: PromptTemplate,
        create_version: bool = True,
    ) -> PromptTemplate:
        """
        Save a prompt template.
        
        Args:
            session: Async database session
            template: Template to save
            create_version: Whether to create version history
            
        Returns:
            Saved template
        """
        saved = await self._store.save_template(session, template, create_version)
        self.invalidate(template.name, template.dialect)
        return saved
    
    async def delete_prompt(
        self,
        session: AsyncSession,
        name: str,
        dialect: PromptDialect = PromptDialect.DEFAULT,
        delete_versions: bool = False,
    ) -> bool:
        """
        Delete a prompt template.
        
        Args:
            session: Async database session
            name: Template name
            dialect: Template dialect
            delete_versions: Also delete version history
            
        Returns:
            True if deleted
        """
        deleted = await self._store.delete_template(session, name, dialect, delete_versions)
        if deleted:
            self.invalidate(name, dialect)
        return deleted
    
    async def list_prompts(
        self,
        session: AsyncSession,
        category: Optional[PromptCategory] = None,
        dialect: Optional[PromptDialect] = None,
    ) -> list:
        """
        List all prompts with optional filtering.
        
        Args:
            session: Async database session
            category: Filter by category
            dialect: Filter by dialect
            
        Returns:
            List of PromptTemplate objects
        """
        return await self._store.list_templates(session, category, dialect)


def get_prompt_manager(tenant_id: str = "default") -> PromptManager:
    """Factory function to create a PromptManager instance."""
    return PromptManager(tenant_id=tenant_id)
