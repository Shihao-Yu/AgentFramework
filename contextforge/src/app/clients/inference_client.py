"""
Abstract interface for LLM inference.

Implement this interface with your LLM service (OpenAI, Anthropic, custom model, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Optional, Type, TypeVar
from pydantic import BaseModel

from app.clients.base import BaseClient

T = TypeVar("T", bound=BaseModel)


@dataclass
class Message:
    role: Literal["system", "user", "assistant"]
    content: str

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        return cls(role="assistant", content=content)


class InferenceClient(BaseClient):
    """
    Abstract interface for LLM inference.
    
    Implementations should connect to your LLM service
    (e.g., OpenAI GPT-4, Anthropic Claude, custom model).
    
    Supports both free-form text generation and structured output.
    
    Example implementation:
    
    ```python
    import instructor
    from openai import AsyncOpenAI
    
    class OpenAIInferenceClient(InferenceClient):
        def __init__(self, api_key: str):
            self.client = instructor.from_openai(
                AsyncOpenAI(api_key=api_key)
            )
            self.model = "gpt-4o"
        
        async def generate(
            self,
            prompt: str,
            system_prompt: Optional[str] = None,
            temperature: float = 0.7,
            max_tokens: int = 1024,
        ) -> str:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        
        async def generate_structured(
            self,
            prompt: str,
            response_model: Type[T],
            system_prompt: Optional[str] = None,
            temperature: float = 0.3,
        ) -> T:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            return await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_model=response_model,
                temperature=temperature,
            )
    ```
    """
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate text completion.
        
        Args:
            prompt: User prompt / query
            system_prompt: Optional system instructions
            temperature: Sampling temperature (0-1, higher = more creative)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
            
        Raises:
            Exception: If generation fails
        """
        pass
    
    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> T:
        pass

    @abstractmethod
    async def complete_structured(
        self,
        messages: list[Message],
        response_model: Type[T],
        temperature: float = 0.3,
    ) -> T:
        pass

    async def health_check(self) -> bool:
        try:
            result = await self.generate("Say 'ok'", max_tokens=10)
            return len(result) > 0
        except Exception:
            return False
