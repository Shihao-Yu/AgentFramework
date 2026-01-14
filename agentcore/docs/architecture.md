# AgentCore Architecture

This document explains how AgentCore works and how its components fit together.

## Overview

AgentCore is an enterprise agent framework designed for **50+ agents** working together. The key innovation is **semantic agent discovery** - finding relevant agents via vector similarity instead of hardcoded routing.

## High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              USER REQUEST                                   │
│                           "Compare PO and Invoice"                          │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         ORCHESTRATOR                                 │   │
│  │                                                                      │   │
│  │  1. Embed Query                                                      │   │
│  │  2. Vector Search (find top 5 relevant agents)                       │   │
│  │  3. LLM Router (decide routing strategy)                             │   │
│  │  4. Invoke Agent(s)                                                  │   │
│  │  5. Synthesize Response (if multiple agents)                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│               ┌───────────────────┴───────────────────┐                    │
│               ▼                                       ▼                    │
│  ┌─────────────────────┐                 ┌─────────────────────┐          │
│  │   Purchasing Agent  │                 │   Payables Agent    │          │
│  │                     │                 │                     │          │
│  │  ┌─────────────┐    │                 │  ┌─────────────┐    │          │
│  │  │  ReAct Loop │    │                 │  │  ReAct Loop │    │          │
│  │  │  ┌────────┐ │    │                 │  │  ┌────────┐ │    │          │
│  │  │  │Planner │ │    │                 │  │  │Planner │ │    │          │
│  │  │  │Research│ │    │                 │  │  │Research│ │    │          │
│  │  │  │Analyze │ │    │                 │  │  │Analyze │ │    │          │
│  │  │  │Execute │ │    │                 │  │  │Execute │ │    │          │
│  │  │  │Synthsz │ │    │                 │  │  │Synthsz │ │    │          │
│  │  │  └────────┘ │    │                 │  │  └────────┘ │    │          │
│  │  └─────────────┘    │                 │  └─────────────┘    │          │
│  │                     │                 │                     │          │
│  │  Domain Tools       │                 │  Domain Tools       │          │
│  └─────────────────────┘                 └─────────────────────┘          │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       SHARED SERVICES                                │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │   │
│  │  │ContextForge │ │  Inference  │ │   Langfuse  │ │ Redis Stack │    │   │
│  │  │ (Knowledge) │ │   (LLM)     │ │  (Tracing)  │ │ (Registry)  │    │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Registry (Agent Discovery)

The registry stores agent information and enables semantic discovery.

**Components:**
- `AgentInfo` - Agent registration data (ID, description, capabilities, domains)
- `RegistryClient` - Redis Stack client with vector search
- `MockRegistryClient` - In-memory client for testing
- `HeartbeatManager` - Keeps agents alive via TTL refresh

**How Discovery Works:**
1. Each agent registers with an embedding of its description + capabilities
2. When a query arrives, it's embedded
3. Vector similarity search finds the top N most relevant agents
4. LLM router decides which agent(s) to invoke

```python
# Registration creates embedding from this text:
text = f"{agent.name}: {agent.description}. {', '.join(agent.capabilities)}"
embedding = await embedding_client.embed(text)
```

### 2. Prompt Management (Langfuse)

Prompts are managed via Langfuse with local fallbacks for resilience.

**Components:**
- `PromptRegistry` - Fetches prompts from Langfuse, falls back to local
- `fallbacks.py` - Hardcoded prompts used when Langfuse unavailable

**Template Syntax (Mustache-style):**
- `{{variable}}` - Simple substitution
- `{{#var}}content{{/var}}` - Conditional block (if truthy)
- `{{^var}}content{{/var}}` - Inverted block (if falsy)

**Available Prompts:**
| Name | Variables | Used By |
|------|-----------|---------|
| `orchestrator-router` | `agent_descriptions` | Orchestrator |
| `agent-planner` | `query`, `knowledge_context`, `blackboard_context`, `replan_reason` | Planner |

