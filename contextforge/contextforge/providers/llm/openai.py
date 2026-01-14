"""
OpenAI LLM Provider

Uses OpenAI's GPT models for text generation.

Installation:
    pip install contextforge[openai]
    # or
    pip install openai

Usage:
    from contextforge.providers.llm import OpenAILLMProvider
    
    provider = OpenAILLMProvider(
        api_key="sk-...",
        model="gpt-4o-mini",
    )
    
    response = await provider.generate("Explain quantum computing")
"""

from __future__ import annotations

import json
import os
from typing import Optional

from contextforge.core.exceptions import ConfigurationError


class OpenAILLMProvider:
    """
    OpenAI LLM provider using the chat completions API.
    
    Supports:
    - gpt-4o, gpt-4o-mini (recommended)
    - gpt-4-turbo, gpt-4
    - gpt-3.5-turbo
    
    Args:
        api_key: OpenAI API key (default: from OPENAI_API_KEY env var)
        model: Model name (default: gpt-4o-mini)
        timeout: Request timeout in seconds (default: 120)
    
    Example:
        provider = OpenAILLMProvider()
        
        # Text generation
        response = await provider.generate(
            prompt="Write a haiku about coding",
            temperature=0.7,
        )
        
        # JSON generation
        data = await provider.generate_json(
            prompt="Return a JSON object with name and age fields",
            system_prompt="Always respond with valid JSON",
        )
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: float = 120.0,
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ConfigurationError(
                "OpenAI API key not provided. "
                "Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )
        
        self._model = model
        self._timeout = timeout
        self._client = None
    
    @property
    def _openai_client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ConfigurationError(
                    "OpenAI library not installed. "
                    "Run: pip install contextforge[openai]"
                )
            
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                timeout=self._timeout,
            )
        return self._client
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
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
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        messages.append({
            "role": "user",
            "content": prompt,
        })
        
        response = await self._openai_client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return response.choices[0].message.content or ""
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> dict:
        messages = []
        
        default_system = "You are a helpful assistant that responds with valid JSON."
        if system_prompt:
            full_system = f"{system_prompt}\n\nAlways respond with valid JSON."
        else:
            full_system = default_system
        
        messages.append({"role": "system", "content": full_system})
        messages.append({"role": "user", "content": prompt})
        
        response = await self._openai_client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    
    async def generate_structured(
        self,
        prompt: str,
        response_model,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        model: Optional[str] = None,
    ):
        import instructor
        
        client = instructor.from_openai(self._openai_client)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return await client.chat.completions.create(
            model=model or self._model,
            messages=messages,
            response_model=response_model,
            temperature=temperature,
        )
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ):
        """
        Generate text completion with streaming.
        
        Yields tokens as they are generated.
        
        Args:
            prompt: User prompt / input text
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Yields:
            Generated text tokens
        """
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        messages.append({
            "role": "user",
            "content": prompt,
        })
        
        stream = await self._openai_client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def __repr__(self) -> str:
        return f"OpenAILLMProvider(model={self._model!r})"
