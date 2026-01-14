"""
Multi-Agent Demo with FREE LLM Providers

This demo shows how to use AgentCore with free LLM providers:

INFERENCE OPTIONS (pick one):
1. Groq (free tier): https://console.groq.com - Fast, free tier available
2. Together.ai (free tier): https://api.together.xyz - $25 free credits
3. OpenRouter (free models): https://openrouter.ai - Some models are free
4. Ollama (local): http://localhost:11434 - Run models locally

EMBEDDING OPTIONS:
1. HuggingFace Transformers (local) - Completely free, runs locally
2. Ollama embeddings - Local embeddings with nomic-embed-text

SETUP:
    # Install sentence-transformers for local embeddings
    pip install sentence-transformers
    
    # Set your API key for inference (pick one provider)
    export GROQ_API_KEY=gsk_...
    # OR
    export TOGETHER_API_KEY=...
    # OR run Ollama locally

RUN:
    # With real LLM (set API key first)
    python -m examples.free_providers_demo
    
    # Mock mode (no network, no API keys needed)
    python -m examples.free_providers_demo --mock

"""

import argparse
import asyncio
import os
from typing import Optional

import numpy as np

from agentcore import (
    AgentInfo,
    RequestContext,
    EnrichedUser,
    Permission,
    Message,
    InferenceClient,
    MockEmbeddingClient,
)
from agentcore.registry.mock_client import MockRegistryClient
from agentcore.orchestrator import Orchestrator, RoutingStrategy
from agentcore.settings import InferenceSettings, OrchestratorSettings

from examples.purchasing_agent.agent import PurchasingAgent
from examples.payables_agent.agent import PayablesAgent


# Global flag for mock mode
MOCK_MODE = False


class MockInferenceClient:
    """Mock inference client that returns canned responses without LLM calls."""
    
    async def complete(self, messages, tools=None, config=None):
        """Return a mock response based on the query."""
        from agentcore.inference import InferenceResponse
        
        # Get user message
        user_msg = next((m.content for m in messages if m.role == "user"), "")
        
        # Return simple mock responses
        if "po" in user_msg.lower() or "purchase" in user_msg.lower():
            return InferenceResponse(
                content="[Mock Mode] I found PO-12345 for Acme Supplies ($5,234.00, Approved).",
                tool_calls=None,
            )
        elif "invoice" in user_msg.lower() or "ap" in user_msg.lower() or "aging" in user_msg.lower():
            return InferenceResponse(
                content="[Mock Mode] AP Aging Summary: Current: $45,000 | 1-30 days: $12,000 | 31-60 days: $5,000",
                tool_calls=None,
            )
        else:
            return InferenceResponse(
                content=f"[Mock Mode] I received your query: '{user_msg[:50]}...'",
                tool_calls=None,
            )
    
    async def stream(self, messages, tools=None, config=None):
        """Yield mock response chunks."""
        response = await self.complete(messages, tools, config)
        yield response.content
    
    async def close(self):
        """No-op for mock client."""
        pass


class LocalEmbeddingClient:
    """Local embedding client using HuggingFace sentence-transformers.
    
    Uses all-MiniLM-L6-v2 by default - small, fast, and free!
    First run downloads the model (~90MB), then it's cached locally.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._dimension = 384  # all-MiniLM-L6-v2 dimension

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                print(f"Loading embedding model: {self._model_name}...")
                self._model = SentenceTransformer(self._model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
                print(f"Model loaded! Dimension: {self._dimension}")
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. Run:\n"
                    "  pip install sentence-transformers"
                )

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> np.ndarray:
        self._load_model()
        embedding = self._model.encode(text, normalize_embeddings=True)
        return embedding.astype(np.float32)

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        self._load_model()
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return [e.astype(np.float32) for e in embeddings]

    async def close(self) -> None:
        pass


class OllamaEmbeddingClient:
    """Embedding client using Ollama's local embeddings.
    
    Requires Ollama running locally with nomic-embed-text model:
        ollama pull nomic-embed-text
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
    ):
        self._base_url = base_url
        self._model = model
        self._dimension = 768
        self._client = None

    @property
    def dimension(self) -> int:
        return self._dimension

    async def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=60.0,
            )
        return self._client

    async def embed(self, text: str) -> np.ndarray:
        client = await self._get_client()
        response = await client.post(
            "/api/embeddings",
            json={"model": self._model, "prompt": text},
        )
        response.raise_for_status()
        data = response.json()
        embedding = np.array(data["embedding"], dtype=np.float32)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        return [await self.embed(text) for text in texts]

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()


def get_inference_settings() -> Optional[InferenceSettings]:
    """Auto-detect which free provider to use based on env vars.
    
    Returns None if MOCK_MODE is enabled.
    """
    
    if MOCK_MODE:
        print("Using mock inference (no LLM calls)")
        return None
    
    if api_key := os.getenv("GROQ_API_KEY"):
        print("Using Groq (free tier)")
        return InferenceSettings(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
            default_model="llama-3.1-8b-instant",  # Fast and free
        )
    
    if api_key := os.getenv("TOGETHER_API_KEY"):
        print("Using Together.ai")
        return InferenceSettings(
            base_url="https://api.together.xyz/v1",
            api_key=api_key,
            default_model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
        )
    
    if api_key := os.getenv("OPENROUTER_API_KEY"):
        print("Using OpenRouter")
        return InferenceSettings(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_model="meta-llama/llama-3.1-8b-instruct:free",
        )
    
    print("Using Ollama (local) - make sure Ollama is running!")
    return InferenceSettings(
        base_url="http://localhost:11434/v1",
        api_key="ollama",  # Ollama doesn't need a real key
        default_model="llama3.2",
    )


