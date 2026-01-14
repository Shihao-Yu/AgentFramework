"""Orchestrator for multi-agent coordination."""

import asyncio
import json
import logging
import time
from typing import AsyncIterator, Optional

import httpx

from agentcore.orchestrator.models import (
    AgentInvocationResult,
    RoutingDecision,
    RoutingStrategy,
)
from agentcore.prompts import get_prompt_registry
from agentcore.registry.client import RegistryClient
from agentcore.registry.models import AgentInfo
from agentcore.settings.orchestrator import OrchestratorSettings

logger = logging.getLogger(__name__)


class InferenceClient:
    """Simple inference client interface."""

    async def complete(self, messages: list[dict]) -> str:
        """Complete a chat and return response content."""
        raise NotImplementedError


class Orchestrator:
    """
    Multi-agent orchestrator with semantic discovery.

    Flow:
    1. Discover agents (vector search)
    2. Route query (LLM or rule-based)
    3. Invoke agent(s)
    4. Synthesize if parallel
    """

    def __init__(
        self,
        registry: RegistryClient,
        inference: Optional[InferenceClient] = None,
        settings: Optional[OrchestratorSettings] = None,
    ):
        self._registry = registry
        self._inference = inference
        self._settings = settings or OrchestratorSettings()

    async def handle_request(
        self,
        query: str,
        session_id: str = "",
        token: str = "",
    ) -> AsyncIterator[dict]:
        """
        Handle a user query by routing to appropriate agents.

        Yields chat-contract style messages.
        """
        # 1. Discover relevant agents
        agents = await self._registry.discover(query, top_k=self._settings.discovery_top_k)
        logger.info(f"Discovered {len(agents)} agents for query: {query[:50]}...")

        # 2. Route
        routing = await self._route(query, agents)
        logger.info(f"Routing decision: {routing.strategy} -> {routing.agents}")

        # 3. Execute based on strategy
        if routing.strategy == RoutingStrategy.SINGLE:
            async for msg in self._invoke_single(query, routing, session_id, token):
                yield msg

        elif routing.strategy == RoutingStrategy.PARALLEL:
            results = await self._invoke_parallel(query, routing, session_id, token)
            # Yield combined results
            for agent_id, result in results.items():
                if result.success:
                    yield {
                        "type": "agent_response",
                        "agent_id": agent_id,
                        "content": result.response,
                    }
                else:
                    yield {
                        "type": "agent_error",
                        "agent_id": agent_id,
                        "error": result.error,
                    }

        elif routing.strategy == RoutingStrategy.SEQUENTIAL:
            async for msg in self._invoke_sequential(query, routing, session_id, token):
                yield msg

    async def _route(self, query: str, agents: list[AgentInfo]) -> RoutingDecision:
        """Decide how to route the query."""
        if not agents:
            return RoutingDecision(
                strategy=RoutingStrategy.SINGLE,
                agents=[self._settings.fallback_agent],
                reasoning="No relevant agents found, using fallback",
            )

        if len(agents) == 1:
            return RoutingDecision(
                strategy=RoutingStrategy.SINGLE,
                agents=[agents[0].agent_id],
                reasoning=f"Single match: {agents[0].name}",
            )

        if not self._settings.use_llm_routing or not self._inference:
            # Rule-based: use top agent
            return RoutingDecision(
                strategy=RoutingStrategy.SINGLE,
                agents=[agents[0].agent_id],
                reasoning="Rule-based: selected top agent by similarity",
            )

        # LLM-based routing
        return await self._llm_route(query, agents)

    async def _llm_route(self, query: str, agents: list[AgentInfo]) -> RoutingDecision:
        """Use LLM to decide routing strategy."""
        agent_descriptions = await self._registry.get_routing_context(agents)
        prompts = get_prompt_registry()
        router_prompt = prompts.get("orchestrator-router", agent_descriptions=agent_descriptions)

        messages = [
            {"role": "system", "content": router_prompt},
            {"role": "user", "content": f"Query: {query}"},
        ]

        try:
            response = await self._inference.complete(messages)
            decision = RoutingDecision.model_validate_json(response)
            return decision
        except Exception as e:
            logger.error(f"LLM routing failed: {e}, falling back to top agent")
            return RoutingDecision(
                strategy=RoutingStrategy.SINGLE,
                agents=[agents[0].agent_id],
                reasoning=f"LLM routing failed: {e}",
            )

    async def _invoke_single(
        self,
        query: str,
        routing: RoutingDecision,
        session_id: str,
        token: str,
    ) -> AsyncIterator[dict]:
        """Invoke a single agent and stream response."""
        agent_id = routing.agents[0]
        agent = await self._registry.get(agent_id)

        if not agent:
            yield {"type": "error", "message": f"Agent {agent_id} not found"}
            return

        async for msg in self._call_agent(agent, query, session_id, token):
            yield msg

    async def _invoke_parallel(
        self,
        query: str,
        routing: RoutingDecision,
        session_id: str,
        token: str,
    ) -> dict[str, AgentInvocationResult]:
        """Invoke multiple agents in parallel."""

        async def invoke_one(agent_id: str) -> AgentInvocationResult:
            agent = await self._registry.get(agent_id)
            if not agent:
                return AgentInvocationResult(
                    agent_id=agent_id,
                    success=False,
                    error="Agent not found",
                )

            start = time.time()
            try:
                response_parts = []
                async for msg in self._call_agent(agent, query, session_id, token):
                    if msg.get("type") == "assistant_message":
                        response_parts.append(msg.get("content", ""))

                return AgentInvocationResult(
                    agent_id=agent_id,
                    success=True,
                    response="".join(response_parts),
                    latency_ms=(time.time() - start) * 1000,
                )
            except Exception as e:
                return AgentInvocationResult(
                    agent_id=agent_id,
                    success=False,
                    error=str(e),
                    latency_ms=(time.time() - start) * 1000,
                )

        # Run in parallel
        max_agents = min(len(routing.agents), self._settings.max_parallel_agents)
        tasks = [invoke_one(aid) for aid in routing.agents[:max_agents]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            r.agent_id: r
            for r in results
            if isinstance(r, AgentInvocationResult)
        }

    async def _invoke_sequential(
        self,
        query: str,
        routing: RoutingDecision,
        session_id: str,
        token: str,
    ) -> AsyncIterator[dict]:
        """Invoke agents sequentially, passing context forward."""
        accumulated_context = ""

        for agent_id in routing.agents:
            agent = await self._registry.get(agent_id)
            if not agent:
                yield {"type": "error", "message": f"Agent {agent_id} not found"}
                continue

            # Augment query with context from previous agents
            augmented_query = query
            if accumulated_context:
                augmented_query = f"{query}\n\nContext from previous agents:\n{accumulated_context}"

            response_parts = []
            async for msg in self._call_agent(agent, augmented_query, session_id, token):
                yield msg
                if msg.get("type") == "assistant_message":
                    response_parts.append(msg.get("content", ""))

            accumulated_context += f"\n\n**{agent_id}**: {''.join(response_parts)}"

    async def _call_agent(
        self,
        agent: AgentInfo,
        query: str,
        session_id: str,
        token: str,
    ) -> AsyncIterator[dict]:
        """Call a single agent and stream response."""
        async with httpx.AsyncClient(timeout=self._settings.agent_timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{agent.base_url}/api/v1/query",
                    json={
                        "query": query,
                        "session_id": session_id,
                    },
                    headers={
                        "Authorization": f"Bearer {token}" if token else "",
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                yield data
                            except json.JSONDecodeError:
                                pass
            except httpx.HTTPError as e:
                yield {"type": "error", "message": f"Agent call failed: {e}"}
