"""Unit tests for registry models."""

import pytest
from datetime import datetime, timezone

from agentcore.registry.models import AgentInfo


class TestAgentInfo:
    def test_create_minimal(self):
        agent = AgentInfo(
            agent_id="test",
            name="Test Agent",
            description="A test agent",
            base_url="http://localhost:8000",
        )
        
        assert agent.agent_id == "test"
        assert agent.name == "Test Agent"
        assert agent.is_healthy is True
        assert agent.capabilities == []
        assert agent.domains == []

    def test_create_full(self):
        agent = AgentInfo(
            agent_id="purchasing",
            name="Purchasing Agent",
            description="Handles purchase orders",
            base_url="http://localhost:8001",
            capabilities=["search", "create"],
            domains=["po", "vendor"],
            example_queries=["Find PO 123"],
            version="2.0.0",
            team="Procurement",
            is_healthy=True,
        )
        
        assert agent.agent_id == "purchasing"
        assert agent.capabilities == ["search", "create"]
        assert agent.domains == ["po", "vendor"]
        assert agent.version == "2.0.0"

    def test_to_embedding_text(self):
        agent = AgentInfo(
            agent_id="test",
            name="Test Agent",
            description="Does testing things",
            base_url="http://localhost:8000",
            capabilities=["test", "verify"],
            domains=["testing"],
            example_queries=["Run tests", "Verify results"],
        )
        
        text = agent.to_embedding_text()
        
        assert "Test Agent" in text
        assert "Does testing things" in text
        assert "test" in text
        assert "verify" in text
        assert "testing" in text
        assert "Run tests" in text

    def test_to_routing_context(self):
        agent = AgentInfo(
            agent_id="purchasing",
            name="Purchasing Agent",
            description="Handles purchase orders",
            base_url="http://localhost:8001",
            capabilities=["search", "create"],
            example_queries=["Find PO 123", "Create PO"],
        )
        
        context = agent.to_routing_context()
        
        assert "Purchasing Agent" in context
        assert "purchasing" in context
        assert "Handles purchase orders" in context
        assert "search" in context
        assert "Find PO 123" in context

    def test_serialization_roundtrip(self):
        agent = AgentInfo(
            agent_id="test",
            name="Test Agent",
            description="A test agent",
            base_url="http://localhost:8000",
            capabilities=["a", "b"],
            domains=["x", "y"],
            registered_at=datetime(2026, 1, 14, 12, 0, 0),
        )
        
        json_str = agent.model_dump_json()
        restored = AgentInfo.model_validate_json(json_str)
        
        assert restored.agent_id == agent.agent_id
        assert restored.name == agent.name
        assert restored.capabilities == agent.capabilities
        assert restored.registered_at == agent.registered_at

    def test_health_endpoint_default(self):
        agent = AgentInfo(
            agent_id="test",
            name="Test",
            description="Test",
            base_url="http://localhost:8000",
        )
        
        assert agent.health_endpoint == "/health"

    def test_mutable_timestamps(self):
        agent = AgentInfo(
            agent_id="test",
            name="Test",
            description="Test",
            base_url="http://localhost:8000",
        )
        
        now = datetime.now(timezone.utc)
        agent.registered_at = now
        agent.last_heartbeat = now
        
        assert agent.registered_at == now
        assert agent.last_heartbeat == now
