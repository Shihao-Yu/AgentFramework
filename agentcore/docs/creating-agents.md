# Creating Domain Agents

## Quick Example

```python
from agentcore import BaseAgent, RequestContext

class MyAgent(BaseAgent):
    agent_id = "my_agent"
    name = "My Agent"
    description = "Handles my domain tasks"
    capabilities = ["search", "create"]
    domains = ["my_domain"]
    example_queries = ["Search for items", "Create entry"]
    
    def get_system_prompt(self, ctx: RequestContext) -> str:
        return """You are My Agent. Be helpful and clear."""
    
    def get_tools(self) -> list[dict]:
        return [{
            "type": "function",
            "function": {
                "name": "search_items",
                "description": "Search for items",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }]
```

## Step-by-Step

### 1. Define Identity

```python
class PurchasingAgent(BaseAgent):
    agent_id = "purchasing"
    name = "Purchasing Agent"
    description = """Purchasing expert: PO management, vendor lookup, spend analysis"""
    version = "1.0.0"
    team = "Procurement"
    capabilities = ["search", "create", "approve", "analyze"]
    domains = ["purchase_order", "vendor", "catalog"]
    example_queries = [
        "Find PO 12345",
        "Create purchase order for office supplies",
    ]
```

### 2. System Prompt

```python
def get_system_prompt(self, ctx: RequestContext) -> str:
    return f"""You are the Purchasing Agent.
    
User: {ctx.user.display_name}
Can create POs: {ctx.user.has_permission(Permission.PO_CREATE)}

Help with PO search, creation, and spend analysis."""
```

### 3. Tools

```python
def get_tools(self) -> list[dict]:
    return [{
        "type": "function",
        "function": {
            "name": "search_purchase_orders",
            "description": "Search POs by number, vendor, or status",
            "parameters": {
                "type": "object",
                "properties": {
                    "po_number": {"type": "string"},
                    "vendor_name": {"type": "string"},
                    "status": {"type": "string", "enum": ["draft", "approved"]},
                },
            },
        },
    }]
```

### 4. FastAPI Server

```python
from fastapi import FastAPI
from agentcore import RequestContext, InferenceClient, MockKnowledgeClient
from agentcore.settings.inference import InferenceSettings

app = FastAPI()
agent = PurchasingAgent(
    inference=InferenceClient(InferenceSettings()),
    knowledge=MockKnowledgeClient(),
)

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/v1/query")
async def query(request: dict):
    ctx = RequestContext.for_system()
    chunks = []
    async for chunk in agent.handle_message(ctx, request["query"]):
        if chunk["type"] == "markdown":
            chunks.append(chunk["payload"])
    return {"response": "".join(chunks)}
```

### 5. Run

```bash
export INFERENCE_API_KEY=sk-...
uvicorn my_agent:app --port 8001

curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Find PO 12345"}'
```

## Using Sub-Agents Directly

```python
from agentcore import PlannerSubAgent, ResearcherSubAgent, AnalyzerSubAgent

planner = PlannerSubAgent(inference=inference_client, retriever=retriever)
plan = await planner.create_plan(ctx, query="Compare vendors", system_prompt="...")

analyzer = AnalyzerSubAgent(inference=inference_client)
result = await analyzer.compare(ctx, items=[vendor_a, vendor_b], criteria=["price"])
```

## Human-in-the-Loop

The `ExecutorSubAgent` auto-requires approval for:
- Destructive ops (delete, remove, cancel)
- High-value transactions (>10000)

Custom rules:
```python
class CustomExecutor(ExecutorSubAgent):
    def _requires_hil(self, tool_name: str, arguments: dict) -> bool:
        if tool_name == "approve_po":
            return True
        return super()._requires_hil(tool_name, arguments)
```

## Project Structure

```
my_agent/
├── agent.py    # Agent class
├── main.py     # FastAPI server
└── tests/
```

## Checklist

- [ ] Unique `agent_id`
- [ ] Detailed `description` for discovery
- [ ] Realistic `example_queries`
- [ ] Tools defined in `get_tools()`
- [ ] FastAPI server with `/health` endpoint
- [ ] Unit tests
