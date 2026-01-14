# Context RAG Pipeline: How ContextForge Assembles Context for AI Agents

This document explains how ContextForge's Context Service retrieves and assembles knowledge for AI agents via the `/api/context` endpoint.

## Overview

The Context RAG (Retrieval-Augmented Generation) pipeline:

1. **Finds entry points** - Hybrid search for relevant knowledge nodes
2. **Expands context** - Graph traversal to find related nodes
3. **Collects entities** - Gathers business entities mentioned
4. **Applies token budget** - Fits context within LLM limits
5. **Returns structured response** - Formatted for AI agent consumption

```
                                    +------------------+
                                    |  Agent Query     |
                                    | "How do I handle |
                                    |  refund requests"|
                                    +--------+---------+
                                             |
                                             v
+----------------+              +------------------------+
| Knowledge      |<-------------|  1. Entry Point Search |
| Nodes          |              |     - Hybrid search    |
| (FAQ, Playbook)|              |     - BM25 + Vector    |
+----------------+              +------------------------+
                                             |
                                             v
+----------------+              +------------------------+
| Knowledge      |<-------------|  2. Graph Expansion    |
| Graph          |              |     - BFS traversal    |
| (Edges)        |              |     - Max depth: 2     |
+----------------+              +------------------------+
                                             |
                                             v
+----------------+              +------------------------+
| Entity         |<-------------|  3. Entity Collection  |
| Nodes          |              |     - Related entities |
+----------------+              +------------------------+
                                             |
                                             v
                                +------------------------+
                                |  4. Token Budget       |
                                |     - 60% entry points |
                                |     - 30% context      |
                                |     - 10% entities     |
                                +------------------------+
                                             |
                                             v
                                +------------------------+
                                |  Structured Response   |
                                |  - entry_points[]      |
                                |  - context[]           |
                                |  - entities[]          |
                                |  - stats{}             |
                                +------------------------+
```

## The Context Endpoint

### Request

```bash
POST /api/context
Content-Type: application/json

{
  "query": "How do I process a refund request?",
  "tenant_ids": ["purchasing", "shared"],
  "entry_types": ["faq", "playbook", "permission_rule"],
  "entry_limit": 10,
  "expand": true,
  "max_depth": 2,
  "context_limit": 50,
  "include_entities": true,
  "include_schemas": false,
  "include_examples": false,
  "max_tokens": 8000,
  "token_model": "gpt-4"
}
```

### Response

```json
{
  "entry_points": [
    {
      "id": 42,
      "node_type": "faq",
      "title": "How to process refunds",
      "summary": "Step-by-step refund processing guide",
      "content": {"question": "...", "answer": "..."},
      "tags": ["refunds", "customer-service"],
      "score": 0.92,
      "match_source": "hybrid"
    }
  ],
  "context": [
    {
      "id": 55,
      "node_type": "playbook",
      "title": "Refund Approval Workflow",
      "summary": "Approval chain for refunds over $100",
      "content": {"steps": [...]},
      "tags": ["workflow", "approvals"],
      "score": 0.75,
      "distance": 1,
      "path": [42, 55],
      "edge_type": "related"
    }
  ],
  "entities": [
    {
      "id": 101,
      "title": "Refund Request",
      "entity_path": "orders.refund_requests",
      "related_schemas": ["orders", "payments"]
    }
  ],
  "stats": {
    "nodes_searched": 100,
    "nodes_expanded": 15,
    "max_depth_reached": 2,
    "entry_points_found": 5,
    "context_nodes_found": 12,
    "total_tokens": 6500,
    "tokens_used": {
      "entry_points": 4200,
      "context_nodes": 1800,
      "entities": 500
    }
  }
}
```

## Step 1: Entry Point Search

Entry points are the primary knowledge nodes that match the user's query.

### Hybrid Search

The system uses hybrid search combining BM25 (keyword) and vector (semantic) search:

```python
# From context_service.py:_find_entry_points()

search_results = await self.node_service.hybrid_search(
    query_text=request.query,
    user_tenant_ids=request.tenant_ids,
    node_types=node_types,  # FAQ, Playbook, etc.
    limit=request.entry_limit,
)
```

