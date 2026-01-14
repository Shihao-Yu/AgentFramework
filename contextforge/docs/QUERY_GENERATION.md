# Query Generation: How ContextForge Converts Natural Language to SQL

This document explains how ContextForge's QueryForge service converts natural language questions into executable SQL/DSL queries.

## Overview

Query generation is a multi-step pipeline that:

1. **Retrieves schema context** - Finds relevant fields using hybrid search
2. **Retrieves examples** - Finds similar Q&A pairs for few-shot learning
3. **Builds the prompt** - Assembles context into an LLM prompt
4. **Generates the query** - LLM produces SQL/DSL
5. **Validates and sanitizes** - Security checks and formatting

```
                                    +------------------+
                                    |  User Question   |
                                    | "Show pending    |
                                    |  orders"         |
                                    +--------+---------+
                                             |
                                             v
+----------------+              +------------------------+
| Schema Fields  |<-------------|  1. Context Retrieval  |
| (hybrid search)|              |     - Schema fields    |
+----------------+              |     - Q&A examples     |
                                +------------------------+
+----------------+                           |
| Q&A Examples   |<--------------------------+
| (vector search)|                           |
+----------------+                           v
                                +------------------------+
                                |  2. Prompt Assembly    |
                                |     - System prompt    |
                                |     - Schema context   |
                                |     - Examples         |
                                +------------------------+
                                             |
                                             v
                                +------------------------+
                                |  3. LLM Generation     |
                                |     - GPT-4o-mini      |
                                |     - Temperature: 0   |
                                +------------------------+
                                             |
                                             v
                                +------------------------+
                                |  4. Validation         |
                                |     - SQL injection    |
                                |     - SELECT only      |
                                |     - LIMIT injection  |
                                +------------------------+
                                             |
                                             v
                                +------------------------+
                                |  Generated Query       |
                                | SELECT * FROM orders   |
                                | WHERE status='pending' |
                                | LIMIT 1000             |
                                +------------------------+
```

## Step 1: Context Retrieval

When a user asks a question, ContextForge retrieves relevant context from the knowledge graph.

### Schema Field Retrieval

The system uses **hybrid search** (BM25 + vector) to find relevant schema fields:

```python
# From queryforge_service.py:_build_query_context()

# 1. Find the schema_index node for the dataset
index_node = await session.execute(
    select(KnowledgeNode).where(
        KnowledgeNode.tenant_id == tenant_id,
        KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
        KnowledgeNode.dataset_name == dataset_name,
    )
)

# 2. Find all schema_field nodes for this dataset
field_nodes = await session.execute(
    select(KnowledgeNode).where(
        KnowledgeNode.node_type == NodeType.SCHEMA_FIELD,
        KnowledgeNode.dataset_name == dataset_name,
    )
)
```

Each field node contains:

| Field | Description | Example |
|-------|-------------|---------|
| `field_path` | Column/field name | `orders.status` |
| `data_type` | SQL/DSL type | `VARCHAR(20)` |
| `description` | Human description | "Order processing status" |
| `allowed_values` | Valid values | `['pending', 'shipped', 'delivered']` |
| `business_meaning` | Domain context | "Tracks order lifecycle" |

### Example Retrieval

The system also retrieves verified Q&A examples for few-shot learning:

```python
# From queryforge_service.py:_build_query_context()

example_nodes = await session.execute(
    select(KnowledgeNode).where(
        KnowledgeNode.node_type == NodeType.EXAMPLE,
        KnowledgeNode.dataset_name == dataset_name,
        KnowledgeNode.is_deleted == False,
    ).limit(10)
)

# Only use verified examples
examples = [
    {"question": e.content["question"], "query": e.content["query"]}
    for e in example_nodes
    if e.content.get("verified", False)
]
```

### Context Structure

The retrieved context is assembled into a dictionary:

```python
context = {
    "source_type": "postgres",           # Database type
    "dataset_name": "orders",            # Table/index name
    "description": "E-commerce orders",  # Dataset description
    "fields": [
        {
            "path": "id",
            "type": "SERIAL",
            "description": "Primary key",
            "allowed_values": [],
        },
        {
            "path": "status",
            "type": "VARCHAR(20)",
            "description": "Order status",
            "allowed_values": ["pending", "shipped", "delivered"],
        },
        # ... more fields
    ],
    "examples": [
        {
            "question": "Show pending orders",
            "query": "SELECT * FROM orders WHERE status = 'pending'",
        },
        # ... more examples
    ],
}
```

## Step 2: Prompt Assembly

The context is formatted into an LLM prompt with three sections:

### System Prompt

