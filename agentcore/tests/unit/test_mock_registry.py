"""Unit tests for MockRegistryClient."""

import pytest
import numpy as np

from agentcore.registry.models import AgentInfo
from agentcore.registry.mock_client import MockRegistryClient
from agentcore.embedding.client import MockEmbeddingClient


@pytest.fixture
def embedding_client():
    return MockEmbeddingClient(dimension=1536)


@pytest.fixture
def registry(embedding_client):
    return MockRegistryClient(embedding_client, discovery_top_k=5)


@pytest.fixture
def sample_agents():
    return [
        AgentInfo(
            agent_id="purchasing",
            name="Purchasing Agent",
            description="Handles purchase orders and vendors",
            base_url="http://localhost:8001",
            capabilities=["search", "create"],
            domains=["po", "vendor"],
        ),
        AgentInfo(
            agent_id="payables",
            name="Payables Agent",
            description="Handles invoices and payments",
            base_url="http://localhost:8002",
            capabilities=["process", "pay"],
            domains=["invoice", "payment"],
        ),
        AgentInfo(
            agent_id="hr",
            name="HR Agent",
            description="Handles employee information and time off",
            base_url="http://localhost:8003",
            capabilities=["search", "request"],
            domains=["employee", "timeoff"],
        ),
    ]


class TestMockRegistryClient:
    @pytest.mark.asyncio
    async def test_register_agent(self, registry, sample_agents):
        agent = sample_agents[0]
        await registry.register(agent)
        
        retrieved = await registry.get(agent.agent_id)
        
        assert retrieved is not None
        assert retrieved.agent_id == agent.agent_id
        assert retrieved.name == agent.name
        assert retrieved.registered_at is not None
        assert retrieved.last_heartbeat is not None

    @pytest.mark.asyncio
    async def test_unregister_agent(self, registry, sample_agents):
        agent = sample_agents[0]
        await registry.register(agent)
        
        await registry.unregister(agent.agent_id)
        
        retrieved = await registry.get(agent.agent_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_heartbeat_updates_timestamp(self, registry, sample_agents):
        agent = sample_agents[0]
        await registry.register(agent)
        
        initial = await registry.get(agent.agent_id)
        initial_heartbeat = initial.last_heartbeat
        
        await registry.heartbeat(agent.agent_id)
        
        updated = await registry.get(agent.agent_id)
        assert updated.last_heartbeat >= initial_heartbeat

    @pytest.mark.asyncio
    async def test_list_all(self, registry, sample_agents):
        for agent in sample_agents:
            await registry.register(agent)
        
        all_agents = await registry.list_all()
        
        assert len(all_agents) == 3
        agent_ids = {a.agent_id for a in all_agents}
        assert agent_ids == {"purchasing", "payables", "hr"}

    @pytest.mark.asyncio
    async def test_discover_returns_results(self, registry, sample_agents):
        for agent in sample_agents:
            await registry.register(agent)
        
        results = await registry.discover("purchase order", top_k=3)
        
        assert len(results) == 3
        assert all(isinstance(a, AgentInfo) for a in results)

    @pytest.mark.asyncio
    async def test_discover_respects_top_k(self, registry, sample_agents):
        for agent in sample_agents:
            await registry.register(agent)
        
        results = await registry.discover("any query", top_k=1)
        
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_discover_empty_registry(self, registry):
        results = await registry.discover("any query")
        
        assert results == []

    @pytest.mark.asyncio
    async def test_discover_excludes_unhealthy(self, registry, sample_agents):
        for agent in sample_agents:
            await registry.register(agent)
        
        purchasing = await registry.get("purchasing")
        purchasing.is_healthy = False
        
        results = await registry.discover("purchase order", top_k=3)
        
        agent_ids = {a.agent_id for a in results}
        assert "purchasing" not in agent_ids

    @pytest.mark.asyncio
    async def test_get_routing_context(self, registry, sample_agents):
        for agent in sample_agents:
            await registry.register(agent)
        
        agents = await registry.list_all()
        context = await registry.get_routing_context(agents)
        
        assert "Purchasing Agent" in context
        assert "Payables Agent" in context
        assert "HR Agent" in context

    @pytest.mark.asyncio
    async def test_ensure_index_is_noop(self, registry):
        await registry.ensure_index()

    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, registry):
        result = await registry.get("does_not_exist")
        assert result is None