### Default Entry Types

If not specified, these node types are searched:

| Node Type | Description | Use Case |
|-----------|-------------|----------|
| `FAQ` | Question/answer pairs | Direct answers |
| `PLAYBOOK` | Step-by-step procedures | How-to guides |
| `PERMISSION_RULE` | Access control rules | Authorization |
| `CONCEPT` | Domain concepts | Background knowledge |

Optional types (enabled via flags):
- `SCHEMA_INDEX` / `SCHEMA_FIELD` - Database schemas (`include_schemas=true`)
- `EXAMPLE` - Q&A examples (`include_examples=true`)

### Match Source Detection

Each result indicates how it was matched:

```python
# From context_service.py:_find_entry_points()

if result.bm25_score > 0 and result.vector_score == 0:
    match_source = "bm25"      # Keyword match only
elif result.vector_score > 0 and result.bm25_score == 0:
    match_source = "vector"    # Semantic match only
else:
    match_source = "hybrid"    # Both matched
```

## Step 2: Graph Expansion

After finding entry points, the system traverses the knowledge graph to find related context.

### Breadth-First Traversal

```python
# From context_service.py:_expand_context()

# Load graph for tenant(s)
await self.graph_service.load_graph(request.tenant_ids)

# BFS from entry points
current_level = set(entry_ids)

for depth in range(1, request.max_depth + 1):
    next_level = set()
    
    for node_id in current_level:
        # Get neighbors (both directions)
        successors = set(graph.successors(node_id))
        predecessors = set(graph.predecessors(node_id))
        neighbors = (successors | predecessors) - visited
        
        for neighbor_id in neighbors:
            # Check node type filter
            if neighbor_type not in expansion_types:
                continue
            
            # Add to context
            context_nodes.append(ContextNodeResult(
                id=neighbor_id,
                distance=depth,
                path=paths[node_id] + [neighbor_id],
                edge_type=edge_type,
                score=base_score * edge_weight,
            ))
            
            next_level.add(neighbor_id)
    
    current_level = next_level
```

### Scoring

Context nodes are scored based on:

1. **Distance decay**: `base_score = 1.0 / (depth + 1)`
2. **Edge weight**: Multiplied by edge weight (default 1.0)

| Distance | Base Score | With 0.8 Edge Weight |
|----------|------------|----------------------|
| 1 hop | 0.50 | 0.40 |
| 2 hops | 0.33 | 0.27 |
| 3 hops | 0.25 | 0.20 |

### Edge Types

The graph contains these edge types:

| Edge Type | Direction | Description |
|-----------|-----------|-------------|
| `RELATED` | Bidirectional | General relationship |
| `PARENT` | Directional | Hierarchical (parent -> child) |
| `EXAMPLE_OF` | Directional | Example -> Schema |
| `SHARED_TAG` | Bidirectional | Auto-generated from tags |
| `SIMILAR` | Bidirectional | Auto-generated from embeddings |

## Step 3: Entity Collection

Entities are business objects mentioned in or related to the context.

```python
# From context_service.py:_collect_entities()

result = await session.execute(
    text("""
        SELECT DISTINCT n.id, n.title, n.content
        FROM knowledge_nodes n
        WHERE n.node_type = 'entity'
          AND n.tenant_id = ANY(:tenant_ids)
          AND (
            n.id = ANY(:node_ids)
            OR EXISTS (
              SELECT 1 FROM knowledge_edges e
              WHERE (e.source_id = n.id AND e.target_id = ANY(:node_ids))
                 OR (e.target_id = n.id AND e.source_id = ANY(:node_ids))
            )
          )
        LIMIT 10
    """),
    {"node_ids": all_node_ids, "tenant_ids": tenant_ids}
)
```

### Entity Result

```python
class EntityResult(BaseModel):
    id: int
    title: str                    # "Refund Request"
    entity_path: str              # "orders.refund_requests"
    related_schemas: List[str]    # ["orders", "payments"]
```

## Step 4: Token Budget Management

When `max_tokens` is specified, the system allocates tokens across categories.

