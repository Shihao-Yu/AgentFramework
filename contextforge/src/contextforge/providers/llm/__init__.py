"""LLM providers."""

from contextforge.providers.llm.mock import MockLLMProvider

def __getattr__(name):
    if name == "OpenAILLMProvider":
        from contextforge.providers.llm.openai import OpenAILLMProvider
        return OpenAILLMProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "MockLLMProvider",
    "OpenAILLMProvider",
]
