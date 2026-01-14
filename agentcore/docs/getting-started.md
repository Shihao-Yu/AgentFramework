# Getting Started with AgentCore

## Prerequisites

- Python 3.11+
- Redis Stack (optional - not needed for development)

## Installation

```bash
cd agentcore
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Quick Demo

```bash
# Mock mode - no API keys needed
python -m examples.free_providers_demo --mock

# Or with free LLM (Groq)
export GROQ_API_KEY=gsk_...
python -m examples.free_providers_demo
```

## Core Concepts

### 1. Agent Registration

```python
from agentcore import AgentInfo, MockRegistryClient, MockEmbeddingClient

embedding = MockEmbeddingClient()
registry = MockRegistryClient(embedding=embedding)

agent = AgentInfo(
    agent_id="purchasing",
    name="Purchasing Agent",
    description="Handles purchase orders, vendors, and spend analysis",
    base_url="http://localhost:8001",
    capabilities=["search", "create", "approve"],
    domains=["purchase_order", "vendor"],
    example_queries=["Find PO 12345", "Create purchase order"],
)

await registry.register(agent)
```

### 2. Semantic Discovery

```python
agents = await registry.discover("I need to create a purchase order", top_k=5)
# Returns agents sorted by relevance
```

### 3. User Context

```python
from agentcore import EnrichedUser, RequestContext, Permission

user = EnrichedUser(
    user_id=123,
    username="jdoe",
    email="jdoe@example.com",
    display_name="John Doe",
    entity_id=1,
    entity_name="Acme Inc",
    permissions=frozenset([Permission.BUYER, Permission.PO_CREATE]),
)

ctx = RequestContext.create(user=user, session_id="session-123")

# Access anywhere via contextvars
current = RequestContext.current()
```

### 4. Inference Client

```python
from agentcore import InferenceClient, Message, MessageRole
from agentcore.settings.inference import InferenceSettings

client = InferenceClient(InferenceSettings())

response = await client.complete([
    Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
    Message(role=MessageRole.USER, content="Hello"),
])
print(response.content)
```

### 5. Prompt Management

Prompts are managed via Langfuse with local fallbacks:

```python
from agentcore.prompts import get_prompt_registry

prompts = get_prompt_registry()
router_prompt = prompts.get(
    "orchestrator-router",
    agent_descriptions="- purchasing: Handles POs",
)
```

## Environment Variables

```bash
# Inference (OpenAI-compatible)
INFERENCE_BASE_URL=https://api.openai.com/v1
INFERENCE_API_KEY=sk-...
INFERENCE_DEFAULT_MODEL=gpt-4

# Embedding
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-...

# Langfuse (optional - for prompt management and tracing)
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
```

## Run Tests

```bash
pytest tests/unit -v
# 311 tests passing
```

## Next Steps

- [Architecture](./architecture.md) - How AgentCore works
- [Creating Agents](./creating-agents.md) - Build your own agent
- [API Reference](./api-reference.md) - Complete API docs
