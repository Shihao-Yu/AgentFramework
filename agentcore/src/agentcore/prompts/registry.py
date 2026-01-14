import logging
from typing import Any, Optional

from agentcore.prompts.fallbacks import FALLBACK_PROMPTS

logger = logging.getLogger(__name__)

try:
    from infra.tracing.prompts import Prompt, PromptConfig, PromptManager
    _HAS_INFRA = True
except ImportError:
    _HAS_INFRA = False
    PromptManager = None  # type: ignore
    Prompt = None  # type: ignore
    PromptConfig = None  # type: ignore


def _compile_template(template: str, **variables: Any) -> str:
    """Simple template compilation when infra is not available."""
    import re
    
    result = template
    
    def replace_conditional(match: re.Match) -> str:
        var_name = match.group(1)
        content = match.group(2)
        value = variables.get(var_name)
        if value:
            return _compile_template(content, **variables)
        return ""
    
    result = re.sub(
        r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}",
        replace_conditional,
        result,
        flags=re.DOTALL,
    )
    
    def replace_inverted(match: re.Match) -> str:
        var_name = match.group(1)
        content = match.group(2)
        value = variables.get(var_name)
        if not value:
            return _compile_template(content, **variables)
        return ""
    
    result = re.sub(
        r"\{\{\^(\w+)\}\}(.*?)\{\{/\1\}\}",
        replace_inverted,
        result,
        flags=re.DOTALL,
    )
    
    def replace_var(match: re.Match) -> str:
        var_name = match.group(1)
        value = variables.get(var_name, "")
        return str(value) if value is not None else ""
    
    result = re.sub(r"\{\{(\w+)\}\}", replace_var, result)
    
    return result


class PromptRegistry:
    def __init__(self, prompt_manager: Optional["PromptManager"] = None):
        self._manager = prompt_manager
        self._initialized = False
    
    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        
        if self._manager is None and _HAS_INFRA:
            from infra.tracing.prompts import get_prompt_manager
            self._manager = get_prompt_manager()
        
        if self._manager:
            for name, template in FALLBACK_PROMPTS.items():
                self._manager.register_local_prompt(name, template)
    
    def get(self, name: str, **variables: Any) -> str:
        """Get a compiled prompt by name.
        
        Tries Langfuse first, falls back to local prompts.
        """
        self._ensure_initialized()
        
        if self._manager:
            prompt = self._manager.get_prompt(name)
            if prompt:
                return prompt.compile(**variables)
        
        template = FALLBACK_PROMPTS.get(name)
        if template:
            return _compile_template(template, **variables)
        
        raise ValueError(f"Prompt '{name}' not found")
    
    def get_template(self, name: str) -> str:
        """Get raw template without compilation."""
        self._ensure_initialized()
        
        if self._manager:
            prompt = self._manager.get_prompt(name)
            if prompt:
                return prompt.template
        
        template = FALLBACK_PROMPTS.get(name)
        if template:
            return template
        
        raise ValueError(f"Prompt '{name}' not found")


_registry: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry
