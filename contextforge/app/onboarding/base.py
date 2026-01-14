"""
Base class for onboarding pipelines.

Each pipeline uses LLM structured output to extract a specific type of
knowledge node from raw text.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Type

from pydantic import BaseModel

from app.clients.langfuse_client import get_langfuse_client

try:
    from infra.inference import InferenceClient, Message
except ImportError:
    from app.clients.inference_client import InferenceClient  # type: ignore
    from app.clients.inference_client import Message  # type: ignore


T = TypeVar("T", bound=BaseModel)


class OnboardingPipeline(ABC, Generic[T]):
    """
    Base class for type-specific onboarding pipelines.

    Each subclass handles extraction for a specific node type (FAQ, Playbook, etc.)
    using LLM structured output for reliable JSON parsing.
    """

    node_type: str
    extraction_model: Type[T]
    prompt_name: str

    def __init__(self, inference_client: InferenceClient):
        self.inference = inference_client
        self._langfuse = get_langfuse_client()

    def get_system_prompt(self) -> str:
        """
        Get the system prompt from Langfuse (with local fallback).
        """
        template = self._langfuse.get_prompt_template(self.prompt_name)
        if template:
            return template
        raise ValueError(f"Prompt '{self.prompt_name}' not found in Langfuse or local files")

    @abstractmethod
    def to_node_content(self, extraction: T) -> dict:
        pass

    @abstractmethod
    def get_title(self, extraction: T) -> str:
        pass

    @abstractmethod
    def get_tags(self, extraction: T) -> list[str]:
        pass

    def get_confidence(self, extraction: T) -> float:
        return getattr(extraction, "confidence", 0.7)

    async def extract(self, text: str) -> tuple[str, dict, list[str], float]:
        messages = [
            Message.system(self.get_system_prompt()),
            Message.user(f"Extract from the following text:\n\n{text}"),
        ]

        extraction = await self.inference.complete_structured(
            messages=messages,
            response_model=self.extraction_model,
        )

        return (
            self.get_title(extraction),
            self.to_node_content(extraction),
            self.get_tags(extraction),
            self.get_confidence(extraction),
        )
