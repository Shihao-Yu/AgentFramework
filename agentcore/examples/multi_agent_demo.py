"""
Multi-Agent Demo - Testing 2 domain agents with orchestration.

This demonstrates:
1. Running Purchasing and Payables agents in-process
2. Registering them with semantic discovery
3. Routing queries to the appropriate agent(s)
4. Handling cross-domain queries (parallel execution)

Run with: python -m examples.multi_agent_demo

No external services required - uses mock clients throughout.
"""

import asyncio
from typing import AsyncIterator

import numpy as np

from agentcore import (
    AgentInfo,
    RequestContext,
    EnrichedUser,
    Permission,
    Message,
    MessageRole,
)
from agentcore.registry.mock_client import MockRegistryClient
from agentcore.orchestrator import Orchestrator, RoutingStrategy
from agentcore.settings import OrchestratorSettings

from examples.purchasing_agent.agent import PurchasingAgent
from examples.payables_agent.agent import PayablesAgent


class MockEmbeddingClient:
    """Mock embedding client with deterministic similarity."""

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self._cache: dict[str, np.ndarray] = {}

    async def embed(self, text: str) -> np.ndarray:
        text_lower = text.lower()
        seed = hash(text_lower[:100]) % (2**32)
        
        if text not in self._cache:
            rng = np.random.RandomState(seed)
            embedding = rng.randn(self.dimension).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)
            self._cache[text] = embedding
        
        return self._cache[text]


class MockInferenceClient:
    """Mock inference client that returns canned responses based on tools."""

    async def complete(self, messages: list, tools: list = None, **kwargs):
        user_msg = next(
            (m.content for m in messages if hasattr(m, 'role') and m.role == MessageRole.USER),
            messages[-1].content if messages else ""
        )
        
        if tools:
            tool_call = self._select_tool(user_msg, tools)
            if tool_call:
                return MockResponse(tool_calls=[tool_call])
        
        return MockResponse(content=f"I processed your query: {user_msg[:50]}...")

    def _select_tool(self, query: str, tools: list) -> dict:
        query_lower = query.lower()
        
        tool_keywords = {
            "search_purchase_orders": ["po", "purchase order", "find po"],
            "get_spend_analysis": ["spend", "analysis", "spending"],
            "search_vendors": ["vendor", "supplier"],
            "search_invoices": ["invoice", "inv-"],
            "get_payment_status": ["payment status", "when will", "paid"],
            "get_ap_aging": ["aging", "ap aging", "accounts payable"],
            "get_vendor_payment_history": ["payment history", "payments to"],
        }
        
        for tool in tools:
            tool_name = tool["function"]["name"]
            keywords = tool_keywords.get(tool_name, [])
            
            if any(kw in query_lower for kw in keywords):
                return MockToolCall(
                    id=f"call_{tool_name}",
                    name=tool_name,
                    arguments=self._extract_args(query, tool),
                )
        
        return None

    def _extract_args(self, query: str, tool: dict) -> dict:
        args = {}
        
        if "po" in query.lower():
            import re
            po_match = re.search(r'po[- ]?(\d+)', query.lower())
            if po_match:
                args["po_number"] = f"PO-{po_match.group(1)}"
        
        if "inv" in query.lower():
            import re
            inv_match = re.search(r'inv[- ]?(\d+)', query.lower())
            if inv_match:
                args["invoice_number"] = f"INV-{inv_match.group(1)}"
        
        if "vendor" in query.lower() or "acme" in query.lower():
            args["vendor_name"] = "Acme Supplies"
        
        if "spend" in query.lower():
            args["group_by"] = "category"
            args["period"] = "Q1 2026"
        
        return args


class MockResponse:
    def __init__(self, content: str = None, tool_calls: list = None):
        self.content = content
        self.tool_calls = tool_calls

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    def to_message(self) -> Message:
        return Message(
            role=MessageRole.ASSISTANT,
            content=self.content,
            tool_calls=[
                {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}}
                for tc in (self.tool_calls or [])
            ] if self.tool_calls else None,
        )


class MockToolCall:
    def __init__(self, id: str, name: str, arguments: dict):
        self.id = id
        self.name = name
        self.arguments = arguments


