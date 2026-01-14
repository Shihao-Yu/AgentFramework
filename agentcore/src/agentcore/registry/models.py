"""Agent registry models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentInfo(BaseModel):
    """Agent registration info for discovery."""

    model_config = ConfigDict(frozen=False)

    agent_id: str
    name: str
    description: str
    version: str = "1.0.0"
    team: str = ""

    base_url: str
    health_endpoint: str = "/health"

    capabilities: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    example_queries: list[str] = Field(default_factory=list)

    is_healthy: bool = True
    registered_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None

    def to_embedding_text(self) -> str:
        """Generate text for embedding computation."""
        parts = [
            f"{self.name}: {self.description}",
            f"Capabilities: {', '.join(self.capabilities)}" if self.capabilities else "",
            f"Domains: {', '.join(self.domains)}" if self.domains else "",
            f"Examples: {'; '.join(self.example_queries[:3])}" if self.example_queries else "",
        ]
        return " ".join(p for p in parts if p)

    def to_routing_context(self) -> str:
        """Generate LLM-friendly description for routing."""
        return f"""Agent: {self.name} (id: {self.agent_id})
Description: {self.description}
Capabilities: {', '.join(self.capabilities)}
Examples: {'; '.join(self.example_queries[:3])}"""
