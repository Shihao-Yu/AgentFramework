"""Registry client for agent registration and discovery."""

import json
import struct
from datetime import datetime
from typing import Optional

import numpy as np
from redis.asyncio import Redis
from redis.commands.search.field import TagField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redis.exceptions import ResponseError

from agentcore.registry.models import AgentInfo
from agentcore.settings.registry import RegistrySettings


class EmbeddingClient:
    """Simple embedding client interface."""

    async def embed(self, text: str) -> np.ndarray:
        """Embed text and return vector."""
        raise NotImplementedError


class RegistryClient:
    """Agent registration and discovery via Redis Stack."""

    def __init__(
        self,
        redis: Redis,
        embedding: EmbeddingClient,
        settings: Optional[RegistrySettings] = None,
    ):
        self._redis = redis
        self._embedding = embedding
        self._settings = settings or RegistrySettings()
        self._prefix = self._settings.key_prefix

    @property
    def index_name(self) -> str:
        return f"{self._prefix}:idx"

    async def ensure_index(self) -> None:
        """Create vector index if it doesn't exist."""
        try:
            await self._redis.ft(self.index_name).info()
        except ResponseError:
            # Index doesn't exist, create it
            schema = [
                TagField("agent_id"),
                VectorField(
                    "embedding",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self._settings.embedding_dimension,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
            ]
            await self._redis.ft(self.index_name).create_index(
                schema,
                definition=IndexDefinition(
                    prefix=[f"{self._prefix}:vec:"],
                    index_type=IndexType.HASH,
                ),
            )

    async def register(self, agent: AgentInfo) -> None:
        """Register agent with embedding for discovery."""
        now = datetime.utcnow()
        agent.registered_at = now
        agent.last_heartbeat = now

        # Compute embedding
        text = agent.to_embedding_text()
        embedding = await self._embedding.embed(text)

        # Store agent info as JSON
        agent_key = f"{self._prefix}:{agent.agent_id}"
        await self._redis.set(agent_key, agent.model_dump_json())
        await self._redis.expire(agent_key, self._settings.agent_ttl_seconds)

        # Store vector for search
        vec_key = f"{self._prefix}:vec:{agent.agent_id}"
        embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding.tolist())
        await self._redis.hset(
            vec_key,
            mapping={
                "agent_id": agent.agent_id,
                "embedding": embedding_bytes,
            },
        )

    async def unregister(self, agent_id: str) -> None:
        """Remove agent from registry."""
        await self._redis.delete(f"{self._prefix}:{agent_id}")
        await self._redis.delete(f"{self._prefix}:vec:{agent_id}")

    async def heartbeat(self, agent_id: str) -> None:
        """Refresh TTL and update last heartbeat."""
        agent_key = f"{self._prefix}:{agent_id}"

        # Refresh TTL
        await self._redis.expire(agent_key, self._settings.agent_ttl_seconds)

        # Update last_heartbeat in stored data
        data = await self._redis.get(agent_key)
        if data:
            agent = AgentInfo.model_validate_json(data)
            agent.last_heartbeat = datetime.utcnow()
            await self._redis.set(agent_key, agent.model_dump_json())
            await self._redis.expire(agent_key, self._settings.agent_ttl_seconds)

    async def get(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent by ID."""
        data = await self._redis.get(f"{self._prefix}:{agent_id}")
        if data:
            return AgentInfo.model_validate_json(data)
        return None

    async def discover(self, query: str, top_k: Optional[int] = None) -> list[AgentInfo]:
        """Find relevant agents via vector search."""
        if top_k is None:
            top_k = self._settings.discovery_top_k

        # Embed query
        query_embedding = await self._embedding.embed(query)
        query_bytes = struct.pack(f"{len(query_embedding)}f", *query_embedding.tolist())

        # Vector search
        try:
            search_query = (
                Query(f"*=>[KNN {top_k} @embedding $vec AS score]")
                .return_fields("agent_id", "score")
                .sort_by("score")
                .dialect(2)
            )
            results = await self._redis.ft(self.index_name).search(
                search_query,
                query_params={"vec": query_bytes},
            )
        except ResponseError:
            # Index might not exist or be empty
            return []

        # Fetch agent info for each result
        agents = []
        for doc in results.docs:
            agent = await self.get(doc.agent_id)
            if agent and agent.is_healthy:
                agents.append(agent)

        return agents

    async def get_routing_context(self, agents: list[AgentInfo]) -> str:
        """Generate LLM-friendly agent descriptions for routing."""
        return "\n---\n".join(agent.to_routing_context() for agent in agents)

    async def list_all(self) -> list[AgentInfo]:
        """List all registered agents (use sparingly)."""
        pattern = f"{self._prefix}:*"
        agents = []

        async for key in self._redis.scan_iter(match=pattern):
            key_str = key.decode() if isinstance(key, bytes) else key
            # Skip vector keys
            if ":vec:" in key_str:
                continue
            data = await self._redis.get(key)
            if data:
                try:
                    agent = AgentInfo.model_validate_json(data)
                    agents.append(agent)
                except Exception:
                    pass  # Skip invalid entries

        return agents