### Budget Allocation

```python
# From context_service.py:_apply_token_budget()

# Default allocation: 60/30/10 split
entry_budget = int(max_tokens * 0.60)    # 4800 of 8000
context_budget = int(max_tokens * 0.30)  # 2400 of 8000
entity_budget = int(max_tokens * 0.10)   # 800 of 8000
```

### Token Counting

Uses tiktoken for accurate token counting:

```python
# From app/utils/tokens.py

class TokenCounter:
    @staticmethod
    @lru_cache(maxsize=16)
    def _get_encoding(model: str):
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            return tiktoken.get_encoding("cl100k_base")
    
    def count(self, text: str, model: str = "gpt-4") -> int:
        encoding = self._get_encoding(model)
        return len(encoding.encode(text))
```

### Filtering Process

Items are added until budget is exhausted:

```python
# From context_service.py:_apply_token_budget()

filtered_entry_points = []
for ep in entry_points:
    text = self._node_to_text(ep.title, ep.summary, ep.content)
    tokens = self.token_counter.count(text, model)
    
    if tokens_used["entry_points"] + tokens <= entry_budget:
        filtered_entry_points.append(ep)
        tokens_used["entry_points"] += tokens
    else:
        break  # Budget exhausted
```

### Token Usage Response

```json
{
  "stats": {
    "total_tokens": 6500,
    "tokens_used": {
      "entry_points": 4200,
      "context_nodes": 1800,
      "entities": 500
    }
  }
}
```

## Request Parameters

### Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | "" | Search query for entry points |
| `tenant_ids` | string[] | [] | Tenant IDs to search |

### Entry Point Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entry_types` | NodeType[] | null | Node types to search (null = default set) |
| `entry_limit` | int | 10 | Max entry points to return |

### Expansion Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `expand` | bool | true | Enable graph expansion |
| `expansion_types` | NodeType[] | null | Node types to expand (null = all) |
| `max_depth` | int | 2 | Max graph traversal depth |
| `context_limit` | int | 50 | Max context nodes to return |

### Content Flags

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_entities` | bool | true | Include entity nodes |
| `include_schemas` | bool | false | Include schema nodes |
| `include_examples` | bool | false | Include example nodes |

### Token Budget

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_tokens` | int | null | Token limit (null = no limit) |
| `token_model` | string | "gpt-4" | Model for token counting |

## Response Structure

### EntryPointResult

```python
class EntryPointResult(BaseModel):
    id: int                                    # Node ID
    node_type: NodeType                        # faq, playbook, etc.
    title: str                                 # Node title
    summary: Optional[str]                     # Brief summary
    content: Dict[str, Any]                    # Full content
    tags: List[str]                            # Tags
    score: float                               # Search relevance score
    match_source: Literal["bm25", "vector", "hybrid"]
```

### ContextNodeResult

```python
class ContextNodeResult(BaseModel):
    id: int                                    # Node ID
    node_type: NodeType                        # Node type
    title: str                                 # Node title
    summary: Optional[str]                     # Brief summary
    content: Dict[str, Any]                    # Full content
    tags: List[str]                            # Tags
    score: float                               # Relevance score
    distance: int                              # Hops from entry point
    path: List[int]                            # Node IDs in path
    edge_type: Optional[EdgeType]              # Edge used to reach
```

### ContextStats

```python
class ContextStats(BaseModel):
    nodes_searched: int                        # Nodes considered
    nodes_expanded: int                        # Nodes traversed
    max_depth_reached: int                     # Deepest traversal
    entry_points_found: int                    # Entry points returned
    context_nodes_found: int                   # Context nodes returned
    total_tokens: Optional[int]                # Total tokens used
    tokens_used: Optional[Dict[str, int]]      # Breakdown by category
```

## Use Cases

### 1. Customer Support Agent

```json
{
  "query": "Customer asking about refund policy",
  "tenant_ids": ["support"],
  "entry_types": ["faq", "playbook"],
  "entry_limit": 5,
  "expand": true,
  "max_depth": 2,
  "max_tokens": 4000
}
```

### 2. Data Analysis Agent

