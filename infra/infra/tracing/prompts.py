import logging
import os
import re
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def compile_template(template: str, **variables: Any) -> str:
    """Compile a template by substituting {{variable}} placeholders.
    
    Supports:
    - {{variable}} - simple substitution
    - {{#variable}}content{{/variable}} - conditional block (if variable is truthy)
    - {{^variable}}content{{/variable}} - inverted block (if variable is falsy)
    """
    result = template
    
    # Handle conditional blocks {{#var}}...{{/var}}
    def replace_conditional(match: re.Match) -> str:
        var_name = match.group(1)
        content = match.group(2)
        value = variables.get(var_name)
        if value:
            return compile_template(content, **variables)
        return ""
    
    result = re.sub(
        r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}",
        replace_conditional,
        result,
        flags=re.DOTALL,
    )
    
    # Handle inverted blocks {{^var}}...{{/var}}
    def replace_inverted(match: re.Match) -> str:
        var_name = match.group(1)
        content = match.group(2)
        value = variables.get(var_name)
        if not value:
            return compile_template(content, **variables)
        return ""
    
    result = re.sub(
        r"\{\{\^(\w+)\}\}(.*?)\{\{/\1\}\}",
        replace_inverted,
        result,
        flags=re.DOTALL,
    )
    
    # Handle simple variable substitution {{var}}
    def replace_var(match: re.Match) -> str:
        var_name = match.group(1)
        value = variables.get(var_name, "")
        return str(value) if value is not None else ""
    
    result = re.sub(r"\{\{(\w+)\}\}", replace_var, result)
    
    return result


class PromptConfig(BaseModel):
    model: str = "gpt-4o-mini"
    context_window: int = 128000
    max_output_tokens: int = 4096
    temperature: float = 0.0

    def get_context_budget(self, buffer: int = 500) -> int:
        return self.context_window - self.max_output_tokens - buffer


class Prompt(BaseModel):
    name: str
    template: str
    config: PromptConfig = PromptConfig()

    def compile(self, **variables: Any) -> str:
        """Compile the template with variable substitution."""
        return compile_template(self.template, **variables)


class PromptManager:
    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
    ):
        self._public_key = public_key or os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        self._secret_key = secret_key or os.environ.get("LANGFUSE_SECRET_KEY", "")
        self._host = host or os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
        self._client = None
        self._enabled = False
        self._local_prompts: dict[str, Prompt] = {}

    def _ensure_client(self) -> None:
        if self._client is not None:
            return

        if not self._public_key or not self._secret_key:
            logger.info("Langfuse not configured, using local prompts only")
            return

        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=self._public_key,
                secret_key=self._secret_key,
                host=self._host,
            )
            self._enabled = True
            logger.info(f"Langfuse prompt manager initialized ({self._host})")
        except ImportError:
            logger.warning("langfuse package not installed")
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {e}")

    @property
    def is_enabled(self) -> bool:
        self._ensure_client()
        return self._enabled

    def register_local_prompt(
        self,
        name: str,
        template: str,
        config: Optional[PromptConfig] = None,
    ) -> None:
        self._local_prompts[name] = Prompt(
            name=name,
            template=template,
            config=config or PromptConfig(),
        )

    def get_prompt(self, name: str) -> Optional[Prompt]:
        self._ensure_client()

        if self._enabled:
            try:
                prompt = self._client.get_prompt(name)
                config_data = prompt.config or {}

                return Prompt(
                    name=name,
                    template=prompt.prompt,
                    config=PromptConfig(
                        model=config_data.get("model", "gpt-4o-mini"),
                        context_window=config_data.get("context_window", 128000),
                        max_output_tokens=config_data.get("max_output_tokens", 4096),
                        temperature=config_data.get("temperature", 0.0),
                    ),
                )
            except Exception as e:
                logger.warning(f"Langfuse fetch failed for '{name}': {e}, falling back to local")

        return self._local_prompts.get(name)

    def get_config(self, name: str) -> PromptConfig:
        prompt = self.get_prompt(name)
        if prompt:
            return prompt.config
        return PromptConfig()

    def get_template(self, name: str) -> Optional[str]:
        prompt = self.get_prompt(name)
        return prompt.template if prompt else None


_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