```python
# From queryforge_service.py:_build_system_prompt()

system_prompt = f"""You are a {query_format} query generator.

Dataset: {context['dataset_name']}
Description: {context['description']}

Schema:
- id (SERIAL): Primary key
- status (VARCHAR(20)): Order status [values: pending, shipped, delivered]
- customer_id (INTEGER): Customer reference
- total_amount (DECIMAL(10,2)): Order total
- created_at (TIMESTAMP): Creation timestamp

Examples:
Q: Show pending orders
A: SELECT * FROM orders WHERE status = 'pending'

Q: Get orders from last week
A: SELECT * FROM orders WHERE created_at > NOW() - INTERVAL '7 days'

Generate valid {query_format} queries based on user questions."""
```

### User Prompt

```python
# From queryforge_service.py:_build_user_prompt()

user_prompt = "Show all pending orders from the last 7 days"

# If explanation requested:
user_prompt += "\n\nInclude a brief explanation of the query logic."
```

### Prompt Configuration

Prompts are configured via `app/prompts/query_generation.json`:

```json
{
  "name": "query_generation",
  "config": {
    "model": "gpt-4o-mini",
    "context_window": 128000,
    "max_output_tokens": 4096,
    "temperature": 0.0
  }
}
```

**Why temperature 0?** Query generation requires deterministic, precise output. Higher temperatures introduce randomness that could produce syntactically invalid queries.

## Step 3: LLM Generation

The assembled prompt is sent to the LLM for query generation.

### Direct Generation Mode

```python
# From queryforge_service.py:_generate_query_direct()

result = await self.llm_client.generate_structured(
    prompt=user_prompt,
    response_model=GeneratedQuery,  # Pydantic model
    system_prompt=system_prompt,
    temperature=0.0,
    model="gpt-4o-mini",
)
```

The `GeneratedQuery` response model:

```python
class GeneratedQuery(BaseModel):
    query: str = Field(description="The generated SQL/DSL query")
    explanation: Optional[str] = Field(description="Brief explanation")
    confidence: Optional[float] = Field(ge=0.0, le=1.0)
```

### Pipeline Generation Mode

For more sophisticated generation, the `QueryGenerationPipeline` is used:

```python
# From queryforge_service.py:generate_query()

pipeline = QueryGenerationPipeline(
    vector_store=KnowledgeVerseAdapter(session, embedding_client),
    llm_client=llm_client,
)

result = await pipeline.generate_query(
    tenant_id="acme",
    document_name="orders",
    user_question="Show pending orders",
)
```

The pipeline adds:
- **Confidence scoring** based on retrieval quality
- **Auto-correction** with retry on execution failure
- **Dialect-aware formatting** (SQL, OpenSearch DSL, etc.)

### Confidence Calculation

Confidence is computed from retrieval quality:

```python
# From generation/pipeline.py:calculate_confidence()

confidence = (
    0.60 * field_confidence +    # How well schema matches question
    0.25 * example_confidence +  # Number of similar examples (max 3)
    0.15 * concept_confidence    # Concept coverage
)
```

| Confidence | Interpretation |
|------------|----------------|
| 0.85+ | High confidence - use directly |
| 0.70-0.84 | Good match - review recommended |
| 0.50-0.69 | Partial match - verify before use |
| <0.50 | Low confidence - may need examples |

## Step 4: Validation and Sanitization

Generated queries pass through security validation before execution.

### QueryValidator

```python
# From app/utils/query_validator.py

validator = QueryValidator(max_limit=1000, require_limit=True)
result = validator.validate(raw_query)

if not result.is_valid:
    return {"status": "error", "error": result.error}
```

### Validation Layers

1. **Blocklist Check** - Dangerous keywords blocked:
   ```python
   DANGEROUS_KEYWORDS = [
       'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE',
       'TRUNCATE', 'EXEC', 'EXECUTE', 'MERGE', 'GRANT', 'REVOKE',
   ]
   ```

2. **SELECT-Only Enforcement** - Only SELECT queries allowed

3. **Injection Pattern Detection** - Blocks common SQL injection patterns:
   ```python
   INJECTION_PATTERNS = [
       r"1\s*=\s*1",           # Always-true conditions
       r"'\s*OR\s*'",          # OR injection
       r"--",                   # Comment injection
       r"/\*.*\*/",            # Block comments
   ]
   ```

4. **LIMIT Injection** - Adds LIMIT if missing:
   ```python
   if 'LIMIT' not in query.upper():
       query = f"{query.rstrip(';')} LIMIT {max_limit}"
   ```

### Validation Result

```python
@dataclass
class QueryValidationResult:
    is_valid: bool
    error: Optional[str]
    sanitized_query: Optional[str]
    warnings: List[str]
```

## Step 5: Optional Execution

If `execute=True`, the validated query is executed:

```python
# From queryforge_service.py:_execute_query()

result = await asyncio.wait_for(
    session.execute(text(query)),
    timeout=settings.QUERYFORGE_EXECUTION_TIMEOUT  # Default: 30s
)

rows = result.fetchmany(settings.QUERYFORGE_MAX_ROWS + 1)  # Default: 1000
truncated = len(rows) > settings.QUERYFORGE_MAX_ROWS
```

