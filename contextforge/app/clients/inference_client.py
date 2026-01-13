"""
Abstract interface for LLM inference.

Implement this interface with your LLM service (OpenAI, Anthropic, custom model, etc.)
"""

from abc import ABC, abstractmethod
from typing import Optional, Type, TypeVar
from pydantic import BaseModel

from app.clients.base import BaseClient

T = TypeVar("T", bound=BaseModel)


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
    ) -> T:
        """
        Generate structured output matching a Pydantic model.
        
        Uses techniques like JSON mode or tool calling to ensure
        the response matches the expected schema.
        
        Args:
            prompt: User prompt / query
            response_model: Pydantic model class for response structure
            system_prompt: Optional system instructions
            temperature: Sampling temperature (lower = more deterministic)
            
        Returns:
            Instance of response_model populated with generated values
            
        Raises:
            Exception: If generation fails or response doesn't match schema
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Check if LLM service is available.
        
        Default implementation tries a simple generation.
        Override if your service has a dedicated health endpoint.
        """
        try:
            result = await self.generate("Say 'ok'", max_tokens=10)
            return len(result) > 0
        except Exception:
            return False


class MockInferenceClient(InferenceClient):
    """
    Mock implementation for testing.
    
    Use this for:
    - Testing without external dependencies
    - Development when LLM service is unavailable
    
    Replace with actual implementation for production.
    
    Note: generate_structured returns default model instance,
    which may not be valid for models with required fields.
    """
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Return a mock response."""
        return "This is a mock response. Replace MockInferenceClient with a real implementation."
    
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> T:
        """
        Return a default instance of the response model.
        
        Warning: This will fail for models with required fields
        that don't have defaults. Override this method or use
        a real implementation for such cases.
        """
        # Try to create with defaults
        try:
            return response_model()
        except Exception:
            # If model has required fields, this will fail
            raise NotImplementedError(
                f"MockInferenceClient cannot create default instance of {response_model}. "
                "Use a real implementation or provide a mock with valid test data."
            )
    
    async def health_check(self) -> bool:
        """Always returns True."""
        return True
