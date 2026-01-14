# API Reference

## Registry

### AgentInfo

```python
from agentcore import AgentInfo

agent = AgentInfo(
    agent_id="purchasing",
    name="Purchasing Agent",
    description="Handles POs, vendors, spend analysis",
    base_url="http://localhost:8001",
    capabilities=["search", "create"],
    domains=["purchase_order"],
    example_queries=["Find PO 12345"],
)
```

### RegistryClient / MockRegistryClient

```python
from agentcore import MockRegistryClient, MockEmbeddingClient

registry = MockRegistryClient(MockEmbeddingClient())

await registry.register(agent)
await registry.unregister("purchasing")
await registry.heartbeat("purchasing")
agent = await registry.get("purchasing")
agents = await registry.discover("purchase order", top_k=5)
```

---

## Orchestrator

```python
from agentcore import Orchestrator, RoutingStrategy, RoutingDecision
from agentcore.settings.orchestrator import OrchestratorSettings

orchestrator = Orchestrator(registry, inference_client, OrchestratorSettings())
decision = await orchestrator.route(query, agents)
# decision.strategy: SINGLE | PARALLEL | SEQUENTIAL
# decision.agents: ["purchasing", "payables"]
```

---

## Auth

### EnrichedUser

```python
from agentcore import EnrichedUser, Permission

user = EnrichedUser(
    user_id=123,
    username="jdoe",
    email="jdoe@example.com",
    display_name="John Doe",
    entity_id=1,
    entity_name="Acme Inc",
    permissions=frozenset([Permission.BUYER, Permission.PO_CREATE]),
)

user.has_permission(Permission.BUYER)  # True
user.has_any_permission(Permission.ADMIN, Permission.BUYER)  # True

EnrichedUser.anonymous()
EnrichedUser.system()
```

### RequestContext

```python
from agentcore import RequestContext

ctx = RequestContext.create(user=user, session_id="session-123")
RequestContext.current()          # Returns ctx or None
RequestContext.require_current()  # Returns ctx or raises
RequestContext.for_system()
RequestContext.for_anonymous()
```

---

## Inference

### Message

```python
from agentcore import Message, MessageRole

Message(role=MessageRole.USER, content="Hello")
Message.system("You are helpful")
Message.user("Hello")
Message.assistant("Hi")
Message.tool(tool_call_id="123", content="result", name="search")
```

### InferenceClient

```python
from agentcore import InferenceClient, InferenceConfig
from agentcore.settings.inference import InferenceSettings

client = InferenceClient(InferenceSettings())

response = await client.complete(messages, tools=[], config=InferenceConfig())
async for chunk in client.stream(messages):
    print(chunk.content)
```

### InferenceResponse

```python
response.content      # Response text
response.tool_calls   # List of ToolCall
response.has_tool_calls
response.to_message()
```

---

## Embedding

```python
from agentcore import EmbeddingClient, MockEmbeddingClient

client = EmbeddingClient(EmbeddingSettings())
vector = await client.embed("text")
vectors = await client.embed_many(["text1", "text2"])

mock = MockEmbeddingClient(dimension=1536)
```

---

## Prompts

```python
from agentcore.prompts import get_prompt_registry

prompts = get_prompt_registry()
compiled = prompts.get("orchestrator-router", agent_descriptions="...")
template = prompts.get_template("agent-planner")
```

**Available prompts:**
- `orchestrator-router` - Variables: `agent_descriptions`
- `agent-planner` - Variables: `query`, `knowledge_context`, `blackboard_context`, `replan_reason`

---

## Tracing

```python
from agentcore import TracingClient, TraceContext, trace_agent, trace_tool

client = TracingClient(TracingSettings())
trace_ctx = client.start_trace(ctx, name="handle_message", agent_id="purchasing")
client.end_trace(trace_ctx, output="response")

@trace_agent("method_name")
async def method(ctx, data): ...

@trace_tool("tool_id")
async def tool(ctx, params): ...
```

---

## Knowledge

```python
from agentcore import KnowledgeClient, KnowledgeRetriever, KnowledgeBundle

client = KnowledgeClient(KnowledgeSettings())
retriever = KnowledgeRetriever(client)

bundle = await retriever.retrieve_for_planning(ctx, query)
context = bundle.to_prompt_context(max_chars=8000)
```

---

## Core

### BaseAgent

```python
from agentcore import BaseAgent

class MyAgent(BaseAgent):
    agent_id = "my_agent"
    name = "My Agent"
    description = "..."
    capabilities = ["search"]
    domains = ["my_domain"]
    
    def get_system_prompt(self, ctx): return "..."
    def get_tools(self): return [...]

async for chunk in agent.handle_message(ctx, "query"):
    # {"type": "markdown", "payload": "text"}
    pass
```

### Blackboard

```python
from agentcore import Blackboard

bb = Blackboard.create(ctx, query="...")
bb.set("key", value, source="researcher")
bb.get("key")
bb.add_tool_result("call_id", "tool_name", result)
bb.add_finding(source="analyzer", content="...", confidence=0.9)
bb.get_context_for_llm(max_tokens=8000)
```

### ExecutionPlan

```python
from agentcore import ExecutionPlan, PlanStep

plan = ExecutionPlan(query="...", goal="...", steps=[
    PlanStep(id="step_1", description="...", sub_agent="researcher", instruction="...")
])
plan.current_step
plan.completed_steps
plan.progress_percent
```

---

## Sub-Agents

### PlannerSubAgent

```python
from agentcore import PlannerSubAgent

planner = PlannerSubAgent(inference, retriever)
plan = await planner.create_plan(ctx, query, system_prompt)
plan = await planner.replan(ctx, current_plan, reason, system_prompt, blackboard)
```

### ResearcherSubAgent

```python
from agentcore import ResearcherSubAgent

researcher = ResearcherSubAgent(inference, retriever, tools=[...])
result = await researcher.execute(ctx, blackboard, step, system_prompt)
```

### AnalyzerSubAgent

```python
from agentcore import AnalyzerSubAgent

analyzer = AnalyzerSubAgent(inference, retriever)
result = await analyzer.analyze(ctx, query, data, system_prompt)
result = await analyzer.compare(ctx, items, criteria, system_prompt)
```

### ExecutorSubAgent

```python
from agentcore import ExecutorSubAgent

executor = ExecutorSubAgent(inference, tool_functions={"create_po": fn}, tools=[...])
result = await executor.execute(ctx, blackboard, step, system_prompt)
# If HIL required: {"status": "awaiting_approval", "interaction_id": "..."}
```

### SynthesizerSubAgent

```python
from agentcore import SynthesizerSubAgent

synthesizer = SynthesizerSubAgent(inference, retriever)
response = await synthesizer.synthesize(ctx, query, findings, system_prompt)
suggestions = await synthesizer.generate_suggestions(ctx, query, response, system_prompt)
```
