# AgentCore Design Document

**Version**: 2.0  
**Date**: January 13, 2026  
**Status**: Approved for Implementation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Agent Discovery](#agent-discovery)
4. [Package Structure](#package-structure)
5. [Core Design Decisions](#core-design-decisions)
6. [Component Specifications](#component-specifications)
7. [Multi-Agent Coordination](#multi-agent-coordination)
8. [Data Models](#data-models)
9. [Configuration](#configuration)
10. [Implementation Tasks](#implementation-tasks)
11. [API Contracts](#api-contracts)

---

## Executive Summary

AgentCore is an enterprise agent framework that enables domain teams to build, deploy, and coordinate AI agents independently. The framework supports **10+ domain agents** with **sub-domain agents**, scaling to **50+ agents** in a unified network.

### Core Innovation: Semantic Agent Discovery

The key challenge with 50+ agents is routing: how does the orchestrator know which agent(s) should handle a query without evaluating all of them?

**Solution:** Each agent registers with an embedding of its description and capabilities. When a query arrives:
1. Embed the query
2. Vector search finds the top 5 most relevant agents
3. LLM router decides which of these 5 to invoke

Simple, fast, scales to hundreds of agents.

### Key Features

- **Semantic discovery** - Vector search finds relevant agents (not keyword matching)
- **Functional sub-agents** (Planner, Researcher, Analyzer, Executor, Synthesizer) for task decomposition
- **Native ContextForge integration** for knowledge retrieval
- **First-class Langfuse tracing** for observability across agent networks
- **Redis-based registry** with vector search (Redis Stack)
- **Pydantic-first configuration** (no hardcoding)

### Key Principles

1. **User context is first-class** - Token, permissions, enriched user info flows through everything
2. **No hardcoding** - All configuration via Pydantic Settings
3. **DRY patterns** - Shared base classes, protocols, generics
4. **Native ContextForge** - Deep integration, not just a tool
5. **Langfuse everywhere** - Trace all decisions, inference calls, tool executions
6. **Semantic discovery** - Vector search finds relevant agents, not hardcoded routing

---

## Architecture Overview

### High-Level Architecture

When a query arrives, the orchestrator:
1. **Embeds** the query
2. **Vector search** finds the top 5 most similar agents
3. **LLM router** decides which of these to invoke

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              USER REQUEST                                       │
│                           "Compare PO and Invoice"                              │
│                                   │                                             │
│                                   ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         ORCHESTRATOR                                     │   │
│  │                                                                          │   │
│  │  1. Embed Query                                                          │   │
│  │            │                                                             │   │
│  │            ▼                                                             │   │
│  │  2. Vector Search (Redis Stack)                                          │   │
│  │     ┌─────────────────────────────────────────────────────────────────┐  │   │
│  │     │  Agent Registry (50+ agents, each with embedding)               │  │   │
│  │     │                                                                 │  │   │
│  │     │  purchasing: "Handles POs, vendors, catalogs..." → [0.12, ...]  │  │   │
│  │     │  payables:   "Handles invoices, payments..."     → [0.34, ...]  │  │   │
│  │     │  asset:      "Handles fixed assets, deprec..."   → [0.56, ...]  │  │   │
│  │     │  hr:         "Handles employees, payroll..."     → [0.78, ...]  │  │   │
│  │     │  ...                                                            │  │   │
│  │     └─────────────────────────────────────────────────────────────────┘  │   │
│  │            │                                                             │   │
│  │            ▼                                                             │   │
│  │  3. Top 5 Results: [Purchasing (0.92), Payables (0.89), ...]            │   │
│  │            │                                                             │   │
│  │            ▼                                                             │   │
│  │  4. LLM Router: "Which of these 5 should handle the query?"              │   │
│  │            │                                                             │   │
│  │            ▼                                                             │   │
│  │  5. Decision: PARALLEL [Purchasing, Payables]                            │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                             │
│               ┌───────────────────┴───────────────────┐                        │
│               ▼                                       ▼                        │
│  ┌─────────────────┐                      ┌─────────────────┐                  │
│  │   Purchasing    │                      │    Payables     │                  │
│  │   Agent (K8s)   │                      │   Agent (K8s)   │                  │
│  │                 │                      │                 │                  │
│  │  ┌───────────┐  │                      │  ┌───────────┐  │                  │
│  │  │ Planner   │  │                      │  │ Planner   │  │                  │
│  │  │ Researcher│  │                      │  │ Researcher│  │                  │
│  │  │ Analyzer  │  │                      │  │ Analyzer  │  │                  │
│  │  │ Executor  │  │                      │  │ Executor  │  │                  │
│  │  │Synthesizer│  │                      │  │Synthesizer│  │                  │
│  │  └───────────┘  │                      │  └───────────┘  │                  │
│  │                 │                      │                 │                  │
│  │  Domain Tools   │                      │  Domain Tools   │                  │
│  └────────┬────────┘                      └────────┬────────┘                  │
│           │                                        │                            │
│           └────────────────┬───────────────────────┘                            │
│                            │                                                    │
│                            ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                       SHARED SERVICES                                    │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
│  │  │ContextForge │ │BottleRocket │ │   Langfuse  │ │ Redis Stack │        │   │
│  │  │ (Knowledge) │ │ (Inference) │ │  (Tracing)  │ │ (Registry)  │        │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘        │   │
│  │  ┌─────────────┐                                                         │   │
│  │  │ PostgreSQL  │                                                         │   │
│  │  │ (Sessions)  │                                                         │   │
│  │  └─────────────┘                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Why Semantic Discovery vs Flat Registry?

| Approach | Discovery Method | Scalability | Routing Quality |
|----------|------------------|-------------|-----------------|
| **Flat Registry** | Iterate all agents | O(n) - scans all 50+ | LLM sees all agents, context overflow |
| **Semantic Discovery** | Vector search | O(log n) | LLM sees only top 5 relevant agents |

### Single Agent Internal Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DOMAIN AGENT                                       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      RequestContext                                  │    │
│  │  - user: EnrichedUser (permissions, roles, token)                   │    │
│  │  - session_id, request_id                                           │    │
│  │  - locale, entity, page_context                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       ReAct Loop                                     │    │
│  │                                                                      │    │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────┐                      │    │
│  │   │ Planner  │───►│Researcher│───►│ Analyzer │                      │    │
│  │   └──────────┘    └──────────┘    └──────────┘                      │    │
│  │         │              │               │                             │    │
│  │         └──────────────┼───────────────┘                             │    │
│  │                        │                                             │    │
│  │                        ▼                                             │    │
│  │              ┌─────────────────┐                                     │    │
│  │              │   Blackboard    │                                     │    │
│  │              │ (shared state)  │                                     │    │
│  │              └─────────────────┘                                     │    │
│  │                        │                                             │    │
│  │         ┌──────────────┼──────────────┐                             │    │
│  │         │              │              │                              │    │
│  │         ▼              ▼              ▼                              │    │
│  │   ┌──────────┐   ┌───────────┐                                      │    │
│  │   │ Executor │   │Synthesizer│───► Final Response                   │    │
│  │   └──────────┘   └───────────┘                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Domain Tools                                    │    │
│  │  @tool search_po, create_po, approve_po, analyze_spend, etc.        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Agent Discovery

Semantic agent discovery enables routing to 50+ agents without evaluating all of them. Each agent registers with an embedding; queries are matched via vector search.

### 3.1 Agent Model

```python
class AgentInfo(BaseModel):
    """Agent registration info for discovery"""
    
    # Identity
    agent_id: str                      # Unique identifier (e.g., "purchasing")
    name: str                          # Human-readable name
    description: str                   # Rich description for embedding
    version: str
    team: str
    
    # Network
    base_url: str
    health_endpoint: str = "/health"
    
    # Discovery (used to compute embedding)
    capabilities: list[str]            # ["search", "create", "approve"]
    domains: list[str]                 # ["purchase_order", "vendor"]
    example_queries: list[str]         # ["Find PO 12345", ...]
    
    # Health
    is_healthy: bool = True
    registered_at: datetime
    last_heartbeat: datetime
```

### 3.2 Discovery Flow

```python
async def discover_agents(query: str, top_k: int = 5) -> list[AgentInfo]:
    """Find relevant agents via vector search"""
    
    # 1. Embed the query
    query_embedding = await embedding_client.embed(query)
    
    # 2. Vector search in Redis Stack
    results = await redis.ft("agent_idx").search(
        Query(f"*=>[KNN {top_k} @embedding $vec AS score]")
        .return_fields("agent_id", "score")
        .sort_by("score")
        .dialect(2),
        query_params={"vec": query_embedding.tobytes()}
    )
    
    # 3. Return top matches
    return [await get_agent(r.agent_id) for r in results.docs]
```

### 3.3 Redis Storage

```
# Agent info (Hash per agent, TTL-based)
agentcore:agents:purchasing -> HASH {
    "agent_id": "purchasing",
    "name": "Purchasing Agent",
    "description": "Handles POs, vendors, catalogs...",
    "base_url": "http://purchasing:8000",
    "capabilities": '["search", "create", "approve"]',
    "domains": '["purchase_order", "vendor"]',
    "is_healthy": "true",
    "last_heartbeat": "2026-01-13T10:00:00Z"
}  # TTL: 30s

# Vector index (Redis Stack)
agentcore:vectors:purchasing -> HASH {
    "agent_id": "purchasing",
    "embedding": <binary 1536 floats>
}

# Index definition
FT.CREATE agent_idx ON HASH PREFIX 1 agentcore:vectors:
    SCHEMA agent_id TAG embedding VECTOR HNSW 6 TYPE FLOAT32 DIM 1536 DISTANCE_METRIC COSINE
```

### 3.4 Registration

```python
async def startup():
    # Register agent
    await registry.register(AgentInfo(
        agent_id="purchasing",
        name="Purchasing Agent",
        description="""Purchasing domain expert that handles:
        - Purchase order creation, search, and management
        - Vendor lookup and management  
        - Catalog item search
        - Spend analysis and reporting""",
        base_url="http://purchasing:8000",
        capabilities=["search", "create", "update", "approve", "analyze"],
        domains=["purchase_order", "vendor", "catalog"],
        example_queries=[
            "Find PO 12345",
            "Create a purchase order for office supplies",
            "What's my spend on IT equipment this quarter?",
        ],
        version="1.0.0",
        team="Procurement Engineering",
        registered_at=datetime.utcnow(),
        last_heartbeat=datetime.utcnow(),
    ))
    
    # Start heartbeat
    heartbeat_manager.start()
```

---

## Package Structure

```
agent_framework/                    # Monorepo root
├── admin-ui/                       # Existing React UI
├── contextforge/                   # Existing RAG backend (unchanged)
├── agentcore/                      # Agent library
│   ├── pyproject.toml
│   ├── README.md
│   ├── src/agentcore/
│   │   ├── __init__.py
│   │   │
│   │   ├── settings/               # Pydantic Settings (centralized config)
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # BaseSettings with common patterns
│   │   │   ├── inference.py        # InferenceSettings
│   │   │   ├── embedding.py        # EmbeddingSettings
│   │   │   ├── knowledge.py        # KnowledgeSettings (ContextForge connection)
│   │   │   ├── auth.py             # AuthSettings
│   │   │   ├── session.py          # SessionSettings (database)
│   │   │   ├── tracing.py          # LangfuseSettings
│   │   │   ├── registry.py         # RegistrySettings (Redis)
│   │   │   └── agent.py            # AgentSettings (behavior)
│   │   │
│   │   ├── auth/                   # Auth & User Context (FIRST-CLASS)
│   │   │   ├── __init__.py
│   │   │   ├── models.py           # EnrichedUser, Permission (Pydantic)
│   │   │   ├── context.py          # RequestContext
│   │   │   ├── provider.py         # AuthProvider protocol + impl
│   │   │   └── dependencies.py     # FastAPI dependencies
│   │   │
│   │   ├── tracing/                # Langfuse First-Class Integration
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # TracingClient (Langfuse wrapper)
│   │   │   ├── context.py          # TraceContext (request-scoped)
│   │   │   ├── decorators.py       # @trace_agent, @trace_tool, etc.
│   │   │   └── spans.py            # Span types (decision, inference, tool)
│   │   │
│   │   ├── knowledge/              # Native ContextForge Integration
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # KnowledgeClient (calls ContextForge API)
│   │   │   ├── models.py           # KnowledgeNode, SearchResult, etc.
│   │   │   ├── retriever.py        # KnowledgeRetriever (for sub-agents)
│   │   │   └── types.py            # KnowledgeType enum, schemas
│   │   │
│   │   ├── core/                   # Core Agent Infrastructure
│   │   │   ├── __init__.py
│   │   │   ├── agent.py            # BaseAgent class
│   │   │   ├── react.py            # ReAct loop with iterative replanning
│   │   │   ├── blackboard.py       # Shared context + key variables
│   │   │   ├── models.py           # Message, ToolCall, etc. (Pydantic)
│   │   │   └── protocols.py        # Agent protocols (DRY)
│   │   │
│   │   ├── sub_agents/             # Functional Sub-Agents
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # SubAgent base class (generic)
│   │   │   ├── planner.py          # Task decomposition
│   │   │   ├── researcher.py       # Information gathering (uses ContextForge)
│   │   │   ├── analyzer.py         # Data analysis
│   │   │   ├── executor.py         # Action execution
│   │   │   └── synthesizer.py      # Final response generation
│   │   │
│   │   ├── tools/                  # Tool System
│   │   │   ├── __init__.py
│   │   │   ├── decorator.py        # @tool decorator
│   │   │   ├── models.py           # ToolSpec, RetentionStrategy (Pydantic)
│   │   │   ├── registry.py         # ToolRegistry
│   │   │   └── executor.py         # ToolExecutor with tracing
│   │   │
│   │   ├── inference/              # LLM Inference
│   │   │   ├── __init__.py
│   │   │   ├── protocol.py         # InferenceProtocol
│   │   │   ├── client.py           # OpenAI-compatible client
│   │   │   ├── models.py           # Request/Response models (Pydantic)
│   │   │   └── pool.py             # Resource pooling (8 concurrent)
│   │   │
│   │   ├── embedding/              # Embedding Service
│   │   │   ├── __init__.py
│   │   │   ├── protocol.py         # EmbeddingProtocol
│   │   │   ├── client.py           # OpenAI-compatible client
│   │   │   └── pool.py             # Resource pooling (32 concurrent)
│   │   │
│   │   ├── session/                # Session & State
│   │   │   ├── __init__.py
│   │   │   ├── models.py           # SQLAlchemy + Pydantic models
│   │   │   ├── store.py            # SessionStore
│   │   │   └── repository.py       # Repository pattern (DRY)
│   │   │
│   │   ├── transport/              # WebSocket Transport
│   │   │   ├── __init__.py
│   │   │   ├── server.py           # WebSocket server
│   │   │   ├── models.py           # chat_contract messages (Pydantic)
│   │   │   ├── handlers.py         # Message handlers
│   │   │   └── streaming.py        # Response streaming
│   │   │
│   │   ├── registry/               # Agent Registry (Redis-based)
│   │   │   ├── __init__.py
│   │   │   ├── models.py           # AgentRegistration, Capability
│   │   │   ├── client.py           # RedisRegistryClient
│   │   │   └── heartbeat.py        # Heartbeat manager
│   │   │
│   │   ├── orchestrator/           # Multi-Agent Orchestration
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py     # Main orchestrator
│   │   │   ├── router.py           # Query router (LLM-based)
│   │   │   └── synthesizer.py      # Cross-agent response synthesis
│   │   │
│   │   ├── agent/                  # Standard Agent API
│   │   │   ├── __init__.py
│   │   │   ├── api.py              # FastAPI wrapper
│   │   │   └── base.py             # BaseAgent with registration
│   │   │
│   │   ├── p2p/                    # P2P Extension (Future)
│   │   │   ├── __init__.py
│   │   │   └── client.py           # Direct agent-to-agent calls
│   │   │
│   │   └── common/                 # Shared Utilities (DRY)
│   │       ├── __init__.py
│   │       ├── pool.py             # Generic resource pool
│   │       ├── retry.py            # Retry with backoff
│   │       ├── json.py             # JSON serialization helpers
│   │       └── errors.py           # Common exceptions
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── fixtures/
│   │
│   └── examples/
│       └── purchasing_agent/       # Complete example domain agent
│           ├── pyproject.toml
│           ├── src/purchasing_agent/
│           │   ├── __init__.py
│           │   ├── agent.py        # PurchasingAgent
│           │   ├── tools.py        # Domain-specific tools
│           │   └── main.py         # FastAPI + WebSocket server
│           └── README.md
│
├── docs/                           # Documentation
│   ├── agentcore_design.md         # This document
│   ├── chat_contract.md            # WebSocket protocol
│   └── knowledge_base_system_design_v2.md
│
├── Makefile
└── README.md
```

---

## Core Design Decisions

### 1. User Context as First-Class Citizen

Every request carries `RequestContext` with:
- `EnrichedUser`: user_id, permissions, roles, token
- `session_id`, `request_id`
- `locale`, `entity`, `page` context

```python
@dataclass(frozen=True)
class RequestContext:
    user: EnrichedUser       # Always required
    session_id: str          # Always required
    request_id: str          # Always required
    locale: Locale
    entity: Optional[EntityContext]
    page: Optional[PageContext]
```

**Rationale**: Enterprise systems require authentication/authorization everywhere. Making user context explicit prevents security holes.

### 2. Pydantic Settings (No Hardcoding)

All configuration via Pydantic Settings with environment variables:

```python
class InferenceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFERENCE_")
    
    base_url: str
    default_model: str = "gpt-4"
    max_concurrent: int = 8
    timeout_seconds: float = 120.0
```

**Rationale**: Configuration should be externalized, validated, and type-safe.

### 3. Langfuse First-Class Tracing

Every request gets a trace capturing:
- Agent decisions (which sub-agent, why)
- All inference calls (input/output/tokens)
- Tool executions
- Context retrievals
- Timing and errors

```python
# Automatic tracing via decorators
@trace_agent("handle_message")
async def handle_message(self, ctx: RequestContext, message: str):
    ...

@trace_inference
async def complete(self, messages, ...):
    ...
```

**Rationale**: Observability is critical for debugging and improving agent behavior.

### 4. Native ContextForge Integration

ContextForge is not just a tool - it's a core dependency. The `knowledge/` module in agentcore provides the integration:

```python
class BaseAgent:
    def __init__(
        self,
        knowledge: KnowledgeClient,  # Required - connects to ContextForge
        inference: InferenceClient,
        ...
    ):
        self.knowledge = knowledge
```

Sub-agents use `KnowledgeRetriever` directly for:
- Planning: Get playbooks and high-level concepts
- Research: Get schemas, FAQs, entities
- Analysis: Get related context for comparison

**Rationale**: Knowledge retrieval is fundamental to agent behavior, not an optional capability.

### 5. Hub-and-Spoke Sub-Agent Architecture

Internal sub-agents communicate through Blackboard (shared state):

```
Main Agent ←→ Blackboard ←→ Planner
Main Agent ←→ Blackboard ←→ Researcher
Main Agent ←→ Blackboard ←→ Analyzer
Main Agent ←→ Blackboard ←→ Executor
Main Agent ←→ Blackboard ←→ Synthesizer
```

**Rationale**: Simpler than P2P, easier to debug, matches proven patterns (OpenCode, Manus).

### 6. Supervisor Pattern for Multi-Agent Coordination

Separate agent instances (Purchasing, Payables, Asset) coordinate via Orchestrator:

```
User Query → Orchestrator → Route → Invoke Agent(s) → Synthesize → Response
```

**Rationale**: Clear ownership, single entry point for cross-domain queries, traceable.

### 7. Redis-Based Service Discovery

Agents self-register to Redis with heartbeat:

```python
# Agent registers on startup
await registry.register(AgentRegistration(
    agent_id="purchasing",
    base_url="http://purchasing:8000",
    capabilities=[...],
    ...
))

# Continuous heartbeat
while running:
    await registry.heartbeat("purchasing")
    await asyncio.sleep(10)
```

**Rationale**: Dynamic discovery without YAML configs, health-aware routing.

---

## Component Specifications

### 5.1 Settings Module

#### Base Settings

```python
# agentcore/settings/base.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class BaseAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

class EnvironmentSettings(BaseAppSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")
    
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
```

#### All Settings Classes

| Settings Class | Env Prefix | Key Fields |
|----------------|------------|------------|
| `InferenceSettings` | `INFERENCE_` | base_url, default_model, max_concurrent (8), timeout |
| `EmbeddingSettings` | `EMBEDDING_` | base_url, default_model, max_concurrent (32) |
| `KnowledgeSettings` | `KNOWLEDGE_` | base_url, default_limit, hybrid weights |
| `TracingSettings` | `LANGFUSE_` | public_key, secret_key, host, enabled |
| `SessionSettings` | `SESSION_` | database_url, pool_size, session_ttl |
| `RegistrySettings` | `REGISTRY_` | redis_url, heartbeat_interval, ttl |
| `AuthSettings` | `AUTH_` | cache_ttl, default_permissions |
| `AgentSettings` | `AGENT_` | max_iterations, max_context_tokens |

### 5.2 Auth Module

#### EnrichedUser Model

```python
class Permission(str, Enum):
    ADMIN = "Admin"
    BUYER = "Buyer"
    PLANNER = "Planner"
    PO_CREATE = "POCreate"
    PO_APPROVE = "POApprove"
    # ... more

class EnrichedUser(BaseModel):
    user_id: int
    username: str
    email: str
    display_name: str
    department: str
    title: str
    entity_id: int
    entity_name: str
    
    is_admin: bool = False
    is_buyer: bool = False
    is_planner: bool = False
    is_super_user: bool = False
    
    permissions: FrozenSet[Permission]
    token: str = Field(exclude=True, repr=False)
    
    class Config:
        frozen = True  # Immutable
    
    def has_permission(self, permission: Permission) -> bool: ...
    def has_any_permission(self, *permissions: Permission) -> bool: ...
    def has_all_permissions(self, *permissions: Permission) -> bool: ...
```

#### RequestContext Model

```python
class RequestContext(BaseModel):
    user: EnrichedUser          # Required
    session_id: str             # Required
    request_id: str             # Required
    locale: Locale
    entity: Optional[EntityContext]
    page: Optional[PageContext]
    extra: dict[str, Any] = {}
    
    class Config:
        frozen = True
    
    @classmethod
    def current(cls) -> Optional["RequestContext"]: ...
    
    @classmethod
    def require_current(cls) -> "RequestContext": ...
```

#### Auth Provider

```python
class AuthProvider(Protocol):
    async def authenticate(self, token: str, user_info: dict) -> EnrichedUser: ...

class DefaultAuthProvider:
    """Takes user_info from jwt_validator, returns EnrichedUser"""
    
    async def authenticate(self, token: str, user_info: dict) -> EnrichedUser:
        # Parse permissions from user_info
        # Create and cache EnrichedUser
        ...
```

### 5.3 Tracing Module

#### TraceContext

```python
class TraceContext:
    trace_id: str
    session_id: str
    user_id: str
    
    # Metrics
    inference_calls: int = 0
    tool_calls: int = 0
    context_retrievals: int = 0
    total_tokens: int = 0
    
    # Langfuse references
    _trace: StatefulTraceClient
    _current_span: StatefulSpanClient
```

#### TracingClient

```python
class TracingClient:
    def start_trace(self, ctx: RequestContext, name: str) -> TraceContext: ...
    def end_trace(self, trace_ctx: TraceContext, output: str = None): ...
    
    async def span(self, name: str, trace_ctx: TraceContext, span_type: str) -> AsyncContextManager: ...
    async def generation(self, name: str, trace_ctx: TraceContext, model: str) -> AsyncContextManager: ...
    
    def log_decision(self, trace_ctx: TraceContext, decision_type: str, decision: str, reasoning: str): ...
```

#### Decorators

```python
@trace_agent("method_name")      # Trace agent methods
@trace_tool("tool_id")           # Trace tool executions
@trace_inference                 # Trace LLM calls
@trace_knowledge                 # Trace ContextForge/knowledge retrieval calls
```

### 5.4 Knowledge Module (ContextForge Integration)

The `knowledge/` module provides native integration with the external ContextForge service.

#### Models

```python
class KnowledgeType(str, Enum):
    """Types of knowledge in ContextForge"""
    SCHEMA = "schema"
    CONCEPT = "concept"
    PLAYBOOK = "playbook"
    FAQ = "faq"
    ENTITY = "entity"

class KnowledgeNode(BaseModel):
    """A single knowledge node from ContextForge"""
    id: str
    type: KnowledgeType
    title: str
    content: str
    metadata: dict
    score: Optional[float]
    edges: list[str]

class KnowledgeBundle(BaseModel):
    """Bundle of knowledge retrieved for a query"""
    schemas: list[KnowledgeNode]
    concepts: list[KnowledgeNode]
    playbooks: list[KnowledgeNode]
    search_results: list[KnowledgeNode]
    
    def to_prompt_context(self) -> str: ...
```

#### KnowledgeClient

```python
class KnowledgeClient:
    """Client for ContextForge knowledge retrieval"""
    
    @trace_knowledge
    async def search(self, ctx: RequestContext, query: str, types: list[KnowledgeType] = None) -> SearchResult: ...
    
    @trace_knowledge
    async def get_bundle(self, ctx: RequestContext, query: str) -> KnowledgeBundle: ...
    
    async def get_node(self, ctx: RequestContext, node_id: str) -> Optional[KnowledgeNode]: ...
    async def get_related(self, ctx: RequestContext, node_id: str) -> list[KnowledgeNode]: ...
```

#### KnowledgeRetriever (for Sub-Agents)

```python
class KnowledgeRetriever:
    """High-level retriever for sub-agents"""
    
    async def retrieve_for_planning(self, ctx: RequestContext, query: str) -> KnowledgeBundle: ...
    async def retrieve_for_research(self, ctx: RequestContext, query: str) -> KnowledgeBundle: ...
    async def retrieve_schema(self, ctx: RequestContext, entity_name: str) -> Optional[str]: ...
```

### 5.5 Core Module

#### Message Models

```python
class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

class Message(BaseModel):
    role: MessageRole
    content: Optional[str]
    name: Optional[str]
    tool_call_id: Optional[str]
    tool_calls: Optional[list[ToolCall]]
    
    def to_openai_format(self) -> dict: ...

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]

class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    result: Any
    compact_result: Optional[Any]  # For context management
    error: Optional[str]
```

#### Blackboard

```python
class Blackboard:
    ctx: RequestContext
    session: Session
    
    plan: Optional[dict]
    current_step: int
    variables: dict[str, Any]
    tool_results: list[dict]
    findings: list[dict]
    pending_interactions: list[dict]
    
    def set(self, key: str, value: Any, source: str): ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def add_finding(self, source: str, finding: dict): ...
    def add_tool_result(self, tool_name: str, result: Any, compact_result: Any = None): ...
    def get_context_for_llm(self, max_tokens: int) -> str: ...
```

#### BaseAgent

```python
class BaseAgent(ABC):
    domain: str
    system_prompt: str
    max_iterations: int = 10
    
    def __init__(
        self,
        knowledge: KnowledgeClient,      # ContextForge integration
        inference: InferenceClient,
        session_store: SessionStore,
        tracing: TracingClient,
        registry: RedisRegistryClient,
        tool_registry: Optional[ToolRegistry] = None,
    ): ...
    
    async def handle_message(
        self,
        ctx: RequestContext,
        message: str,
        attachments: list[dict] = None,
    ) -> AsyncIterator[dict]: ...
    
    @abstractmethod
    def get_system_prompt(self, ctx: RequestContext) -> str: ...
    
    # For registration
    def get_capabilities(self) -> list[str]: ...
    def get_domains(self) -> list[str]: ...
    def get_keywords(self) -> list[str]: ...
    def get_example_queries(self) -> list[str]: ...
```

### 5.6 Sub-Agents Module

#### SubAgent Base

```python
class SubAgentResult(BaseModel):
    success: bool
    output: Any
    error: Optional[str]
    tokens_used: int = 0
    replan_needed: bool = False
    replan_reason: Optional[str] = None

class SubAgent(ABC):
    name: str
    
    def __init__(self, inference: InferenceClient, knowledge: KnowledgeClient): ...
    
    @abstractmethod
    async def execute(
        self,
        ctx: RequestContext,
        blackboard: Blackboard,
        instruction: str,
        **kwargs,
    ) -> SubAgentResult: ...
    
    def get_context_window(self, blackboard: Blackboard, max_tokens: int) -> str: ...
```

#### Sub-Agent Specifications

| Sub-Agent | Purpose | Uses Tools | Uses Knowledge |
|-----------|---------|------------|----------------|
| **Planner** | Decompose task into steps | No | Yes (playbooks) |
| **Researcher** | Gather information | Yes (read-only) | Yes (search) |
| **Analyzer** | Analyze data, compare | No | Yes (schemas) |
| **Executor** | Perform actions | Yes (write) | No |
| **Synthesizer** | Generate final response | No | No |

### 5.7 Tools Module

#### Tool Decorator

```python
@tool(
    id="search_po",
    description="Search for purchase orders",
    retention=RetentionStrategy(max_items=20),
    hil=HILConfig(requires_confirmation=False),
    requires_permissions=["Buyer"],
    timeout=30.0,
)
async def search_po(self, ctx: RequestContext, po_number: str) -> list[dict]:
    ...
```

#### ToolSpec Model

```python
class RetentionStrategy(BaseModel):
    max_items: Optional[int]
    max_chars: Optional[int]
    compact_fields: list[str] = []

class HILConfig(BaseModel):
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str]
    form_schema: Optional[dict]
    timeout: float = 300.0

class ToolSpec(BaseModel):
    id: str
    name: str
    description: str
    parameters: dict  # JSON Schema
    retention: Optional[RetentionStrategy]
    hil: Optional[HILConfig]
    requires_permissions: list[str]
    timeout: float = 30.0
    
    def to_openai_format(self) -> dict: ...
```

### 5.8 Inference Module

#### InferenceClient

```python
class InferenceClient:
    def __init__(self, settings: InferenceSettings): ...
    
    @trace_inference
    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] = None,
        config: InferenceConfig = None,
        ctx: RequestContext = None,
    ) -> InferenceResponse: ...
    
    async def stream(
        self,
        messages: list[Message],
        ...
    ) -> AsyncIterator[InferenceResponse]: ...
    
    @property
    def pool_metrics(self) -> dict: ...
```

#### Resource Pooling

```python
class ResourcePool:
    """Semaphore-based pool for rate limiting"""
    
    def __init__(self, max_concurrent: int, queue_timeout: float): ...
    
    async def __aenter__(self): ...
    async def __aexit__(self, ...): ...
    
    @property
    def metrics(self) -> dict: ...
```

### 5.9 Session Module

#### SQLAlchemy Models

```python
class SessionModel(Base):
    __tablename__ = "agent_sessions"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    agent_type = Column(String(50), nullable=False, index=True)
    state = Column(JSON, default=dict)
    blackboard = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    messages = relationship("MessageModel", back_populates="session")
    checkpoints = relationship("CheckpointModel", back_populates="session")

class MessageModel(Base):
    __tablename__ = "agent_messages"
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("agent_sessions.id"))
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=True)
    name = Column(String(100), nullable=True)
    tool_call_id = Column(String(100), nullable=True)
    tool_calls = Column(JSON, nullable=True)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

class CheckpointModel(Base):
    __tablename__ = "agent_checkpoints"
    
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("agent_sessions.id"))
    thread_id = Column(String(100), nullable=False)
    checkpoint_id = Column(String(100), nullable=False)
    parent_checkpoint_id = Column(String(100), nullable=True)
    state = Column(JSON, nullable=False)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### SessionStore

```python
class SessionStore:
    async def get(self, session_id: str) -> Optional[Session]: ...
    async def get_or_create(self, session_id: str, user_id: int, agent_type: str) -> Session: ...
    async def save(self, session: Session): ...
    async def add_message(self, session_id: str, message: MessageData) -> str: ...
    async def delete(self, session_id: str): ...
    async def cleanup_expired(self) -> int: ...
```

---

## Multi-Agent Coordination

### 6.1 Agent Registry

The registry module provides agent registration with semantic discovery via Redis Stack vector search.

#### Registry Settings

```python
class RegistrySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REGISTRY_")
    
    redis_url: str
    key_prefix: str = "agentcore:agents"
    heartbeat_interval_seconds: int = 10
    agent_ttl_seconds: int = 30
    
    # Vector Search
    embedding_dimension: int = 1536
    discovery_top_k: int = 5
```

#### RegistryClient

```python
class RegistryClient:
    """Agent registration and discovery via Redis Stack"""
    
    def __init__(
        self,
        redis: Redis,
        embedding: EmbeddingClient,
        settings: RegistrySettings,
    ): ...
    
    async def register(self, agent: AgentInfo) -> None:
        """
        Register agent with embedding for discovery.
        
        1. Compute embedding from description + capabilities
        2. Store agent info as Redis hash with TTL
        3. Store embedding in vector index
        """
        text = f"{agent.name}: {agent.description}. {', '.join(agent.capabilities)}"
        embedding = await self._embedding.embed(text)
        
        # Store agent info
        await self._redis.hset(
            f"{self._prefix}:{agent.agent_id}",
            mapping=agent.model_dump(mode="json")
        )
        await self._redis.expire(
            f"{self._prefix}:{agent.agent_id}",
            self._settings.agent_ttl_seconds
        )
        
        # Store vector
        await self._redis.hset(
            f"{self._prefix}:vec:{agent.agent_id}",
            mapping={"agent_id": agent.agent_id, "embedding": embedding.tobytes()}
        )
    
    async def unregister(self, agent_id: str) -> None:
        """Remove agent from registry"""
        await self._redis.delete(f"{self._prefix}:{agent_id}")
        await self._redis.delete(f"{self._prefix}:vec:{agent_id}")
    
    async def heartbeat(self, agent_id: str) -> None:
        """Refresh TTL"""
        await self._redis.expire(f"{self._prefix}:{agent_id}", self._settings.agent_ttl_seconds)
        await self._redis.hset(f"{self._prefix}:{agent_id}", "last_heartbeat", datetime.utcnow().isoformat())
    
    async def get(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent by ID"""
        data = await self._redis.hgetall(f"{self._prefix}:{agent_id}")
        return AgentInfo.model_validate(data) if data else None
    
    async def discover(self, query: str, top_k: int = 5) -> list[AgentInfo]:
        """Find relevant agents via vector search"""
        query_embedding = await self._embedding.embed(query)
        
        results = await self._redis.ft(f"{self._prefix}:idx").search(
            Query(f"*=>[KNN {top_k} @embedding $vec AS score]")
            .return_fields("agent_id", "score")
            .sort_by("score")
            .dialect(2),
            query_params={"vec": query_embedding.tobytes()}
        )
        
        agents = []
        for doc in results.docs:
            agent = await self.get(doc.agent_id)
            if agent and agent.is_healthy:
                agents.append(agent)
        return agents
    
    async def get_routing_context(self, agents: list[AgentInfo]) -> str:
        """Generate LLM-friendly agent descriptions for routing"""
        parts = []
        for agent in agents:
            parts.append(f"""
Agent: {agent.name} (id: {agent.agent_id})
Description: {agent.description}
Capabilities: {', '.join(agent.capabilities)}
Examples: {'; '.join(agent.example_queries[:3])}
""")
        return "\n---\n".join(parts)
```

#### Heartbeat Manager

```python
class HeartbeatManager:
    """Background task to keep agent alive"""
    
    def __init__(self, registry: RegistryClient, agent_id: str, interval: int = 10): ...
    
    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())
    
    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
    
    async def _loop(self) -> None:
        while self._running:
            await self._registry.heartbeat(self._agent_id)
            await asyncio.sleep(self._interval)
```

#### Vector Index Setup

```python
async def ensure_vector_index(redis: Redis, prefix: str, dim: int = 1536) -> None:
    """Create vector index if not exists"""
    try:
        await redis.ft(f"{prefix}:idx").info()
    except ResponseError:
        await redis.ft(f"{prefix}:idx").create_index(
            [TagField("agent_id"), VectorField("embedding", "HNSW", {"TYPE": "FLOAT32", "DIM": dim, "DISTANCE_METRIC": "COSINE"})],
            definition=IndexDefinition(prefix=[f"{prefix}:vec:"], index_type=IndexType.HASH)
        )
```

### 6.2 Orchestrator

The Orchestrator discovers relevant agents via vector search, then routes queries.

#### Orchestrator Settings

```python
class OrchestratorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_")
    
    discovery_top_k: int = 5              # Agents to consider
    use_llm_routing: bool = True          # LLM vs rule-based routing
    routing_model: str = "gpt-4"
    max_parallel_agents: int = 5
    agent_timeout: float = 60.0
    fallback_agent: str = "purchasing"
```

#### Routing Models

```python
class RoutingStrategy(str, Enum):
    SINGLE = "single"           # One agent
    PARALLEL = "parallel"       # Multiple, independent
    SEQUENTIAL = "sequential"   # Multiple, dependent

class RoutingDecision(BaseModel):
    strategy: RoutingStrategy
    agents: list[str]
    reasoning: str
```

#### Orchestrator

```python
class Orchestrator:
    """
    Flow:
    1. Discover agents (vector search)
    2. Route query (LLM or rule-based)
    3. Invoke agent(s)
    4. Synthesize if parallel
    """
    
    def __init__(
        self,
        registry: RegistryClient,
        inference: InferenceClient,
        tracing: TracingClient,
        settings: OrchestratorSettings,
    ): ...
    
    async def handle_request(
        self,
        ctx: RequestContext,
        query: str,
    ) -> AsyncIterator[dict]:
        # 1. Discover
        agents = await self._registry.discover(query, top_k=self._settings.discovery_top_k)
        
        # 2. Route
        routing = await self._route(ctx, query, agents)
        
        # 3. Execute
        if routing.strategy == RoutingStrategy.SINGLE:
            async for msg in self._invoke_single(ctx, query, routing):
                yield msg
        elif routing.strategy == RoutingStrategy.PARALLEL:
            results = await self._invoke_parallel(ctx, query, routing)
            async for msg in self._synthesize(ctx, query, results):
                yield msg
        elif routing.strategy == RoutingStrategy.SEQUENTIAL:
            async for msg in self._invoke_sequential(ctx, query, routing):
                yield msg
    
    async def _route(self, ctx: RequestContext, query: str, agents: list[AgentInfo]) -> RoutingDecision:
        if not agents:
            return RoutingDecision(strategy=RoutingStrategy.SINGLE, agents=[self._settings.fallback_agent], reasoning="Fallback")
        
        if len(agents) == 1:
            return RoutingDecision(strategy=RoutingStrategy.SINGLE, agents=[agents[0].agent_id], reasoning="Single match")
        
        if not self._settings.use_llm_routing:
            return RoutingDecision(strategy=RoutingStrategy.SINGLE, agents=[agents[0].agent_id], reasoning="Top match")
        
        # LLM routing
        context = await self._registry.get_routing_context(agents)
        response = await self._inference.complete([
            Message(role=MessageRole.SYSTEM, content=ROUTER_PROMPT),
            Message(role=MessageRole.USER, content=f"Query: {query}\n\nAgents:\n{context}")
        ])
        return RoutingDecision.model_validate_json(response.content)
```

#### Router Prompt

```python
ROUTER_PROMPT = """You are a query router. Decide which agent(s) should handle the query.

Guidelines:
1. SINGLE: Use when one agent can fully answer the query
2. PARALLEL: Use when multiple agents can work independently
   - Example: "Compare PO prices with budget forecasts" → Purchasing + Finance in parallel
3. SEQUENTIAL: Use when one agent's output is needed by another
   - Example: "Find the PO for invoice 123 and approve it" → Invoice first, then PO Approval
4. HANDOFF: Use when initial triage leads to a specialist
   - Example: Complex vendor dispute → Start with Purchasing, handoff to Legal

Always choose the simplest strategy that will satisfy the query.
Prefer SINGLE when possible - only use multiple agents when truly needed.
"""
```

### 6.3 Domain Agent Standard API

Every domain agent exposes:

```
GET  /health                    # Health check
GET  /capabilities              # Return registration info
POST /api/v1/query              # Handle query (streaming or complete)
POST /api/v1/p2p                # P2P calls from other agents (future)
```

#### AgentAPI Wrapper

```python
class AgentAPI:
    def __init__(self, agent: BaseAgent): ...
    
    # Routes
    # GET /health -> {"status": "healthy", "agent": "purchasing"}
    # GET /capabilities -> AgentRegistration
    # POST /api/v1/query -> StreamingResponse or JSON
```

---

## Data Models

### 7.1 Pydantic Models Summary

| Model | Module | Purpose |
|-------|--------|---------|
| `EnrichedUser` | auth | User identity and permissions |
| `RequestContext` | auth | Request-scoped context |
| `TraceContext` | tracing | Request-scoped trace |
| `Message` | core | Conversation message |
| `ToolCall` | core | LLM tool invocation |
| `ToolResult` | core | Tool execution result |
| `ToolSpec` | tools | Tool definition |
| `KnowledgeNode` | knowledge | ContextForge node |
| `KnowledgeBundle` | knowledge | Retrieved knowledge |
| `AgentInfo` | registry | Agent registration for discovery |
| `RoutingDecision` | orchestrator | Query routing with discovery metadata |
| `AgentInvocationResult` | orchestrator | Result from single agent invocation |
| `Session` | session | Session state |

### 7.2 SQLAlchemy Models Summary

| Model | Table | Purpose |
|-------|-------|---------|
| `SessionModel` | agent_sessions | Session persistence |
| `MessageModel` | agent_messages | Message history |
| `CheckpointModel` | agent_checkpoints | LangGraph checkpoints |

---

## Configuration

### 8.1 Environment Variables

```bash
# .env.example

# =============================================================================
# ENVIRONMENT
# =============================================================================
APP_ENVIRONMENT=development
APP_DEBUG=true
APP_LOG_LEVEL=INFO

# =============================================================================
# INFERENCE (BottleRocket - OpenAI Compatible)
# =============================================================================
INFERENCE_BASE_URL=https://bottlerocket.internal.company.com
INFERENCE_API_KEY=sk-xxx  # Optional
INFERENCE_DEFAULT_MODEL=gpt-4
INFERENCE_MAX_CONCURRENT=8
INFERENCE_TIMEOUT_SECONDS=120
INFERENCE_TEMPERATURE=0.7
INFERENCE_MAX_TOKENS=4096
INFERENCE_MAX_RETRIES=3

# =============================================================================
# EMBEDDING (BottleRocket)
# =============================================================================
EMBEDDING_BASE_URL=https://bottlerocket.internal.company.com
EMBEDDING_DEFAULT_MODEL=text-embedding-ada-002
EMBEDDING_MAX_CONCURRENT=32
EMBEDDING_TIMEOUT_SECONDS=30

# =============================================================================
# KNOWLEDGE (ContextForge Integration)
# =============================================================================
KNOWLEDGE_BASE_URL=http://localhost:8000
KNOWLEDGE_DEFAULT_LIMIT=10
KNOWLEDGE_HYBRID_SEARCH_ENABLED=true
KNOWLEDGE_BM25_WEIGHT=0.3
KNOWLEDGE_VECTOR_WEIGHT=0.7
KNOWLEDGE_CACHE_TTL_SECONDS=300

# =============================================================================
# LANGFUSE (Tracing)
# =============================================================================
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_ENABLED=true
LANGFUSE_SAMPLE_RATE=1.0
LANGFUSE_TRACE_INFERENCE=true
LANGFUSE_TRACE_TOOLS=true
LANGFUSE_TRACE_CONTEXT_RETRIEVAL=true
LANGFUSE_TRACE_DECISIONS=true
LANGFUSE_MAX_CONTENT_LENGTH=10000

# =============================================================================
# SESSION (PostgreSQL)
# =============================================================================
SESSION_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/agent_sessions
SESSION_POOL_SIZE=5
SESSION_MAX_OVERFLOW=10
SESSION_POOL_TIMEOUT=30
SESSION_SESSION_TTL_HOURS=24
SESSION_MAX_MESSAGES_PER_SESSION=100

# =============================================================================
# REGISTRY (Redis)
# =============================================================================
REGISTRY_REDIS_URL=redis://localhost:6379/0
REGISTRY_KEY_PREFIX=agentcore:agents
REGISTRY_HEARTBEAT_INTERVAL_SECONDS=10
REGISTRY_AGENT_TTL_SECONDS=30

# =============================================================================
# AUTH
# =============================================================================
AUTH_USER_CACHE_TTL_SECONDS=300

# =============================================================================
# AGENT (Behavior)
# =============================================================================
AGENT_MAX_ITERATIONS=10
AGENT_MAX_TOOL_CALLS_PER_ITERATION=5
AGENT_MAX_CONTEXT_TOKENS=8000
AGENT_USE_COMPACT_RESULTS=true
AGENT_TOOL_TIMEOUT_SECONDS=30
AGENT_SUB_AGENT_TIMEOUT_SECONDS=60

# =============================================================================
# ORCHESTRATOR
# =============================================================================
ORCHESTRATOR_USE_LLM_ROUTING=true
ORCHESTRATOR_FALLBACK_AGENT=purchasing
ORCHESTRATOR_MAX_PARALLEL_AGENTS=5
ORCHESTRATOR_AGENT_TIMEOUT_SECONDS=60
```

---

## Implementation Tasks

### Phase 1: Foundation ✅ COMPLETE

#### 1.1 Project Setup ✅
- [x] Create `agentcore/` directory structure
- [x] Set up `pyproject.toml` with dependencies
- [x] Create `__init__.py` files for all modules
- [x] Set up development environment (venv)

#### 1.2 Settings Module ✅ COMPLETE
- [x] Implement `BaseAppSettings` with common config
- [x] Implement `RegistrySettings`
- [x] Implement `OrchestratorSettings`
- [x] Implement `EmbeddingSettings`
- [x] Implement `InferenceSettings`
- [x] Implement `KnowledgeSettings`
- [x] Implement `TracingSettings`
- [x] Implement `SessionSettings`
- [x] Implement `AuthSettings`
- [x] Implement `AgentSettings`
- [x] Create `Settings` aggregator class
- [x] Create `get_settings()` singleton

#### 1.3 Common Utilities
- [ ] Implement `ResourcePool` (generic semaphore pool)
- [ ] Implement `RetryConfig` and `with_retry` decorator
- [ ] Implement common exceptions (`AgentCoreError`, etc.)
- [ ] Implement JSON serialization helpers

#### 1.4 Auth Module ✅
- [x] Implement `Permission` enum
- [x] Implement `EnrichedUser` model
- [x] Implement `Locale`, `EntityContext`, `PageContext` models
- [x] Implement `RequestContext` model with contextvars
- [ ] Implement `AuthProvider` protocol
- [ ] Implement `DefaultAuthProvider`
- [ ] Implement FastAPI dependencies for auth

### Phase 2: Tracing & Knowledge ✅ COMPLETE

#### 2.1 Tracing Module ✅
- [x] Implement `TraceContext` model
- [x] Implement `TracingClient` with Langfuse
- [x] Implement `MockTracingClient` for testing
- [x] Implement `start_trace()` and `end_trace()`
- [x] Implement `span()` context manager
- [x] Implement `generation()` context manager
- [x] Implement `log_decision()` method
- [x] Implement `@trace_agent` decorator
- [x] Implement `@trace_tool` decorator
- [x] Implement `@trace_inference` decorator
- [x] Implement `@trace_knowledge` decorator

#### 2.2 Knowledge Module (ContextForge Integration) ✅
- [x] Implement `KnowledgeType` enum
- [x] Implement `KnowledgeNode` model
- [x] Implement `SearchResult` and `SearchResults` models
- [x] Implement `KnowledgeBundle` model with `to_prompt_context()`
- [x] Implement `KnowledgeClient`
  - [x] `search()` method
  - [x] `get_bundle()` method
  - [x] `get_node()` method
  - [x] `get_related()` method
- [x] Implement `MockKnowledgeClient` for testing
- [x] Implement `KnowledgeRetriever`
  - [x] `retrieve_for_planning()`
  - [x] `retrieve_for_research()`
  - [x] `retrieve_for_analysis()`
  - [x] `retrieve_schema()`

### Phase 3: Core & Inference

#### 3.1 Core Models ✅ COMPLETE
- [x] Implement `MessageRole` enum (in inference/models.py)
- [x] Implement `Message` model with `to_openai_format()` (in inference/models.py)
- [x] Implement `ToolCall` model (in inference/models.py)
- [x] Implement `ToolResult` model (in core/models.py)
- [x] Implement `SubAgentResult` model (in core/models.py)
- [x] Implement `ExecutionPlan` and `PlanStep` models (in core/models.py)
- [x] Implement `AgentState` enum (in core/models.py)
- [x] Implement `StepStatus` enum (in core/models.py)

#### 3.2 Inference Module ✅
- [x] Implement `InferenceConfig` model
- [x] Implement `InferenceResponse` model
- [x] Implement `InferenceClient` (OpenAI-compatible)
  - [x] `complete()` method
  - [x] `stream()` method
  - [ ] Resource pooling integration
  - [ ] Integration with tracing
  - [ ] Retry logic
- [ ] Implement pool metrics

#### 3.3 Embedding Module ✅
- [x] Implement `EmbeddingProtocol` (protocol.py)
- [x] Implement `EmbeddingClient` with OpenAI-compatible API (client.py)
- [x] Implement `MockEmbeddingClient` for testing (client.py)
- [x] `embed()` and `embed_many()` methods
- [ ] Resource pooling (32 concurrent)
- [ ] Integration with tracing

#### 3.4 Session Module ✅ COMPLETE
- [x] Implement SQLAlchemy models (orm.py)
  - [x] `SessionModel` with user_id, agent_type, state, blackboard
  - [x] `MessageModel` with role, content, tool_calls
  - [x] `CheckpointModel` with thread_id, state, parent_checkpoint_id
- [x] Implement Pydantic models (models.py)
  - [x] `Session` with message management, state operations
  - [x] `MessageData` with `to_openai_format()`
  - [x] `Checkpoint` for state recovery
- [x] Implement `SessionStore` (store.py)
  - [x] `get()`, `get_or_create()`
  - [x] `save()`, `add_message()`, `get_messages()`
  - [x] `delete()`, `cleanup_expired()`
  - [x] `create_checkpoint()`, `get_latest_checkpoint()`
  - [x] `list_sessions()` with filtering
- [x] Implement `MockSessionStore` for testing
- [ ] Create Alembic migrations (deferred - manual table creation works)

### Phase 4: Sub-Agents & ReAct ✅ COMPLETE

#### 4.1 Blackboard ✅
- [x] Implement `Blackboard` class
  - [x] Variable storage with history
  - [x] Tool results with dual-form
  - [x] Findings collection
  - [x] `get_context_for_llm()` with truncation
  - [x] Pending interactions for HIL

#### 4.2 Sub-Agent Base ✅
- [x] Implement `SubAgentBase` abstract base class
- [x] Implement `SubAgentConfig` for configuration
- [x] Implement `_get_blackboard_context()` (isolated context)
- [x] Implement `_make_llm_call()` helper
- [x] Implement `_execute_with_retry()` with retry logic

#### 4.3 Sub-Agents Implementation ✅
- [x] Implement `PlannerSubAgent`
  - [x] System prompt
  - [x] Plan generation with JSON output
  - [x] `create_plan()` and `replan()` methods
  - [x] Fallback plan on parse failure
- [x] Implement `ResearcherSubAgent`
  - [x] System prompt
  - [x] Tool calling loop
  - [x] `research()` method with tool execution
  - [x] Findings collection to blackboard
- [x] Implement `AnalyzerSubAgent`
  - [x] System prompt
  - [x] `analyze()` and `compare()` methods
  - [x] Replan signal detection (`REPLAN_NEEDED:`)
- [x] Implement `ExecutorSubAgent`
  - [x] System prompt
  - [x] Tool execution with registration
  - [x] HIL interrupt support (destructive/high-value)
  - [x] Tool registry and execution
- [x] Implement `SynthesizerSubAgent`
  - [x] System prompt
  - [x] Final response generation
  - [x] `generate_suggestions()` method
  - [x] Multiple format types (markdown, json, plain, structured)

#### 4.4 ReAct Loop ✅
- [x] Sub-agents communicate via Blackboard (hub-and-spoke)
- [x] Replan support via AnalyzerSubAgent signal
- [x] Progress tracking via blackboard variables
- [x] Error handling in all sub-agents

### Phase 5: Tools & Agent

#### 5.1 Tools Module ✅ COMPLETE
- [x] Implement `RetentionStrategy` model
  - [x] `max_items`, `max_chars` for truncation
  - [x] `compact_fields` for selective field retention
  - [x] `should_compact()` and `compact()` methods
- [x] Implement `HILConfig` model
  - [x] `requires_confirmation` always-confirm mode
  - [x] `high_value_threshold` for value-based HIL
  - [x] `requires_confirmation_for()` method
- [x] Implement `ToolSpec` model with `to_openai_format()`
  - [x] `ToolParameter` with JSON Schema conversion
  - [x] `requires_hil_for()` method
  - [x] `compact_result()` method
- [x] Implement `@tool` decorator
  - [x] Parameter extraction from type hints
  - [x] Docstring parsing for descriptions
  - [x] Optional/required detection
  - [x] Array item type extraction
  - [x] `get_tool_spec()` and `is_tool()` helpers
- [x] Implement `ToolRegistry`
  - [x] Registration from decorated functions
  - [x] Registration from object methods (`register_all()`)
  - [x] Discovery by tags
  - [x] Permission validation
  - [x] OpenAI format conversion
- [x] Implement `ToolExecutor`
  - [x] Async and sync function support
  - [x] Timeout handling
  - [x] Permission validation
  - [x] Result compaction with retention strategy
  - [x] Parallel and sequential execution modes
  - [x] HIL requirement checking

#### 5.2 Base Agent ✅ COMPLETE
- [x] Implement `BaseAgent` class
  - [x] Auto-register decorated tools (via `_auto_register_tools()`)
  - [x] `handle_message()` with ReAct loop
  - [x] `handle_human_input()` for HIL
  - [x] Registration info methods (`get_registration_info()`)
  - [x] Integrated `ToolRegistry` and `ToolExecutor`
  - [x] `get_tools(ctx)` returns tools from registry with permission filtering
  - [x] Tool execution in `_execute_researcher` and `_execute_executor`
  - [x] HIL check before destructive tool execution

### Phase 6: Registry & Orchestrator ✅ COMPLETE

#### 6.1 Registry Module ✅
- [x] Implement `AgentInfo` model
  - [x] Identity fields (agent_id, name, description, version, team)
  - [x] Network fields (base_url, health_endpoint)
  - [x] Discovery fields (capabilities, domains, example_queries)
  - [x] Status fields (is_healthy, registered_at, last_heartbeat)
  - [x] `to_embedding_text()` method
  - [x] `to_routing_context()` method
- [x] Implement `RegistrySettings`
- [x] Implement `ensure_index()` for Redis Stack vector index
- [x] Implement `RegistryClient`
  - [x] `register()` - store agent + compute/store embedding
  - [x] `unregister()` - remove agent
  - [x] `heartbeat()` - refresh TTL
  - [x] `get()` - get agent by ID
  - [x] `discover()` - vector search for relevant agents
  - [x] `get_routing_context()` - LLM-friendly descriptions
  - [x] `list_all()` - list all registered agents
- [x] Implement `MockRegistryClient` (in-memory for testing without Redis Stack)
- [x] Implement `HeartbeatManager`

#### 6.2 Orchestrator Module ✅
- [x] Implement `OrchestratorSettings`
- [x] Implement `RoutingStrategy` enum (SINGLE, PARALLEL, SEQUENTIAL)
- [x] Implement `RoutingDecision` model
- [x] Implement `Orchestrator`
  - [x] `handle_request()` - main entry (stub)
  - [x] `_route()` - LLM or rule-based routing
  - [x] `_invoke_single()` - single agent (stub)
  - [x] `_invoke_parallel()` - parallel execution (stub)
  - [x] `_invoke_sequential()` - sequential execution (stub)
  - [x] `_synthesize()` - combine parallel results (stub)

#### 6.3 Demo & Testing ✅
- [x] Create `examples/demo.py` with 4 sample agents
- [x] Demo runs successfully with MockRegistryClient
- [x] Create `examples/purchasing_agent/` with FastAPI server and tools
- [x] Unit tests for AgentInfo serialization (7 tests)
- [x] Unit tests for MockRegistryClient (11 tests)
- [x] Unit tests for Auth module (21 tests)
- [ ] Integration tests for Redis Stack vector index (requires Redis Stack)
- [ ] Integration tests for semantic search
- [ ] Integration tests for orchestrator routing

### Phase 7: Transport & API

#### 7.1 Transport Module ✅ COMPLETE
- [x] Implement chat_contract message models (Pydantic)
  - [x] `AuthMessage`, `QueryMessage`, `HumanInputMessage`
  - [x] `AuthResponse`, `ProgressMessage`, `UIInteractionMessage`
  - [x] `MarkdownMessage`, `SuggestionsMessage`, `ErrorMessage`
- [x] Implement `parse_message()` and `serialize_message()` functions
- [x] Implement `MessageHandler` class
  - [x] Auth handling
  - [x] Query handling
  - [x] Human input handling
- [x] Implement `WebSocketServer`
  - [x] Connection state management (`ConnectionState` enum)
  - [x] Auth flow
  - [x] Query handling with streaming
  - [x] Human input handling
  - [x] Progress/Markdown/Suggestions streaming

#### 7.2 Agent API ✅ COMPLETE
- [x] Implement `AgentAPI` FastAPI wrapper
  - [x] `GET /health`
  - [x] `GET /capabilities`
  - [x] `POST /api/v1/query` (SSE streaming)
  - [x] `WebSocket /ws` (via WebSocketServer)
- [x] Implement startup/shutdown hooks
  - [x] Register on startup
  - [x] Start heartbeat
  - [x] Unregister on shutdown
- [x] Request/response models (`QueryRequest`, `QueryContext`, `HealthResponse`)

### Phase 8: Example & Documentation

#### 8.1 Purchasing Agent Example ✅
- [x] Create `examples/purchasing_agent/` structure
- [x] Implement `PurchasingAgent` class
  - [x] System prompt
  - [x] Domain tools (`search_po`, `get_po_details`, `analyze_spend`)
  - [x] Registration info
- [x] Implement `main.py` with FastAPI app
- [ ] Create example `.env`
- [ ] Create README.md

#### 8.2 Documentation
- [x] Update design document with implementation status
- [ ] Create API documentation
- [ ] Create deployment guide
- [ ] Create domain team onboarding guide

### Phase 9: Testing

#### 9.1 Unit Tests
- [ ] Settings tests
- [ ] Auth model tests
- [ ] Tracing decorator tests
- [ ] Tool decorator tests
- [ ] Model serialization tests

#### 9.2 Integration Tests
- [ ] KnowledgeClient (ContextForge) integration tests
- [ ] Inference client tests
- [ ] Session store tests
- [ ] Registry client tests (requires Redis Stack)

#### 9.3 End-to-End Tests
- [ ] Single agent flow tests
- [ ] Multi-agent orchestration tests
- [ ] WebSocket protocol tests

---

## Current Implementation Status

**Last Updated:** January 14, 2026

### Completed Components

| Component | Status | Files | Tests |
|-----------|--------|-------|-------|
| **Package Setup** | ✅ Complete | `pyproject.toml`, `README.md` | - |
| **Settings** | ✅ Complete | `settings/base.py`, `registry.py`, `orchestrator.py`, `embedding.py`, `inference.py` | - |
| **Registry Module** | ✅ Complete | `registry/models.py`, `client.py`, `mock_client.py`, `heartbeat.py` | 18 tests |
| **Orchestrator Module** | ✅ Complete | `orchestrator/models.py`, `orchestrator.py` | - |
| **Embedding Module** | ✅ Complete | `embedding/client.py`, `protocol.py` (OpenAI-compatible) | - |
| **Auth Module** | ✅ Complete | `auth/models.py`, `context.py` (`EnrichedUser`, `RequestContext`, `Locale`, `EntityContext`, `PageContext`) | 21 tests |
| **Inference Module** | ✅ Complete | `inference/client.py`, `models.py` (OpenAI-compatible with streaming) | - |
| **Tracing Module** | ✅ Complete | `tracing/client.py`, `context.py`, `decorators.py` (Langfuse integration) | 15 tests |
| **Knowledge Module** | ✅ Complete | `knowledge/client.py`, `models.py`, `retriever.py` (ContextForge integration) | 35 tests |
| **Core Module** | ✅ Complete | `core/agent.py`, `blackboard.py`, `models.py` (BaseAgent with ReAct) | 34 tests |
| **Sub-Agents** | ✅ Complete | `sub_agents/planner.py`, `researcher.py`, `analyzer.py`, `executor.py`, `synthesizer.py` | 27 tests |
| **Tools Module** | ✅ Complete | `tools/decorator.py`, `registry.py`, `executor.py`, `models.py` | 42 tests |
| **Session Module** | ✅ Complete | `session/models.py`, `store.py` (PostgreSQL persistence) | 29 tests |
| **Transport Module** | ✅ Complete | `transport/models.py`, `parser.py`, `handlers.py`, `server.py` (WebSocket) | 31 tests |
| **API Module** | ✅ Complete | `api/server.py`, `api/models.py` (FastAPI wrapper with SSE + WebSocket) | 24 tests |
| **Settings Module** | ✅ Complete | All settings classes + `Settings` aggregator + `get_settings()` | 15 tests |
| **Demo** | ✅ Working | `examples/demo.py` (4 sample agents, no Redis required) | - |
| **Example Agent** | ✅ Complete | `examples/purchasing_agent/agent.py`, `main.py` (FastAPI with 3 tools) | - |

**Total Tests: 291 passing** (run with `python -m pytest tests/unit -v`)

### File Structure

```
agentcore/
├── pyproject.toml
├── README.md
├── .venv/                          # Virtual environment
├── src/agentcore/
│   ├── __init__.py                 # Main exports
│   ├── settings/
│   │   ├── base.py                 # BaseAppSettings
│   │   ├── registry.py             # RegistrySettings
│   │   ├── orchestrator.py         # OrchestratorSettings
│   │   ├── embedding.py            # EmbeddingSettings
│   │   └── inference.py            # InferenceSettings
│   ├── registry/
│   │   ├── models.py               # AgentInfo
│   │   ├── client.py               # RegistryClient (Redis Stack)
│   │   ├── mock_client.py          # MockRegistryClient (in-memory)
│   │   └── heartbeat.py            # HeartbeatManager
│   ├── orchestrator/
│   │   ├── models.py               # RoutingStrategy, RoutingDecision
│   │   └── orchestrator.py         # Orchestrator
│   ├── embedding/
│   │   ├── protocol.py             # EmbeddingProtocol
│   │   └── client.py               # EmbeddingClient, MockEmbeddingClient
│   ├── inference/
│   │   ├── models.py               # Message, MessageRole, ToolCall, InferenceConfig, InferenceResponse
│   │   └── client.py               # InferenceClient (OpenAI-compatible)
│   ├── auth/
│   │   ├── models.py               # Permission, EnrichedUser, Locale, EntityContext, PageContext
│   │   └── context.py              # RequestContext (contextvars)
│   └── common/
│       └── __init__.py
├── examples/
│   ├── demo.py                     # Demo with 4 sample agents
│   └── purchasing_agent/
│       ├── agent.py                # PurchasingAgent with tools
│       └── main.py                 # FastAPI server
└── tests/
    └── unit/
        ├── test_auth.py            # 21 tests
        ├── test_mock_registry.py   # 11 tests
        └── test_registry_models.py # 7 tests
```

### Components Not Started

| Component | Priority | Description | Dependencies |
|-----------|----------|-------------|--------------|
| **Resource Pooling** | Low | Generic semaphore pool for inference/embedding rate limiting | - |
| **Common Utilities** | Low | `RetryConfig`, common exceptions | - |
| **AuthProvider Implementation** | Low | Token validation, FastAPI auth dependencies | - |

### Known Issues & Limitations

1. **Redis Stack Required**: Production `RegistryClient` requires Redis Stack with RediSearch module for vector search. Use `MockRegistryClient` for local development/testing.

2. **No Resource Pooling**: Inference and Embedding clients don't have rate limiting yet. Pool integration planned.

### Quick Start

```bash
# Setup
cd agentcore
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
python -m pytest tests/unit -v

# Run demo (no Redis required)
python -m examples.demo

# Run purchasing agent (needs INFERENCE_API_KEY for real LLM)
uvicorn examples.purchasing_agent.main:app --port 8001
```

### Next Steps (Recommended Order)

1. **Tracing Module** - Langfuse integration (`tracing/client.py`, `tracing/decorators.py`)
2. **Knowledge Module** - ContextForge integration (`knowledge/client.py`, `knowledge/models.py`)
3. **Core Agent Base** - `BaseAgent` with ReAct loop (`core/agent.py`, `core/blackboard.py`)
4. **Tools Module** - `@tool` decorator, `ToolRegistry` (`tools/decorator.py`, `tools/registry.py`)

---

## API Contracts

### 10.1 Agent Registration (Redis)

```json
// Key: agentcore:agents:{agent_id}
// TTL: 30 seconds (refreshed by heartbeat)
{
    "agent_id": "purchasing",
    "name": "Purchasing Agent",
    "description": "Handles purchase orders, vendors, and procurement",
    "base_url": "http://purchasing-agent:8000",
    "health_endpoint": "/health",
    "capabilities": ["search", "create", "update", "analyze"],
    "domains": ["po", "vendor", "catalog", "procurement"],
    "keywords": ["purchase", "po", "vendor", "buy", "procurement", "supplier"],
    "example_queries": [
        "Search for my purchase orders",
        "Create a PO for laptops",
        "Find vendors for office supplies"
    ],
    "version": "1.0.0",
    "team": "procurement-engineering",
    "registered_at": "2026-01-13T10:00:00Z",
    "last_heartbeat": "2026-01-13T10:05:00Z",
    "is_healthy": true
}
```

### 10.2 Agent Query API

```
POST /api/v1/query
Content-Type: application/json
Authorization: Bearer {user_token}
X-Request-ID: {request_id}
X-Session-ID: {session_id}

{
    "query": "Search for my purchase orders",
    "attachments": [],
    "context": {
        "user_id": 123,
        "session_id": "xxx",
        "request_id": "yyy",
        "locale": {"timezone": "America/Los_Angeles", "language": "en-US"},
        "entity": {"entity_id": 1, "name": "Acme Inc"},
        "page": {"module": "Purchasing"}
    },
    "stream": true
}

Response (streaming): newline-delimited JSON
{"type": "component", "payload": {"component": "progress", "data": {"status": "Thinking"}}}
{"type": "component", "payload": {"component": "progress", "data": {"status": "Searching"}}}
{"type": "markdown", "payload": "## Your Purchase Orders\n\n..."}
{"type": "suggestions", "payload": {"options": [...]}}
```

### 10.3 WebSocket Protocol (chat_contract)

See `docs/chat_contract.md` for full specification.

Key message types:
- UI → Agent: `auth`, `query`, `human_input`
- Agent → UI: `auth`, `suggestions`, `component`, `markdown`, `ui_field_options`

---

## Appendix

### A. Dependencies

```toml
# pyproject.toml
[project]
dependencies = [
    # Core
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    
    # Async
    "asyncio",
    "httpx>=0.25",
    
    # Web
    "fastapi>=0.100",
    "uvicorn>=0.23",
    "websockets>=11.0",
    
    # Database
    "sqlalchemy>=2.0",
    "asyncpg>=0.28",
    "alembic>=1.12",
    
    # Redis
    "redis>=5.0",
    
    # Tracing
    "langfuse>=2.0",
    
    # Utilities
    "python-dotenv>=1.0",
]
```

### B. Database Schema

```sql
-- migrations/001_initial.sql

CREATE TABLE agent_sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    state JSONB DEFAULT '{}',
    blackboard JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE INDEX idx_sessions_user_id ON agent_sessions(user_id);
CREATE INDEX idx_sessions_agent_type ON agent_sessions(agent_type);
CREATE INDEX idx_sessions_expires_at ON agent_sessions(expires_at);

CREATE TABLE agent_messages (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) REFERENCES agent_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT,
    name VARCHAR(100),
    tool_call_id VARCHAR(100),
    tool_calls JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_messages_session_id ON agent_messages(session_id);

CREATE TABLE agent_checkpoints (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) REFERENCES agent_sessions(id) ON DELETE CASCADE,
    thread_id VARCHAR(100) NOT NULL,
    checkpoint_id VARCHAR(100) NOT NULL,
    parent_checkpoint_id VARCHAR(100),
    state JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_checkpoints_session_id ON agent_checkpoints(session_id);
CREATE INDEX idx_checkpoints_thread_id ON agent_checkpoints(thread_id);
```

### C. Deployment

```yaml
# kubernetes/purchasing-agent.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: purchasing-agent
  namespace: agents
spec:
  replicas: 2
  selector:
    matchLabels:
      app: purchasing-agent
  template:
    metadata:
      labels:
        app: purchasing-agent
    spec:
      containers:
        - name: agent
          image: purchasing-agent:latest
          ports:
            - containerPort: 8000
          env:
            - name: APP_ENVIRONMENT
              value: production
            - name: REGISTRY_REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: redis-credentials
                  key: url
            # ... other env vars from ConfigMap/Secret
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: purchasing-agent
  namespace: agents
spec:
  selector:
    app: purchasing-agent
  ports:
    - port: 8000
      targetPort: 8000
```

---

**Document End**

*Last Updated: January 13, 2026*
*Author: AgentCore Design Team*
