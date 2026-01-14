# AgentCore

Enterprise agent framework with semantic discovery for multi-agent coordination at scale.

## Overview

AgentCore enables coordination of 50+ AI agents using **semantic search** for discovery instead of hardcoded routing. Each agent registers with an embedding of its capabilities; queries are matched via vector similarity.

### Key Features

- **Semantic Discovery** - Find relevant agents via vector similarity (not keyword matching)
- **Dynamic Registration** - Agents self-register with embeddings, heartbeat to stay alive
- **Smart Routing** - LLM or rule-based routing to single/parallel/sequential agents
- **First-class Auth** - User context (`EnrichedUser`, `RequestContext`) flows through everything
- **OpenAI-compatible** - Inference and embedding clients work with any OpenAI-compatible API

## Installation

### Prerequisites

- Python 3.11+
- Redis Stack (for production vector search) - optional for development

### Setup

```bash
cd agentcore
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Run Tests

```bash
python -m pytest tests/unit -v
# Result: 311 passed
```

### Run Demo (No Redis Required)

```bash
python -m examples.demo
```

## Quick Start

### Register an Agent

```python
from agentcore import AgentInfo, MockRegistryClient, MockEmbeddingClient

# Create registry (use RegistryClient for production with Redis Stack)
embedding = MockEmbeddingClient()
registry = MockRegistryClient(embedding=embedding)

# Register agent
agent = AgentInfo(
    agent_id="purchasing",
    name="Purchasing Agent",
    description="Handles purchase orders, vendors, catalogs...",
    base_url="http://localhost:8001",
    capabilities=["search", "create", "approve"],
    domains=["purchase_order", "vendor"],
    example_queries=["Find PO 12345", "Create purchase order"],
    version="1.0.0",
    team="Procurement",
)
await registry.register(agent)
```

### Discover Agents

```python
# Find agents relevant to a query (vector similarity search)
agents = await registry.discover("I need to create a purchase order", top_k=5)
# Returns: [AgentInfo(agent_id="purchasing", score=0.92), ...]
```

### Route Queries with Orchestrator

```python
from agentcore import Orchestrator, OrchestratorSettings

orchestrator = Orchestrator(
    registry=registry,
    inference=inference_client,
    settings=OrchestratorSettings(),
)

# Discovers relevant agents and routes automatically
routing = await orchestrator.route(query="Compare PO with invoice")
# Returns: RoutingDecision(strategy=PARALLEL, agents=["purchasing", "payables"])
```

### User Context (First-Class)

```python
from agentcore import EnrichedUser, RequestContext, Permission

# Create user context
user = EnrichedUser(
    user_id=123,
    username="jdoe",
    email="jdoe@example.com",
    permissions=frozenset([Permission.BUYER, Permission.PO_CREATE]),
)

# Create request context (stored in contextvars)
ctx = RequestContext.create(
    user=user,
    session_id="session-123",
    request_id="req-456",
)

# Access anywhere via contextvars
current = RequestContext.current()  # Returns ctx or None
required = RequestContext.require_current()  # Returns ctx or raises
```

## Architecture

```
Query: "Find PO 12345"
        │
        ▼
┌─────────────────────────────────┐
│         Orchestrator            │
│                                 │
│  1. Embed query                 │
│  2. Vector search (Redis Stack) │
│  3. LLM routes to agent(s)      │
│  4. Invoke & stream response    │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│      Agent Registry (Redis)     │
│                                 │
│  purchasing: [0.12, 0.34, ...]  │──┐
│  payables:   [0.56, 0.78, ...]  │  │ Vector similarity
│  hr:         [0.90, 0.11, ...]  │  │ search finds
│  ...50+ agents...               │  │ top matches
└─────────────────────────────────┘  │
        │                            │
        ▼                            │
   Purchasing Agent  ◄───────────────┘