**Usage:**
```python
from agentcore.prompts import get_prompt_registry

prompts = get_prompt_registry()
router_prompt = prompts.get(
    "orchestrator-router",
    agent_descriptions="- purchasing: Handles POs\n- payables: Handles invoices"
)
```

**Why Langfuse + Fallbacks:**
- Edit prompts in production without code changes
- A/B testing and version control via Langfuse
- System still works if Langfuse is down

### 3. Orchestrator (Query Routing)

The orchestrator decides how to route queries across agents.

**Routing Strategies:**
- `SINGLE` - One agent handles the query
- `PARALLEL` - Multiple agents work independently (e.g., "Compare PO with invoice")
- `SEQUENTIAL` - One agent's output feeds into another

**Flow:**
```python
# 1. Discover relevant agents
agents = await registry.discover(query, top_k=5)

# 2. Route to appropriate agent(s)
routing = await orchestrator.route(query, agents)
# Returns: RoutingDecision(strategy=PARALLEL, agents=["purchasing", "payables"])

# 3. Invoke agent(s) based on strategy
if routing.strategy == RoutingStrategy.SINGLE:
    result = await invoke_single(agents[0], query)
elif routing.strategy == RoutingStrategy.PARALLEL:
    results = await asyncio.gather(*[invoke(a, query) for a in agents])
    result = await synthesize(results)
```

### 4. BaseAgent (ReAct Loop)

Each domain agent extends `BaseAgent` which provides the ReAct (Reason + Act) loop.

**Sub-Agents:**
- **PlannerSubAgent** - Decomposes query into execution plans with step-by-step instructions
- **ResearcherSubAgent** - Gathers information using tools and knowledge base
- **AnalyzerSubAgent** - Analyzes data, makes comparisons, can trigger replanning
- **ExecutorSubAgent** - Performs actions (create, update, delete) with HIL support
- **SynthesizerSubAgent** - Generates final user-facing response and follow-up suggestions

**Sub-Agent Architecture:**
```
┌─────────────────────────────────────────────────────────────────┐
│                        BaseAgent                                 │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                     Blackboard                           │    │
│  │  ┌─────────────┬─────────────┬─────────────┐            │    │
│  │  │ Variables   │  Findings   │ Tool Results│            │    │
│  │  └─────────────┴─────────────┴─────────────┘            │    │
│  │  ┌─────────────┬─────────────┐                          │    │
│  │  │   Plan      │ Pending HIL │                          │    │
│  │  └─────────────┴─────────────┘                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│         ▲               ▲               ▲               ▲       │
│         │               │               │               │       │
│  ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴────┐ │
│  │   Planner   │ │ Researcher  │ │  Analyzer   │ │ Executor  │ │
│  │             │ │             │ │             │ │   (HIL)   │ │
│  │  Creates    │ │  Gathers    │ │  Analyzes   │ │  Executes │ │
│  │  Plans      │ │  Info       │ │  Data       │ │  Tools    │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
│         │                                               │       │
│         └───────────────────┬───────────────────────────┘       │
│                             ▼                                   │
│                   ┌─────────────────┐                           │
│                   │   Synthesizer   │                           │
│                   │                 │                           │
│                   │ Generates final │                           │
│                   │ response + tips │                           │
│                   └─────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

**Blackboard Pattern:**
Sub-agents communicate via a shared `Blackboard` (hub-and-spoke, not peer-to-peer):

The blackboard contains:
- **Variables** - Key-value store with history tracking
- **Tool results** - Results from tool executions (with compact form for context management)
- **Findings** - Insights discovered by sub-agents with source and confidence
- **Pending interactions** - Human-in-the-loop prompts awaiting user response
- **Execution Plan** - Current plan with steps and their status

**Human-in-the-Loop (HIL):**
The ExecutorSubAgent supports HIL for sensitive actions:
- Destructive operations (delete, remove, cancel) require approval
- High-value transactions above configurable thresholds
- Custom HIL rules can be implemented per agent

### 5. Knowledge Module (RAG)

Integrates with ContextForge for knowledge retrieval.

**Components:**
- `KnowledgeClient` - HTTP client to ContextForge API
- `KnowledgeRetriever` - High-level retrieval for sub-agents
- `KnowledgeBundle` - Organized knowledge by type (schemas, playbooks, FAQs)

**Knowledge Types:**
- `SCHEMA` - Entity definitions
- `PLAYBOOK` - Step-by-step guides
- `CONCEPT` - High-level concepts
- `FAQ` - Frequently asked questions
- `ENTITY` - Entity instances

```python
# Retrieve knowledge for planning
bundle = await retriever.retrieve_for_planning(ctx, query)