class MultiAgentOrchestrator:
    """Orchestrator that routes queries to in-process agents."""

    def __init__(
        self,
        registry: MockRegistryClient,
        agents: dict,
    ):
        self._registry = registry
        self._agents = agents
        self._orchestrator = Orchestrator(
            registry=registry,
            settings=OrchestratorSettings(use_llm_routing=False),
        )

    async def handle_query(
        self,
        ctx: RequestContext,
        query: str,
    ) -> AsyncIterator[str]:
        """Route and handle a query."""
        discovered = await self._registry.discover(query, top_k=3)
        
        if not discovered:
            yield "No agents found to handle this query."
            return
        
        routing = await self._orchestrator._route(query, discovered)
        
        yield f"[Routing: {routing.strategy.value}]\n"
        yield f"[Agents: {routing.agents}]\n"
        yield f"[Reason: {routing.reasoning}]\n\n"
        
        if routing.strategy == RoutingStrategy.SINGLE:
            agent_id = routing.agents[0]
            agent = self._agents.get(agent_id)
            
            if agent:
                yield f"--- {agent.info.name} ---\n"
                async for chunk in agent.handle_query(ctx, query):
                    yield chunk
            else:
                yield f"Agent {agent_id} not available."
        
        elif routing.strategy == RoutingStrategy.PARALLEL:
            results = await self._execute_parallel(ctx, query, routing.agents)
            
            for agent_id, response in results.items():
                agent = self._agents.get(agent_id)
                name = agent.info.name if agent else agent_id
                yield f"\n--- {name} ---\n"
                yield response
                yield "\n"
        
        else:
            for agent_id in routing.agents:
                agent = self._agents.get(agent_id)
                
                if agent:
                    yield f"\n--- {agent.info.name} ---\n"
                    async for chunk in agent.handle_query(ctx, query):
                        yield chunk
                    yield "\n"

    async def _execute_parallel(
        self,
        ctx: RequestContext,
        query: str,
        agent_ids: list[str],
    ) -> dict[str, str]:
        """Execute query on multiple agents in parallel."""
        async def run_agent(agent_id: str) -> tuple[str, str]:
            agent = self._agents.get(agent_id)
            if not agent:
                return agent_id, f"Agent {agent_id} not available"
            
            response = ""
            async for chunk in agent.handle_query(ctx, query):
                response += chunk
            return agent_id, response
        
        tasks = [run_agent(aid) for aid in agent_ids]
        results = await asyncio.gather(*tasks)
        
        return dict(results)


async def main():
    print("=" * 70)
    print("Multi-Agent Demo - Purchasing + Payables Agents")
    print("=" * 70)
    
    embedding = MockEmbeddingClient()
    registry = MockRegistryClient(embedding, discovery_top_k=5)
    await registry.ensure_index()
    
    inference = MockInferenceClient()
    
    purchasing_agent = PurchasingAgent(inference)
    payables_agent = PayablesAgent(inference)
    
    await registry.register(purchasing_agent.info)
    await registry.register(payables_agent.info)
    
    print("\nRegistered agents:")
    print(f"  1. {purchasing_agent.info.name} - {purchasing_agent.info.domains}")
    print(f"  2. {payables_agent.info.name} - {payables_agent.info.domains}")
    
    agents = {
        "purchasing": purchasing_agent,
        "payables": payables_agent,
    }
    
    orchestrator = MultiAgentOrchestrator(registry, agents)
    
    user = EnrichedUser(
        user_id=1,
        username="demo_user",
        email="demo@example.com",
        display_name="Demo User",
        entity_id=1,
        entity_name="Demo Corp",
        permissions=frozenset([Permission.BUYER]),
    )
    ctx = RequestContext.create(
        user=user,
        session_id="demo-session",
        request_id="req-001",
    )
    
    test_queries = [
        ("Purchasing", "Find PO 12345"),
        ("Payables", "When will invoice INV-789 be paid?"),
        ("Purchasing", "What's my spend by category this quarter?"),
        ("Payables", "Show the AP aging report"),
        ("Cross-domain", "Compare my PO spending with invoice payments"),
    ]
    
    print("\n" + "=" * 70)
    print("Running Test Queries")
    print("=" * 70)
    
    for domain, query in test_queries:
        print(f"\n{'─' * 70}")
        print(f"[{domain}] Query: \"{query}\"")
        print("─" * 70)
        
        async for chunk in orchestrator.handle_query(ctx, query):
            print(chunk, end="")
        
        print()
    
    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print("\nTo run agents as separate servers:")
    print("  Terminal 1: uvicorn examples.purchasing_agent.main:app --port 8001")
    print("  Terminal 2: uvicorn examples.payables_agent.main:app --port 8002")


if __name__ == "__main__":
    asyncio.run(main())
