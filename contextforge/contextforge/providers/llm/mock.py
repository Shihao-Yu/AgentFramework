"""
Mock LLM Provider

For testing and development without external dependencies.
"""

import json


class MockLLMProvider:
    """
    Mock LLM provider for testing.
    
    Returns canned responses for testing without external LLM service.
    
    Example:
        provider = MockLLMProvider()
        response = await provider.generate("What is 2+2?")
        # Returns: "This is a mock response."
    """
    
    def __init__(self, default_response: str = "This is a mock response."):
        self.default_response = default_response
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """Return mock response."""
        return self.default_response
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> dict:
        """Return mock JSON response."""
        return {"mock": True, "prompt_length": len(prompt)}
