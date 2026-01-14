from typing import Optional
import logging

from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class PromptConfig(BaseModel):
    model: str = "gpt-4o-mini"
    context_window: int = 128000
    max_output_tokens: int = 4096
    temperature: float = 0.0
    
    def get_context_budget(self, buffer: int = 500) -> int:
        return self.context_window - self.max_output_tokens - buffer


def _load_local_prompt_config(prompt_name: str) -> Optional[PromptConfig]:
    from app.prompts import load_prompt_config
    return load_prompt_config(prompt_name)


def _load_local_prompt_template(prompt_name: str) -> Optional[str]:
    from app.prompts import load_prompt_template
    return load_prompt_template(prompt_name)


class LangfuseClient:
    
    def __init__(self):
        self._client = None
        self._enabled = False
    
    def _ensure_client(self):
        if self._client is not None:
            return
        
        if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
            logger.info("Langfuse not configured, using local prompts")
            return
        
        try:
            from langfuse import Langfuse
            
            self._client = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST,
            )
            self._enabled = True
            logger.info(f"Langfuse client initialized ({settings.LANGFUSE_HOST})")
        except ImportError:
            logger.warning("langfuse package not installed, using local prompts")
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {e}, using local prompts")
    
    @property
    def is_enabled(self) -> bool:
        self._ensure_client()
        return self._enabled
    
    def get_prompt_config(self, prompt_name: str) -> PromptConfig:
        self._ensure_client()
        
        if self._enabled:
            try:
                prompt = self._client.get_prompt(prompt_name)
                config_data = prompt.config or {}
                
                return PromptConfig(
                    model=config_data.get("model", "gpt-4o-mini"),
                    context_window=config_data.get("context_window", 128000),
                    max_output_tokens=config_data.get("max_output_tokens", 4096),
                    temperature=config_data.get("temperature", 0.0),
                )
            except Exception as e:
                logger.warning(f"Langfuse fetch failed for '{prompt_name}': {e}, falling back to local")
        
        local_config = _load_local_prompt_config(prompt_name)
        if local_config:
            return local_config
        
        return PromptConfig()
    
    def get_prompt_template(self, prompt_name: str) -> Optional[str]:
        self._ensure_client()
        
        if self._enabled:
            try:
                prompt = self._client.get_prompt(prompt_name)
                return prompt.prompt
            except Exception as e:
                logger.warning(f"Langfuse fetch failed for '{prompt_name}': {e}, falling back to local")
        
        return _load_local_prompt_template(prompt_name)


_langfuse_client: Optional[LangfuseClient] = None


def get_langfuse_client() -> LangfuseClient:
    global _langfuse_client
    if _langfuse_client is None:
        _langfuse_client = LangfuseClient()
    return _langfuse_client