# Get formatted context for LLM
context = bundle.to_prompt_context(max_chars=8000)
```

### 6. Inference Module (LLM)

OpenAI-compatible client for LLM inference.

**Features:**
- Streaming support
- Tool/function calling
- Configurable via environment variables
- Works with any OpenAI-compatible API

```python
response = await inference.complete(
    messages=[Message.system(prompt), Message.user(query)],
    tools=tools,
    config=InferenceConfig(temperature=0.7),
)
```

### 7. Auth Module (User Context)

User context flows through everything as a first-class citizen.

**Components:**
- `EnrichedUser` - User identity with permissions
- `RequestContext` - Request-scoped context (user, session, locale)
- `Permission` - Permission enum

**contextvars Integration:**
```python
# Set context
ctx = RequestContext.create(user=user, session_id="...", request_id="...")

# Access anywhere
current = RequestContext.current()  # None if not set
required = RequestContext.require_current()  # Raises if not set
```

### 8. Tracing Module (Observability)

Langfuse integration for tracing all operations.

**Components:**
- `TracingClient` - Langfuse client wrapper
- `TraceContext` - Request-scoped trace state
- Decorators: `@trace_agent`, `@trace_tool`, `@trace_inference`, `@trace_knowledge`

**What Gets Traced:**
- Agent decisions (which sub-agent, why)
- LLM inference calls (input, output, tokens)
- Tool executions
- Knowledge retrievals

## Data Flow

### Query Processing Flow

```
1. User sends query
   │
2. Orchestrator embeds query
   │
3. Vector search finds relevant agents (top 5)
   │
4. LLM router decides routing strategy
   │
5. Invoke selected agent(s)
   │
   ├─► Single Agent Path:
   │   └─► Agent runs ReAct loop
   │       └─► Planner creates plan
   │       └─► Sub-agents execute steps
   │       └─► Synthesizer generates response
   │
   └─► Multi-Agent Path:
       └─► Agents run in parallel/sequential
       └─► Orchestrator synthesizes results
   │
6. Stream response to user
```

### Agent Internal Flow

```
handle_message(ctx, query)
   │
   ├─► Create Blackboard
   │
   ├─► Planning Phase
   │   └─► Retrieve knowledge (playbooks)
   │   └─► LLM generates plan (steps)
   │
   ├─► Execution Phase (for each step)
   │   ├─► Researcher: gather info, call tools
   │   ├─► Analyzer: analyze data
   │   ├─► Executor: perform actions
   │   └─► Check for replan signals
   │
   ├─► Synthesis Phase
   │   └─► Synthesizer generates response
   │   └─► Generate follow-up suggestions
   │
   └─► Stream response chunks
