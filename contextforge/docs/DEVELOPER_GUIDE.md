# ContextForge Developer Guide

This guide provides a comprehensive reference for developers working on the ContextForge codebase.

## Project Overview

```
contextforge/
├── app/
│   ├── clients/          # Embedding & inference clients
│   ├── contextforge/     # Core engine (migrated from AgenticSearch)
│   ├── core/             # Config, database, dependencies
│   ├── models/           # SQLModel entities
│   ├── routes/           # API endpoints
│   ├── schemas/          # Pydantic models
│   └── services/         # Business logic
├── alembic/              # Database migrations
├── jobs/                 # Background jobs
├── pipeline/             # Ticket-to-knowledge conversion
└── tests/                # Test suite
```

## Quick Reference: Import Paths

```python
# Services
from app.services.queryforge_service import QueryForgeService
from app.services.queryforge_adapter import KnowledgeVerseAdapter
from app.services.node_service import NodeService
from app.services.edge_service import EdgeService
from app.services.graph_service import GraphService
from app.services.search_service import SearchService

# Models
from app.models.nodes import KnowledgeNode
from app.models.edges import KnowledgeEdge
from app.models.enums import NodeType, EdgeType, KnowledgeStatus

# Clients
from app.clients.embedding_client import EmbeddingClient
from app.clients.inference_client import InferenceClient

# ContextForge (core engine)
from app.contextforge.generation import QueryGenerationPipeline
from app.contextforge.sources import get_source, list_sources
from app.contextforge.schema import FieldSpec
from app.contextforge.core import QueryType
```

## Development Commands

```bash
# Run server
uvicorn app.main:app --reload

# Run tests
pytest tests/ -v

# Run migrations
alembic upgrade head
alembic revision --autogenerate -m "message"

# Code formatting
black app/ pipeline/ jobs/
ruff check app/ pipeline/ jobs/

# Type checking
mypy app/ pipeline/ jobs/
```

## Common Patterns

### Pattern 1: Service Usage

```python
async with get_session() as session:
    service = QueryForgeService(
        session=session,
        embedding_client=get_embedding_client(),
        llm_client=get_inference_client(),
    )
    result = await service.onboard_dataset(...)
```

### Pattern 2: Node Creation

```python
node = KnowledgeNode(
    tenant_id="acme",
    node_type=NodeType.FAQ,
    title="How do I reset my password?",
    summary="Password reset instructions",
    content={"answer": "..."},
    status=KnowledgeStatus.PUBLISHED,
)
session.add(node)
await session.commit()
```

### Pattern 3: Edge Creation

```python
edge = KnowledgeEdge(
    source_id=node1.id,
    target_id=node2.id,
    edge_type=EdgeType.RELATED,
)
session.add(edge)
await session.commit()
```

### Pattern 4: Hybrid Search

```python
result = await session.execute(
    text("""
        SELECT * FROM hybrid_search_nodes(
            :query_text, :embedding::vector,
            :tenant_ids, :node_types, :top_k,
            :bm25_weight, :vector_weight
        )
    """),
    params,
)
```

## Testing Patterns

```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
async def mock_embedding_client():
    client = AsyncMock(spec=EmbeddingClient)
    client.embed.return_value = [0.0] * 1024
    return client

@pytest.mark.asyncio
async def test_onboard_dataset(db_session, mock_embedding_client):
    service = QueryForgeService(db_session, mock_embedding_client)
    result = await service.onboard_dataset(...)
    assert result["status"] == "success"
```

## Environment Variables

```bash
CONTEXT_DB_URL=postgresql+asyncpg://user:pass@localhost/contextforge
EMBEDDING_API_URL=http://localhost:8080/embed
INFERENCE_API_URL=http://localhost:8081/generate
```

## Important Notes

1. All services are async - use await
2. Sessions should be used with context managers
3. Embeddings are 1024-dimensional vectors
4. Multi-tenant: always include tenant_id
5. Soft deletes: set is_deleted=True, don't hard delete

## Architecture Principles

### Multi-Tenancy
All data operations must include `tenant_id` for proper isolation. Never query across tenants without explicit authorization.

### Async/Await
The entire stack is built on async/await. All database operations, client calls, and service methods are asynchronous.

### Database Sessions
Always use context managers for database sessions to ensure proper cleanup:

```python
from app.core.database import get_session

async with get_session() as session:
    # Your database operations here
    pass
```

### Dependency Injection
FastAPI's dependency injection is used throughout. Common dependencies:

```python
from app.core.dependencies import (
    get_embedding_client,
    get_inference_client,
    get_current_tenant,
)
```