def get_embedding_client():
    """Get embedding client - prefers local HuggingFace, falls back to mock."""
    
    if MOCK_MODE:
        print("Using MockEmbeddingClient (mock mode)")
        return MockEmbeddingClient(dimension=384)
    
    try:
        import sentence_transformers
        print("Using local HuggingFace embeddings (free!)")
        return LocalEmbeddingClient()
    except ImportError:
        pass
    
    # Check if Ollama is likely running (try to avoid connection errors)
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.5)
        result = sock.connect_ex(('localhost', 11434))
        if result == 0:
            print("Using Ollama embeddings (requires: ollama pull nomic-embed-text)")
            return OllamaEmbeddingClient()
    except Exception:
        pass
    finally:
        sock.close()
    
    # Fallback to mock if nothing else works
    print("No embedding provider found. Using MockEmbeddingClient (hash-based, not semantic).")
    print("  For better results, install sentence-transformers: pip install sentence-transformers")
    return MockEmbeddingClient(dimension=384)


async def run_demo():
    print("=" * 70)
    print("Multi-Agent Demo with FREE Providers")
    if MOCK_MODE:
        print("(MOCK MODE - no network calls)")
    print("=" * 70)
    
    embedding_client = get_embedding_client()
    
    registry = MockRegistryClient(embedding_client, discovery_top_k=5)
    await registry.ensure_index()
    
    inference_settings = get_inference_settings()
    if MOCK_MODE:
        inference_client = MockInferenceClient()
    else:
        inference_client = InferenceClient(inference_settings)
    
    purchasing_agent = PurchasingAgent(inference_client)
    payables_agent = PayablesAgent(inference_client)
    
    await registry.register(purchasing_agent.info)
    await registry.register(payables_agent.info)
    
    print("\nRegistered agents:")
    print(f"  1. {purchasing_agent.info.name}")
    print(f"  2. {payables_agent.info.name}")
    
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
    
    print("\n" + "=" * 70)
    print("Testing Agent Discovery (Semantic Search)")
    print("=" * 70)
    
    test_queries = [
        "Find purchase order 12345",
        "When will my invoice be paid?",
        "Show me the AP aging report",
        "What vendors do we have for office supplies?",
    ]
    
    for query in test_queries:
        print(f"\nQuery: \"{query}\"")
        agents = await registry.discover(query, top_k=2)
        print(f"  Discovered: {[a.agent_id for a in agents]}")
    
    # Skip LLM tests in mock mode
    if MOCK_MODE:
        print("\n" + "=" * 70)
        print("Skipping LLM queries (mock mode)")
        print("=" * 70)
        print("\nTo test with real LLM, set an API key:")
        print("  export GROQ_API_KEY=gsk_...  # Get from https://console.groq.com")
        print("  python -m examples.free_providers_demo")
    else:
        print("\n" + "=" * 70)
        print("Testing Agent Queries (with real LLM)")
        print("=" * 70)
        
        print("\n--- Testing Purchasing Agent ---")
        print("Query: 'Find PO 12345'")
        try:
            async for chunk in purchasing_agent.handle_query(ctx, "Find PO 12345"):
                print(chunk, end="")
            print()
        except Exception as e:
            print(f"Error: {e}")
            print("(Make sure your LLM provider is configured correctly)")
        
        print("\n--- Testing Payables Agent ---")
        print("Query: 'What is the AP aging summary?'")
        try:
            async for chunk in payables_agent.handle_query(ctx, "What is the AP aging summary?"):
                print(chunk, end="")
            print()
        except Exception as e:
            print(f"Error: {e}")
    
    if inference_client:
        await inference_client.close()
    await embedding_client.close()
    
    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)


def main():
    global MOCK_MODE
    
    parser = argparse.ArgumentParser(description="AgentCore Multi-Agent Demo")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode (no network calls, no API keys needed)",
    )
    args = parser.parse_args()
    
    MOCK_MODE = args.mock
    
    if not MOCK_MODE:
        print("""
FREE PROVIDER SETUP:

Option 1 - Groq (Recommended, very fast):
  1. Sign up at https://console.groq.com
  2. Create API key
  3. export GROQ_API_KEY=gsk_...

Option 2 - Together.ai ($25 free credits):
  1. Sign up at https://api.together.xyz
  2. Create API key
  3. export TOGETHER_API_KEY=...

Option 3 - Ollama (100% local, no API key):
  1. Install Ollama: https://ollama.ai
  2. ollama pull llama3.2
  3. ollama pull nomic-embed-text (for embeddings)

For embeddings (recommended - completely free):
  pip install sentence-transformers

TIP: Run with --mock for offline demo (no API keys needed)
""")
    
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