```json
{
  "query": "How to query order data",
  "tenant_ids": ["analytics"],
  "entry_types": ["schema_index", "schema_field", "example"],
  "include_schemas": true,
  "include_examples": true,
  "entry_limit": 10,
  "max_tokens": 8000
}
```

### 3. Compliance Agent

```json
{
  "query": "What permissions are needed for financial reports",
  "tenant_ids": ["finance", "shared"],
  "entry_types": ["permission_rule", "playbook"],
  "include_entities": true,
  "max_depth": 3,
  "max_tokens": 6000
}
```

## Integration Example

### Python Client

```python
import httpx

async def get_context_for_agent(query: str, tenant_ids: list[str]) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/context",
            json={
                "query": query,
                "tenant_ids": tenant_ids,
                "entry_limit": 10,
                "expand": True,
                "max_depth": 2,
                "max_tokens": 8000,
            },
        )
        return response.json()

# Usage
context = await get_context_for_agent(
    query="How do I process a refund?",
    tenant_ids=["purchasing", "shared"],
)

# Format for LLM
system_prompt = f"""You are a helpful assistant. Use this context:

Entry Points:
{format_entry_points(context['entry_points'])}

Related Context:
{format_context_nodes(context['context'])}

Entities:
{format_entities(context['entities'])}
"""
```

### LangChain Integration

```python
from langchain.retrievers import BaseRetriever
from langchain.schema import Document

class ContextForgeRetriever(BaseRetriever):
    base_url: str = "http://localhost:8000"
    tenant_ids: list[str] = []
    
    def _get_relevant_documents(self, query: str) -> list[Document]:
        response = httpx.post(
            f"{self.base_url}/api/context",
            json={
                "query": query,
                "tenant_ids": self.tenant_ids,
                "max_tokens": 8000,
            },
        )
        data = response.json()
        
        documents = []
        for ep in data["entry_points"]:
            documents.append(Document(
                page_content=f"{ep['title']}\n{ep['summary']}\n{ep['content']}",
                metadata={"id": ep["id"], "type": ep["node_type"]},
            ))
        
        return documents
```

## Performance Considerations

### Graph Loading

The graph is loaded per-tenant and cached:

```python
# Graph is cached in GraphService
await self.graph_service.load_graph(request.tenant_ids)
```

**Tip:** For multi-tenant queries, the graph includes all specified tenants.

### Token Counting

Token counting uses cached encodings:

```python
@lru_cache(maxsize=16)
def _get_encoding(model: str):
    return tiktoken.encoding_for_model(model)
```

**Tip:** Reuse the same `token_model` across requests for cache efficiency.

### Depth vs. Performance

| Max Depth | Typical Nodes | Latency |
|-----------|---------------|---------|
| 1 | 10-20 | ~50ms |
| 2 | 30-100 | ~100ms |
| 3 | 100-500 | ~300ms |

**Recommendation:** Use `max_depth=2` for most use cases.

## Troubleshooting

### Empty Entry Points

**Symptoms:** `entry_points: []`

**Solutions:**
1. Check tenant_ids are correct
2. Verify nodes exist with matching node_types
3. Try broader entry_types (remove filter)
4. Check query text is meaningful

### No Graph Expansion

**Symptoms:** `context: []` despite `expand: true`

**Solutions:**
1. Verify edges exist between nodes
2. Check expansion_types includes target node types
3. Increase max_depth
4. Ensure graph is loaded (check stats.nodes_expanded)

### Token Budget Exceeded

**Symptoms:** Fewer results than expected

**Solutions:**
1. Increase max_tokens
2. Reduce entry_limit or context_limit
3. Use more specific queries
4. Check tokens_used breakdown

## Related Documentation

- [RETRIEVAL_DESIGN.md](RETRIEVAL_DESIGN.md) - Hybrid search architecture
- [QUERY_GENERATION.md](QUERY_GENERATION.md) - NL to SQL conversion
- [COMPLETE_WORKFLOW.md](COMPLETE_WORKFLOW.md) - End-to-end examples
- [API_REFERENCE.md](API_REFERENCE.md) - Full API documentation
