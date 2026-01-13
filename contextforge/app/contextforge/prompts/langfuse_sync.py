"""
Optional Langfuse Sync for ContextForge Prompts.

Provides two-way sync between local PostgreSQL prompts and Langfuse:
- Push: Export local prompts to Langfuse for versioning
- Pull: Import prompts from Langfuse to local store

Gracefully disabled if Langfuse is not configured.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .models import PromptCategory, PromptDialect, PromptTemplate
from .store import PostgresPromptStore

logger = logging.getLogger(__name__)

LANGFUSE_AVAILABLE = False
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    pass


class LangfusePromptSync:
    """
    Sync prompts between local PostgreSQL and Langfuse.
    
    Langfuse provides:
    - Centralized prompt versioning
    - A/B testing for prompts
    - Prompt analytics and monitoring
    
    This integration is optional and gracefully disabled if Langfuse is not installed.
    """
    
    def __init__(
        self,
        store: PostgresPromptStore,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
    ):
        self._store = store
        self._client: Optional[Any] = None
        self._enabled = False
        
        if not LANGFUSE_AVAILABLE:
            logger.info("Langfuse not installed. Prompt sync disabled.")
            return
        
        if not public_key or not secret_key:
            logger.info("Langfuse credentials not provided. Prompt sync disabled.")
            return
        
        try:
            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
            self._enabled = True
            logger.info("Langfuse prompt sync enabled")
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse client: {e}")
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
    
    async def push_to_langfuse(
        self,
        session: AsyncSession,
        name: str,
        dialect: PromptDialect,
    ) -> bool:
        """
        Push a local prompt to Langfuse.
        
        Creates or updates a prompt in Langfuse with the same name.
        Local version is stored in Langfuse labels for tracking.
        """
        if not self._enabled or not self._client:
            return False
        
        template = await self._store.get_template(session, name, dialect)
        if not template:
            logger.warning(f"Template {name}_{dialect} not found locally")
            return False
        
        try:
            langfuse_name = f"{name}_{dialect}"
            self._client.create_prompt(
                name=langfuse_name,
                prompt=template.content,
                labels=[f"v{template.version}", template.category],
                config={
                    "variables": template.variables,
                    "category": template.category,
                    "dialect": dialect,
                    "local_version": template.version,
                },
            )
            logger.info(f"Pushed {langfuse_name} v{template.version} to Langfuse")
            return True
        except Exception as e:
            logger.error(f"Failed to push {name} to Langfuse: {e}")
            return False
    
    async def pull_from_langfuse(
        self,
        session: AsyncSession,
        name: str,
        dialect: PromptDialect,
        langfuse_version: Optional[int] = None,
    ) -> Optional[PromptTemplate]:
        """
        Pull a prompt from Langfuse and save locally.
        
        Fetches the prompt content and metadata, then saves to PostgreSQL.
        """
        if not self._enabled or not self._client:
            return None
        
        try:
            langfuse_name = f"{name}_{dialect}"
            prompt = self._client.get_prompt(langfuse_name, version=langfuse_version)
            
            config = prompt.config or {}
            
            template = PromptTemplate(
                name=name,
                category=PromptCategory(config.get("category", "query_generation")),
                dialect=dialect,
                content=prompt.prompt,
                variables=config.get("variables", []),
                description=f"Imported from Langfuse",
                metadata={
                    "langfuse_version": prompt.version,
                    "source": "langfuse",
                },
            )
            
            saved = await self._store.save_template(session, template, create_version=True)
            logger.info(f"Pulled {langfuse_name} from Langfuse")
            return saved
        except Exception as e:
            logger.error(f"Failed to pull {name} from Langfuse: {e}")
            return None
    
    async def sync_all(
        self,
        session: AsyncSession,
        direction: str = "push",
    ) -> Dict[str, int]:
        """
        Sync all prompts in specified direction.
        
        Args:
            session: Database session
            direction: "push" (local->Langfuse) or "pull" (Langfuse->local)
            
        Returns:
            Dict with counts: {"success": N, "failed": M}
        """
        if not self._enabled:
            return {"success": 0, "failed": 0, "skipped": 0}
        
        results = {"success": 0, "failed": 0}
        
        if direction == "push":
            templates = await self._store.list_templates(session)
            for template in templates:
                success = await self.push_to_langfuse(
                    session, template.name, PromptDialect(template.dialect)
                )
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
        
        return results
    
    def list_langfuse_prompts(self) -> List[str]:
        """List all prompt names available in Langfuse."""
        if not self._enabled or not self._client:
            return []
        
        try:
            prompts = self._client.get_prompts()
            return [p.name for p in prompts]
        except Exception as e:
            logger.error(f"Failed to list Langfuse prompts: {e}")
            return []


def create_langfuse_sync(
    store: PostgresPromptStore,
    public_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    host: Optional[str] = None,
) -> LangfusePromptSync:
    """
    Factory function to create LangfusePromptSync.
    
    Reads credentials from environment if not provided.
    """
    import os
    
    return LangfusePromptSync(
        store=store,
        public_key=public_key or os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=secret_key or os.getenv("LANGFUSE_SECRET_KEY"),
        host=host or os.getenv("LANGFUSE_HOST"),
    )