## Service Layer Architecture

Services encapsulate business logic and coordinate between models, clients, and external systems.

### QueryForgeService
Primary service for dataset onboarding and query generation.

```python
service = QueryForgeService(
    session=session,
    embedding_client=embedding_client,
    llm_client=llm_client,
)
```

### NodeService
CRUD operations for knowledge nodes.

```python
node_service = NodeService(session)
nodes = await node_service.get_by_tenant(tenant_id)
```

### EdgeService
Manages relationships between knowledge nodes.

```python
edge_service = EdgeService(session)
edges = await edge_service.get_by_source(source_id)
```

### GraphService
High-level graph operations and traversals.

```python
graph_service = GraphService(session)
subgraph = await graph_service.get_subgraph(node_id, depth=2)
```

### SearchService
Hybrid search combining BM25 and vector similarity.

```python
search_service = SearchService(session, embedding_client)
results = await search_service.search(
    query="password reset",
    tenant_ids=["acme"],
    top_k=10,
)
```

## Database Migrations

### Creating Migrations

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new field to nodes"

# Create empty migration for manual changes
alembic revision -m "Add custom index"
```

### Applying Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade to specific revision
alembic upgrade abc123

# Downgrade one revision
alembic downgrade -1
```

### Migration Best Practices

1. Always review auto-generated migrations
2. Test migrations on a copy of production data
3. Include both upgrade and downgrade paths
4. Add indexes for frequently queried columns
5. Use batch operations for large data changes

## Testing Strategy

### Unit Tests
Test individual functions and methods in isolation.

```python
@pytest.mark.asyncio
async def test_node_creation():
    node = KnowledgeNode(
        tenant_id="test",
        node_type=NodeType.FAQ,
        title="Test",
    )
    assert node.tenant_id == "test"
```

### Integration Tests
Test service interactions with database and clients.

```python
@pytest.mark.asyncio
async def test_onboard_dataset_integration(db_session):
    service = QueryForgeService(db_session, mock_clients...)
    result = await service.onboard_dataset(...)
    
    # Verify database state
    nodes = await db_session.execute(select(KnowledgeNode))
    assert len(nodes.scalars().all()) > 0
```

### Fixtures
Common test fixtures are defined in `tests/conftest.py`:

- `db_session`: Test database session
- `mock_embedding_client`: Mocked embedding client
- `mock_inference_client`: Mocked LLM client
- `sample_tenant`: Test tenant data

## Code Style Guidelines

### Formatting
- Use Black for code formatting (line length: 88)
- Use Ruff for linting
- Sort imports with isort

### Type Hints
Always include type hints for function parameters and return values:

```python
async def get_node(session: AsyncSession, node_id: UUID) -> KnowledgeNode | None:
    result = await session.get(KnowledgeNode, node_id)
    return result
```

### Docstrings
Use Google-style docstrings:

```python
async def search_nodes(
    session: AsyncSession,
    query: str,
    tenant_ids: list[str],
) -> list[KnowledgeNode]:
    """Search for knowledge nodes using hybrid search.
    
    Args:
        session: Database session
        query: Search query text
        tenant_ids: List of tenant IDs to search within
        
    Returns:
        List of matching knowledge nodes
        
    Raises:
        ValueError: If query is empty or tenant_ids is empty
    """
    pass
```

## Performance Considerations

### Database Queries
- Use `select()` with explicit column selection when possible
- Leverage indexes for frequently queried fields
- Use `joinedload()` for eager loading relationships
- Batch operations when processing multiple records

### Embeddings
- Cache embeddings when possible
- Batch embedding requests for multiple texts
- Consider async batch processing for large datasets

### Vector Search
- Tune `bm25_weight` and `vector_weight` for your use case
- Adjust `top_k` based on result quality vs. performance needs
- Use appropriate index types (IVFFlat, HNSW) for scale

## Troubleshooting

### Common Issues

**Database Connection Errors**
- Verify CONTEXT_DB_URL is correct
- Check PostgreSQL is running
- Ensure pgvector extension is installed

**Embedding Client Errors**
- Verify EMBEDDING_API_URL is accessible
- Check embedding dimension matches (1024)
- Ensure API is running and healthy

**Migration Conflicts**
- Pull latest migrations from main branch
- Resolve conflicts in migration files
- Test migration on clean database

**Test Failures**
- Ensure test database is clean
- Check for async/await issues
- Verify mock configurations

## Additional Resources

- API Documentation: `/docs` (Swagger UI)
- Database Schema: `alembic/versions/`
- Example Scripts: `examples/`
- Architecture Decisions: `docs/ADR/`