```

## Project Structure

```
agentcore/
├── pyproject.toml
├── README.md
├── src/agentcore/
│   ├── __init__.py                 # Main exports
│   │
│   ├── settings/                   # Pydantic Settings (all config)
│   │   ├── base.py                 # BaseAppSettings
│   │   ├── registry.py             # RegistrySettings
│   │   ├── orchestrator.py         # OrchestratorSettings
│   │   ├── embedding.py            # EmbeddingSettings
│   │   └── inference.py            # InferenceSettings
│   │
│   ├── prompts/                    # Prompt Management (Langfuse + fallbacks)
│   │   ├── fallbacks.py            # Hardcoded fallback prompts
│   │   └── registry.py             # PromptRegistry (Langfuse-first)
│   │
│   ├── registry/                   # Agent Registration & Discovery
│   │   ├── models.py               # AgentInfo
│   │   ├── client.py               # RegistryClient (Redis Stack)
│   │   ├── mock_client.py          # MockRegistryClient (in-memory)
│   │   └── heartbeat.py            # HeartbeatManager
│   │
│   ├── orchestrator/               # Query Routing
│   │   ├── models.py               # RoutingStrategy, RoutingDecision
│   │   └── orchestrator.py         # Orchestrator
│   │
│   ├── embedding/                  # Embedding Service
│   │   ├── protocol.py             # EmbeddingProtocol
│   │   └── client.py               # EmbeddingClient, MockEmbeddingClient
│   │
│   ├── inference/                  # LLM Inference
│   │   ├── models.py               # Message, ToolCall, InferenceConfig, etc.
│   │   └── client.py               # InferenceClient (OpenAI-compatible)
│   │
│   ├── auth/                       # User Context (First-Class)
│   │   ├── models.py               # Permission, EnrichedUser, Locale, etc.
│   │   └── context.py              # RequestContext (contextvars)
│   │
│   └── common/                     # Shared Utilities
│       └── __init__.py
│
├── examples/
│   ├── demo.py                     # Demo with 4 sample agents
│   └── purchasing_agent/
│       ├── agent.py                # PurchasingAgent with 3 tools
│       └── main.py                 # FastAPI server
│
└── tests/
    └── unit/
        ├── test_auth.py            # 21 tests
        ├── test_prompts.py         # 20 tests
        ├── test_mock_registry.py   # 11 tests
        └── test_registry_models.py # 7 tests
```

## Configuration

All configuration via environment variables with Pydantic Settings:

```bash
# Registry (Redis Stack)
REGISTRY_REDIS_URL=redis://localhost:6379/0
REGISTRY_KEY_PREFIX=agentcore:agents
REGISTRY_HEARTBEAT_INTERVAL_SECONDS=10
REGISTRY_AGENT_TTL_SECONDS=30
REGISTRY_EMBEDDING_DIMENSION=1536

# Orchestrator
ORCHESTRATOR_DISCOVERY_TOP_K=5
ORCHESTRATOR_USE_LLM_ROUTING=true
ORCHESTRATOR_ROUTING_MODEL=gpt-4
ORCHESTRATOR_FALLBACK_AGENT=default

# Embedding (OpenAI-compatible)
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-ada-002

# Inference (OpenAI-compatible)
INFERENCE_BASE_URL=https://api.openai.com/v1
INFERENCE_API_KEY=sk-...
INFERENCE_DEFAULT_MODEL=gpt-4
INFERENCE_MAX_TOKENS=4096
INFERENCE_TEMPERATURE=0.7
```

## Implemented Modules

| Module | Status | Description |
|--------|--------|-------------|
| **Settings** | ✅ Complete | Pydantic Settings for all config |
| **Prompts** | ✅ Complete | Langfuse prompt management with fallbacks |
| **Registry** | ✅ Complete | Agent registration with vector search |
| **Orchestrator** | ✅ Complete | Query routing (single/parallel/sequential) |
| **Embedding** | ✅ Complete | OpenAI-compatible embedding client |
| **Inference** | ✅ Complete | OpenAI-compatible LLM client with streaming |
| **Auth** | ✅ Complete | EnrichedUser, RequestContext, Permissions |

## Planned Modules

| Module | Priority | Description |
|--------|----------|-------------|
| **Tracing** | High | Langfuse integration for observability |
| **Knowledge** | High | ContextForge integration for RAG |
| **Core Agent** | High | BaseAgent with ReAct loop |
| **Sub-Agents** | Medium | Planner, Researcher, Analyzer, Executor, Synthesizer |
| **Tools** | Medium | @tool decorator, ToolRegistry |
| **Session** | Medium | PostgreSQL persistence |
| **Transport** | Medium | WebSocket server |

## Example: Purchasing Agent

```bash
# Run the example agent (needs INFERENCE_API_KEY for real LLM calls)
cd agentcore
source .venv/bin/activate
uvicorn examples.purchasing_agent.main:app --port 8001

# Endpoints:
# GET  /health              - Health check
# GET  /capabilities        - Agent registration info
# POST /api/v1/query        - Handle queries
```

See `examples/purchasing_agent/` for a complete FastAPI agent implementation.

## Design Document

For detailed architecture, specifications, and implementation tasks, see:
[docs/agentcore_design.md](../docs/agentcore_design.md)

## License

Internal use only.
