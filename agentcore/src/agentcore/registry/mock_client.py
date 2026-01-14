"""Mock registry client for testing without Redis Stack."""

from datetime import datetime, timezone
from typing import Optional, Protocol

import numpy as np

from agentcore.registry.models import AgentInfo


class EmbeddingClient(Protocol):
    """Embedding client protocol."""

    async def embed(self, text: str) -> np.ndarray:
        ...


class MockRegistryClient:
    """In-memory agent registry for testing without Redis Stack."""

    def __init__(
        self,
        embedding: EmbeddingClient,
        discovery_top_k: int = 5,
    ):
        self._embedding = embedding
        self._discovery_top_k = discovery_top_k
        self._agents: dict[str, AgentInfo] = {}
        self._vectors: dict[str, np.ndarray] = {}

    async def ensure_index(self) -> None:
        pass

    async def register(self, agent: AgentInfo) -> None:
        now = datetime.now(timezone.utc)
        agent.registered_at = now
        agent.last_heartbeat = now

        # Compute embedding
        text = agent.to_embedding_text()
        embedding = await self._embedding.embed(text)

        # Store in memory
        self._agents[agent.agent_id] = agent
        self._vectors[agent.agent_id] = embedding

    async def unregister(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
        self._vectors.pop(agent_id, None)

    async def heartbeat(self, agent_id: str) -> None:
        if agent_id in self._agents:
            self._agents[agent_id].last_heartbeat = datetime.now(timezone.utc)

    async def get(self, agent_id: str) -> Optional[AgentInfo]:
        return self._agents.get(agent_id)

    async def discover(self, query: str, top_k: Optional[int] = None) -> list[AgentInfo]:
        if top_k is None:
            top_k = self._discovery_top_k

        if not self._agents:
            return []

        query_embedding = await self._embedding.embed(query)

        similarities: list[tuple[str, float]] = []
        for agent_id, vec in self._vectors.items():
            sim = np.dot(query_embedding, vec) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(vec)
            )
            similarities.append((agent_id, float(sim)))

        similarities.sort(key=lambda x: x[1], reverse=True)

        result = []
        for agent_id, _sim in similarities[:top_k]:
            agent = self._agents.get(agent_id)
            if agent and agent.is_healthy:
                result.append(agent)

        return result

    async def get_routing_context(self, agents: list[AgentInfo]) -> str:
        return "\n---\n".join(agent.to_routing_context() for agent in agents)

    async def list_all(self) -> list[AgentInfo]:
        return list(self._agents.values())