```

## Module Structure

```
agentcore/
├── src/agentcore/
│   ├── settings/           # Pydantic Settings (all config)
│   │   ├── base.py         # BaseAppSettings
│   │   ├── registry.py     # RegistrySettings
│   │   ├── orchestrator.py # OrchestratorSettings
│   │   ├── embedding.py    # EmbeddingSettings
│   │   ├── inference.py    # InferenceSettings
│   │   ├── knowledge.py    # KnowledgeSettings
│   │   ├── tracing.py      # TracingSettings
│   │   └── agent.py        # AgentSettings
│   │
│   ├── prompts/            # Prompt Management
│   │   ├── fallbacks.py    # Hardcoded fallback prompts
│   │   └── registry.py     # PromptRegistry (Langfuse + fallbacks)
│   │
│   ├── registry/           # Agent Registration & Discovery
│   │   ├── models.py       # AgentInfo
│   │   ├── client.py       # RegistryClient (Redis Stack)
│   │   ├── mock_client.py  # MockRegistryClient
│   │   └── heartbeat.py    # HeartbeatManager
│   │
│   ├── orchestrator/       # Query Routing
│   │   ├── models.py       # RoutingStrategy, RoutingDecision
│   │   └── orchestrator.py # Orchestrator
│   │
│   ├── embedding/          # Embedding Service
│   │   ├── protocol.py     # EmbeddingProtocol
│   │   └── client.py       # EmbeddingClient, MockEmbeddingClient
│   │
│   ├── inference/          # LLM Inference
│   │   ├── models.py       # Message, ToolCall, InferenceResponse
│   │   └── client.py       # InferenceClient
│   │
│   ├── auth/               # User Context
│   │   ├── models.py       # Permission, EnrichedUser, Locale
│   │   └── context.py      # RequestContext
│   │
│   ├── tracing/            # Observability
│   │   ├── context.py      # TraceContext
│   │   ├── client.py       # TracingClient, MockTracingClient
│   │   └── decorators.py   # @trace_* decorators
│   │
│   ├── knowledge/          # RAG Integration
│   │   ├── models.py       # KnowledgeType, KnowledgeNode, KnowledgeBundle
│   │   ├── client.py       # KnowledgeClient, MockKnowledgeClient
│   │   └── retriever.py    # KnowledgeRetriever
│   │
│   ├── core/               # Agent Infrastructure
│   │   ├── models.py       # ExecutionPlan, PlanStep, SubAgentResult
│   │   ├── blackboard.py   # Blackboard
│   │   └── agent.py        # BaseAgent
│   │
│   └── sub_agents/         # Specialized Sub-Agents
│       ├── base.py         # SubAgentBase, SubAgentConfig
│       ├── planner.py      # PlannerSubAgent
│       ├── researcher.py   # ResearcherSubAgent
│       ├── analyzer.py     # AnalyzerSubAgent
│       ├── executor.py     # ExecutorSubAgent
│       └── synthesizer.py  # SynthesizerSubAgent
```

## Design Principles

### 1. User Context is First-Class
Every request carries `RequestContext` with user info, permissions, and session data. This enables:
- Permission checking in tools
- User-specific knowledge retrieval
- Audit logging

### 2. No Hardcoding
All configuration via Pydantic Settings with environment variables. No magic strings or hardcoded values.

### 3. Semantic Discovery
Vector search finds relevant agents instead of:
- Keyword matching
- Hardcoded routing tables
- Complex graph edges

### 4. Hub-and-Spoke Sub-Agents
Sub-agents communicate through Blackboard, not peer-to-peer. This is:
- Simpler to debug
- Easier to trace
- More maintainable

### 5. Graceful Degradation
Components work without their dependencies:
- Prompts work without Langfuse (fallback to local prompts)
- Tracing works without Langfuse credentials
- Registry has MockRegistryClient for testing
- Knowledge has MockKnowledgeClient for testing

### 6. Centralized Prompt Management
All LLM prompts are managed via Langfuse:
- Edit prompts in production without code deploys
- Version control and A/B testing built-in
- Local fallbacks ensure system works if Langfuse is down
- Mustache-style templating with `{{variables}}`

## Production Deployment

For production:
1. Use `RegistryClient` with Redis Stack (not MockRegistryClient)
2. Configure Langfuse for tracing and prompt management
3. Create prompts in Langfuse: `orchestrator-router`, `agent-planner`
4. Point to your ContextForge instance
5. Set up proper authentication

See the [Deployment Guide](../docs/agentcore_design.md#appendix) for Kubernetes manifests.