### Execution Response

```python
{
    "status": "success",
    "columns": ["id", "status", "customer_id", "total_amount"],
    "rows": [
        {"id": 1, "status": "pending", "customer_id": 42, "total_amount": 99.99},
        # ...
    ],
    "row_count": 15,
    "truncated": False,
    "execution_time_ms": 12.5,
}
```

### Error Handling

On execution failure, the session is rolled back:

```python
except asyncio.TimeoutError:
    await self.session.rollback()
    return {"status": "error", "error": f"Query timed out after {timeout}s"}
except Exception as e:
    await self.session.rollback()
    return {"status": "error", "error": str(e)}
```

## Improving Query Generation

Query generation quality improves over time through:

### 1. Adding Verified Examples

```python
await service.add_example(
    tenant_id="acme",
    dataset_name="orders",
    question="Show high-value pending orders",
    query="SELECT * FROM orders WHERE status = 'pending' AND total_amount > 1000",
    query_type="sql",
    verified=True,
)
```

### 2. Adding Question Variants

Multiple phrasings for the same query pattern:

```python
variants = [
    "Show pending orders",
    "List orders that are pending",
    "Get unprocessed orders",
    "Pending order report",
]

for question in variants:
    await service.add_example(
        tenant_id="acme",
        dataset_name="orders",
        question=question,
        query="SELECT * FROM orders WHERE status = 'pending'",
        query_type="sql",
        verified=True,
    )
```

### 3. Enriching Schema Metadata

Add business context to field descriptions:

```python
# During onboarding
await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders",
    source_type="postgres",
    raw_schema=DDL,
    description="E-commerce orders with status tracking",
    enable_enrichment=True,  # LLM enriches field descriptions
)
```

## Supported Query Types

| Source Type | Query Format | Example |
|-------------|--------------|---------|
| `postgres` | SQL | `SELECT * FROM orders WHERE status = 'pending'` |
| `mysql` | SQL | `SELECT * FROM orders WHERE status = 'pending'` |
| `clickhouse` | SQL | `SELECT * FROM orders WHERE status = 'pending'` |
| `opensearch` | DSL (JSON) | `{"query": {"term": {"status": "pending"}}}` |
| `elasticsearch` | DSL (JSON) | `{"query": {"term": {"status": "pending"}}}` |
| `rest_api` | API Request | `GET /orders?status=pending` |

## API Usage

### Generate Query Endpoint

```bash
POST /api/datasets/generate
Content-Type: application/json

{
  "tenant_id": "acme",
  "dataset_name": "orders",
  "question": "Show pending orders from last week",
  "include_explanation": true,
  "execute": false
}
```

### Response

```json
{
  "status": "success",
  "query": "SELECT * FROM orders WHERE status = 'pending' AND created_at > NOW() - INTERVAL '7 days' LIMIT 1000",
  "query_type": "postgres",
  "explanation": "Filters orders by pending status and creation date within the last 7 days",
  "confidence": 0.85,
  "validation": {
    "is_valid": true,
    "warnings": []
  }
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QUERYFORGE_EXECUTION_TIMEOUT` | 30 | Query execution timeout (seconds) |
| `QUERYFORGE_MAX_ROWS` | 1000 | Maximum rows returned |
| `EMBEDDING_DIMENSION` | 1536 | Embedding vector dimension |

### Prompt Configuration

Located in `app/prompts/query_generation.json`:

```json
{
  "name": "query_generation",
  "config": {
    "model": "gpt-4o-mini",
    "context_window": 128000,
    "max_output_tokens": 4096,
    "temperature": 0.0
  }
}
```

## Troubleshooting

### Low Confidence Scores

**Symptoms:** Confidence < 0.5, queries may be incorrect

**Solutions:**
1. Add more verified examples for similar questions
2. Ensure schema fields have good descriptions
3. Add business context via `enable_enrichment=True`

### Query Validation Failures

**Symptoms:** `"Generated query failed validation"`

**Solutions:**
1. Check if query contains blocked keywords
2. Ensure query is SELECT-only
3. Review for SQL injection patterns

### Slow Query Generation

**Symptoms:** Generation takes > 5 seconds

**Solutions:**
1. Reduce number of schema fields (use more specific datasets)
2. Limit examples to most relevant ones
3. Check embedding service latency

## Related Documentation

- [RETRIEVAL_DESIGN.md](RETRIEVAL_DESIGN.md) - Hybrid search architecture
- [SCHEMA_ONBOARDING.md](SCHEMA_ONBOARDING.md) - Dataset onboarding workflow
- [COMPLETE_WORKFLOW.md](COMPLETE_WORKFLOW.md) - End-to-end usage examples
- [CONTEXT_RAG.md](CONTEXT_RAG.md) - Context assembly for AI agents
