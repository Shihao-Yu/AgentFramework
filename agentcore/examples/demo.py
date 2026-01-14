"""
Demo script showing AgentCore semantic discovery.

This demonstrates:
1. Registering agents with embeddings
2. Discovering agents via semantic search
3. Routing queries to appropriate agents

Run with: python -m examples.demo

This demo uses a MockRegistryClient (in-memory) that doesn't require Redis Stack.
For production use with Redis Stack, use RegistryClient instead.
"""

import asyncio
from datetime import datetime

import numpy as np

from agentcore.registry import AgentInfo, HeartbeatManager
from agentcore.registry.mock_client import MockRegistryClient
from agentcore.orchestrator import Orchestrator, RoutingStrategy
from agentcore.settings import OrchestratorSettings


class MockEmbeddingClient:
    """Mock embedding client that uses random vectors for demo."""

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        # Use fixed seeds for reproducible "similarity"
        self._cache: dict[str, np.ndarray] = {}

    async def embed(self, text: str) -> np.ndarray:
        """Generate a pseudo-embedding based on text content."""
        # Simple hash-based seeding for reproducibility
        seed = hash(text.lower()[:100]) % (2**32)
        if text not in self._cache:
            rng = np.random.RandomState(seed)
            embedding = rng.randn(self.dimension).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)  # Normalize
            self._cache[text] = embedding
        return self._cache[text]


# Sample agents for demo
DEMO_AGENTS = [
    AgentInfo(
        agent_id="purchasing",
        name="Purchasing Agent",
        description="""Purchasing domain expert that handles:
        - Purchase order creation, search, and management
        - Vendor lookup and management
        - Catalog item search
        - Spend analysis and reporting""",
        base_url="http://localhost:8001",
        capabilities=["search", "create", "update", "approve", "analyze"],
        domains=["purchase_order", "vendor", "catalog"],
        example_queries=[
            "Find PO 12345",
            "Create a purchase order for office supplies",
            "What's my spend on IT equipment this quarter?",
        ],
        version="1.0.0",
        team="Procurement",
    ),
    AgentInfo(
        agent_id="payables",
        name="Payables Agent",
        description="""Accounts payable expert that handles:
        - Invoice processing and matching
        - Payment scheduling and execution
        - Vendor payment inquiries
        - AP aging and reporting""",
        base_url="http://localhost:8002",
        capabilities=["search", "process", "pay", "report"],
        domains=["invoice", "payment", "vendor"],
        example_queries=[
            "Show unpaid invoices for vendor ACME",
            "When will invoice 789 be paid?",
            "Process payment batch for this week",
        ],
        version="1.0.0",
        team="Finance",
    ),
    AgentInfo(
        agent_id="hr",
        name="HR Agent",
        description="""Human resources expert that handles:
        - Employee information lookup
        - Time off requests
        - Benefits inquiries
        - Org chart navigation""",
        base_url="http://localhost:8003",
        capabilities=["search", "request", "report"],
        domains=["employee", "benefits", "timeoff"],
        example_queries=[
            "What's my PTO balance?",
            "Who reports to Jane Smith?",
            "Submit time off request for next Friday",
        ],
        version="1.0.0",
        team="HR",
    ),
    AgentInfo(
        agent_id="it_support",
        name="IT Support Agent",
        description="""IT helpdesk expert that handles:
        - Password resets and account issues
        - Software installation requests
        - Hardware troubleshooting
        - Network and VPN issues""",
        base_url="http://localhost:8004",
        capabilities=["troubleshoot", "reset", "install", "ticket"],
        domains=["password", "software", "hardware", "network"],
        example_queries=[
            "Reset my password",
            "Install Microsoft Office on my laptop",
            "VPN not connecting",
        ],
        version="1.0.0",
        team="IT",
    ),
]


async def demo_registration(registry: MockRegistryClient) -> None:
    """Demo: Register agents."""
    print("\n" + "=" * 60)
    print("DEMO: Agent Registration")
    print("=" * 60)

    # Ensure vector index exists (no-op for mock)
    await registry.ensure_index()
    print("Vector index created/verified (mock - in memory)")

    # Register agents
    for agent in DEMO_AGENTS:
        await registry.register(agent)
        print(f"  Registered: {agent.name} ({agent.agent_id})")

    # List all
    all_agents = await registry.list_all()
    print(f"\nTotal agents registered: {len(all_agents)}")


async def demo_discovery(registry: MockRegistryClient) -> None:
    """Demo: Discover agents via semantic search."""
    print("\n" + "=" * 60)
    print("DEMO: Semantic Agent Discovery")
    print("=" * 60)

    test_queries = [
        "I need to create a purchase order for office supplies",
        "When will my invoice be paid?",
        "What's my vacation balance?",
        "My password expired and I can't log in",
        "Compare spending between Q1 and Q2",  # Could match multiple
    ]

    for query in test_queries:
        print(f"\nQuery: \"{query}\"")
        agents = await registry.discover(query, top_k=3)
        print(f"  Found {len(agents)} relevant agents:")
        for i, agent in enumerate(agents, 1):
            print(f"    {i}. {agent.name} ({agent.agent_id})")


async def demo_routing(registry: MockRegistryClient) -> None:
    """Demo: Query routing decisions."""
    print("\n" + "=" * 60)
    print("DEMO: Query Routing (Rule-based)")
    print("=" * 60)

    settings = OrchestratorSettings(
        use_llm_routing=False,  # Use rule-based for demo
        fallback_agent="purchasing",
    )
    orchestrator = Orchestrator(registry=registry, settings=settings)

    test_queries = [
        "Find PO 12345",
        "Reset my password",
        "Show invoice aging report",
    ]

    for query in test_queries:
        print(f"\nQuery: \"{query}\"")
        agents = await registry.discover(query, top_k=3)
        routing = await orchestrator._route(query, agents)
        print(f"  Strategy: {routing.strategy.value}")
        print(f"  Agents: {routing.agents}")
        print(f"  Reasoning: {routing.reasoning}")


async def demo_heartbeat(registry: MockRegistryClient) -> None:
    """Demo: Heartbeat keeps agent alive."""
    print("\n" + "=" * 60)
    print("DEMO: Heartbeat Manager")
    print("=" * 60)

    # Start heartbeat for one agent
    heartbeat = HeartbeatManager(registry, "purchasing", interval=5)
    await heartbeat.start()
    print("Started heartbeat for 'purchasing' agent (5s interval)")

    # Wait a bit
    await asyncio.sleep(2)

    # Check agent is still there
    agent = await registry.get("purchasing")
    if agent:
        print(f"  Agent still registered, last heartbeat: {agent.last_heartbeat}")

    # Stop heartbeat
    await heartbeat.stop()
    print("Stopped heartbeat")


async def main():
    """Run all demos."""
    print("=" * 60)
    print("AgentCore Demo - Semantic Agent Discovery")
    print("=" * 60)
    print("\nUsing MockRegistryClient (in-memory, no Redis required)")

    # Create mock embedding client and registry
    embedding_client = MockEmbeddingClient()
    registry = MockRegistryClient(embedding_client, discovery_top_k=5)

    # Run demos
    await demo_registration(registry)
    await demo_discovery(registry)
    await demo_routing(registry)
    await demo_heartbeat(registry)

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
