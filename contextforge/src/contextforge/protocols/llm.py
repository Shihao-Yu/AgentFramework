"""
LLM Provider Protocol

Implement this protocol to provide custom LLM generation.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """
    Protocol for LLM (Large Language Model) providers.
    
    Implement this to integrate with your LLM service
    (OpenAI, Anthropic, local models, etc.)
    
    Example:
        class MyLLMProvider(LLMProvider):
            def __init__(self, api_key: str):
                self.client = MyLLMService(api_key)
            
            async def generate(
                self,
                prompt: str,
                system_prompt: str | None = None,
                temperature: float = 0.0,
                max_tokens: int = 1024,
            ) -> str:
                return await self.client.complete(
                    prompt=prompt,
                    system=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
    """
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate text completion.
        
        Args:
            prompt: User prompt / input text
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
        """
        ...
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> dict:
        """
        Generate JSON response.
        
        Default implementation calls generate() and parses JSON.
        Override if your provider has native JSON mode.
        
        Args:
            prompt: User prompt / input text
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Parsed JSON response as dict
        """
        ...
