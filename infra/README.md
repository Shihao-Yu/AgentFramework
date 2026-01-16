# Infra

Shared infrastructure for the AgentFramework.

## Installation

```bash
# Core only
pip install -e .

# With specific components
pip install -e ".[inference,embedding]"

# All components
pip install -e ".[all]"

# Development
pip install -e ".[all,dev]"
```

## Components

### Auth (`infra.auth`)

User context and authorization models.

```python
from infra.auth import EnrichedUser, RequestContext, ResourceAction

# Create user
user = EnrichedUser(
    user_id=1,
    username="john",
    email="john@example.com",
    display_name="John Doe",
)

# Check permissions
if user.can("purchase_order", "create"):
    # create PO
    pass

# Request context
ctx = RequestContext.create(user=user, session_id="sess-123")
```

### Inference (`infra.inference`)

OpenAI-compatible LLM client.

```python
from infra.inference import InferenceClient, Message

client = InferenceClient()  # Uses OPENAI_API_KEY env var

response = await client.complete([
    Message.system("You are helpful."),
    Message.user("Hello!"),
])
print(response.content)

# Streaming
async for chunk in client.stream([Message.user("Tell me a story")]):
    print(chunk, end="")
```

### Embedding (`infra.embedding`)

OpenAI-compatible embedding client.

```python
from infra.embedding import EmbeddingClient

client = EmbeddingClient()

vector = await client.embed("Hello world")
vectors = await client.embed_batch(["Hello", "World"])
```

### Tracing (`infra.tracing`)

Langfuse integration for observability and prompt management.

```python
from infra.tracing import TracingClient, get_prompt

# Tracing
tracing = TracingClient()
trace = tracing.start_trace(ctx, name="handle_query")
# ... do work ...
tracing.end_trace(trace)

# Prompt management
prompt = get_prompt("query_classifier")
result = await client.complete([Message.system(prompt.template)])
```

### Clients (`infra.clients`)

Infrastructure clients for HTTP, Redis, PostgreSQL, ClickHouse.

```python
from infra.clients import HttpClient, RedisClient, PostgresClient

# HTTP
async with HttpClient() as http:
    response = await http.get("https://api.example.com/data")

# Redis
redis = RedisClient()
await redis.set("key", "value")

# PostgreSQL
pg = PostgresClient()
async with pg.session() as session:
    result = await session.execute(query)
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required for inference/embedding |
| `OPENAI_BASE_URL` | OpenAI-compatible base URL | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Default model | `gpt-4o-mini` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | - |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | - |
| `LANGFUSE_HOST` | Langfuse host | `https://cloud.langfuse.com` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `FRAMEWORK_DB_URL` | PostgreSQL connection URL | - |
| `CLICKHOUSE_HOST` | ClickHouse host | `localhost` |

## Development

```bash
# Install dev dependencies
pip install -e ".[all,dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=infra
```
