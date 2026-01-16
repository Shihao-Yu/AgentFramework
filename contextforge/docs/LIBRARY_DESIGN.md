# ContextForge Library Design

## Executive Summary

ContextForge is a knowledge management library for FastAPI applications that provides:

- **Hybrid Search**: Combines BM25 (keyword) and vector (semantic) search for optimal retrieval
- **Knowledge Graph**: Structured relationships between knowledge nodes with edge types and metadata
- **NL-to-SQL Query Generation**: QueryForge integration for natural language database queries
- **Pip-installable**: Single package installation with bundled Admin UI
- **Pluggable Architecture**: Customizable auth, embedding, and LLM providers

### Key Features

- Multi-tenant isolation with row-level security
- Works offline with local embeddings (SentenceTransformers)
- Enterprise-ready with connection pooling and batch operations
- FastAPI-native with async/await throughout
- Type-safe with Pydantic models and SQLModel

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database Schema | `agent` (configurable) | Isolate from host app tables, avoid naming conflicts |
| Auth | Pluggable via AuthProvider protocol | Integrate with any auth system (JWT, OAuth, custom) |
| Admin UI | Bundled, served at `/admin` | Single package installation, no separate deployment |
| Multi-tenancy | Required, tenant isolation built-in | Enterprise requirement, prevents data leakage |
| Default Embedding | SentenceTransformers (local) | Works offline, no API key needed, good quality |
| Database | PostgreSQL with pgvector | Production-ready, vector search support, ACID compliance |
| ORM | SQLModel | Type-safe, async support, Pydantic integration |
| API Framework | FastAPI | Modern, async, auto-generated docs, dependency injection |

## Package Structure

```
contextforge/
├── __init__.py                    # Main exports: ContextForge, ContextForgeConfig
├── core/
│   ├── app.py                     # ContextForge main class
│   ├── config.py                  # ContextForgeConfig (Pydantic Settings)
│   ├── database.py                # Engine/session factory
│   └── exceptions.py              # ContextForgeError, etc.
├── protocols/
│   ├── embedding.py               # EmbeddingProvider protocol
│   ├── llm.py                     # LLMProvider protocol
│   └── auth.py                    # AuthProvider protocol
├── providers/
│   ├── embedding/
│   │   ├── sentence_transformers.py  # Default local provider
│   │   ├── openai.py
│   │   ├── cached.py              # Caching wrapper
│   │   └── mock.py
│   ├── llm/
│   │   ├── openai.py
│   │   └── mock.py
│   └── auth/
│       ├── header.py              # Trust X-User-ID header
│       ├── jwt.py                 # JWT validation
│       └── noop.py                # No auth (dev only)
├── models/                        # SQLModel entities
│   ├── base.py                    # Base model with common fields
│   ├── tenant.py                  # Tenant model
│   ├── node.py                    # Node model
│   ├── edge.py                    # Edge model
│   ├── search.py                  # Search history
│   └── analytics.py               # Analytics models
├── services/                      # Business logic
│   ├── tenant.py                  # TenantService
│   ├── node.py                    # NodeService
│   ├── edge.py                    # EdgeService
│   ├── search.py                  # SearchService
│   ├── staging.py                 # StagingService
│   └── analytics.py               # AnalyticsService
├── routes/                        # FastAPI routers
│   ├── tenants.py
│   ├── nodes.py
│   ├── edges.py
│   ├── search.py
│   ├── staging.py
│   └── analytics.py
├── migrations/                    # Alembic migrations
│   ├── env.py
│   └── versions/
├── admin/                         # Bundled Admin UI static files
│   ├── index.html
│   ├── assets/
│   └── config.json
└── cli/                           # CLI commands
    ├── __init__.py
    ├── db.py                      # Database commands
    └── admin.py                   # Admin commands
```

## Core API Design

### ContextForge Class

The main entry point for the library. Provides factory methods for services and FastAPI integration.

```python
from contextforge import ContextForge, ContextForgeConfig
from contextforge.providers.embedding import SentenceTransformersProvider
from contextforge.providers.auth import JWKSAuthProvider

# Minimal setup (uses defaults)
cf = ContextForge(database_url="postgresql+asyncpg://localhost/mydb")

# Full configuration with Azure AD auth
cf = ContextForge(
    config=ContextForgeConfig(
        database_url="postgresql+asyncpg://localhost/mydb",
        db_schema="agent",
        search_bm25_weight=0.4,
        search_vector_weight=0.6,
        admin_ui_enabled=True,
        admin_ui_path="/admin",
    ),
    embedding_provider=SentenceTransformersProvider(
        model_name="all-MiniLM-L6-v2",
    ),
    llm_provider=None,
    auth_provider=JWKSAuthProvider(
        jwks_url="https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys",
        issuer="https://login.microsoftonline.com/{tenant}/v2.0",
        audience="api://your-app-id",
    ),
)

# Integration options
app.include_router(cf.router, prefix="/api/kb")  # Just the API
app.mount("/contextforge", cf.app)               # Full app with Admin UI
```

### ContextForgeConfig

Configuration using Pydantic Settings with environment variable support.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class ContextForgeConfig(BaseSettings):
    """Configuration for ContextForge library.
    
    All settings can be overridden via environment variables with
    CONTEXTFORGE_ prefix (e.g., CONTEXTFORGE_DATABASE_URL).
    """
    model_config = SettingsConfigDict(env_prefix="CONTEXTFORGE_")
    
    # Database
    database_url: str
    db_schema: str = "agent"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False
    
    # Search
    search_bm25_weight: float = 0.4
    search_vector_weight: float = 0.6
    search_default_limit: int = 20
    search_max_limit: int = 100
    
    # Admin UI
    admin_ui_enabled: bool = True
    admin_ui_path: str = "/admin"
    admin_ui_title: str = "ContextForge"
    admin_ui_logo_url: str | None = None
    admin_ui_theme: str = "light"
    
    # Features
    enable_queryforge: bool = True
    enable_staging: bool = True
    enable_analytics: bool = True
    
    # Performance
    batch_size: int = 100
    embedding_cache_enabled: bool = False
    embedding_cache_backend: str = "memory"  # memory, redis
    embedding_cache_url: str | None = None
    embedding_cache_ttl: int = 86400  # 24 hours
```

### Protocol Definitions

Type-safe protocols for pluggable providers using Python's Protocol class.

```python
from typing import Protocol, runtime_checkable
from dataclasses import dataclass, field
from fastapi import Request

@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding providers.
    
    Implementations must provide text-to-vector conversion.
    """
    
    async def embed(self, text: str) -> list[float]:
        """Generate embedding vector for text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        ...
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        ...
    
    @property
    def dimensions(self) -> int:
        """Return embedding dimensions (e.g., 384, 1024, 1536)."""
        ...

@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers.
    
    Used for QueryForge SQL generation and other text generation tasks.
    """
    
    async def generate(
        self, 
        prompt: str, 
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text completion.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
        """
        ...

@runtime_checkable  
class AuthProvider(Protocol):
    """Protocol for authentication providers.
    
    Implementations must extract user context from requests and
    enforce tenant access control.
    """
    
    async def get_current_user(self, request: Request) -> "AuthContext":
        """Extract user info from request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            AuthContext with user and tenant info
            
        Raises:
            UnauthorizedError: If authentication fails
        """
        ...
    
    async def check_tenant_access(
        self, 
        user: "AuthContext", 
        tenant_id: str,
    ) -> bool:
        """Check if user can access tenant.
        
        Args:
            user: Authenticated user context
            tenant_id: Tenant ID to check
            
        Returns:
            True if user has access, False otherwise
        """
        ...

@dataclass
class AuthContext:
    """User authentication context."""
    email: str
    tenant_ids: list[str]           # Tenants user can access
    roles: list[str] = field(default_factory=list)
    is_admin: bool = False
    metadata: dict = field(default_factory=dict)
```

## Integration Patterns

### Pattern 1: Standalone (New Project)

Use ContextForge as the main application.

```python
from fastapi import FastAPI
from contextforge import ContextForge

app = FastAPI()
cf = ContextForge(database_url="postgresql+asyncpg://localhost/kb")

# Mount everything
app.mount("/", cf.app)

# Access at:
# - /api/* - REST API
# - /admin - Admin UI
# - /docs - OpenAPI docs
```

### Pattern 2: Add to Existing FastAPI App

Integrate ContextForge into an existing application.

```python
from fastapi import FastAPI
from contextforge import ContextForge

app = FastAPI(title="My App")

# Existing routes
@app.get("/")
async def root():
    return {"message": "My App"}

# Add ContextForge
cf = ContextForge(
    database_url="postgresql+asyncpg://localhost/mydb",
    config=ContextForgeConfig(db_schema="agent"),
)

# Option A: Include just the API routes
app.include_router(cf.router, prefix="/api/knowledge", tags=["Knowledge"])

# Option B: Mount as sub-app (includes Admin UI)
app.mount("/knowledge", cf.app)

# Access at:
# - /api/knowledge/* - REST API
# - /knowledge/admin - Admin UI
```

### Pattern 3: Use Services Directly

Use ContextForge services in your own routes without exposing the built-in API.

```python
from fastapi import FastAPI, Depends
from contextforge import ContextForge
from contextforge.services import NodeService, SearchService
from contextforge.protocols import AuthContext

app = FastAPI()
cf = ContextForge(database_url="postgresql+asyncpg://localhost/mydb")

# Custom route using ContextForge services
@app.get("/my-search")
async def my_search(
    query: str,
    node_service: NodeService = Depends(cf.get_node_service),
    search_service: SearchService = Depends(cf.get_search_service),
):
    """Custom search endpoint using ContextForge services."""
    results = await search_service.hybrid_search(
        query_text=query,
        tenant_ids=["my-tenant"],
        limit=10,
    )
    return {"results": results}

@app.post("/my-nodes")
async def create_node(
    title: str,
    content: str,
    node_service: NodeService = Depends(cf.get_node_service),
):
    """Custom node creation with business logic."""
    # Add custom validation or processing
    if len(content) < 10:
        raise ValueError("Content too short")
    
    node = await node_service.create_node(
        tenant_id="my-tenant",
        title=title,
        content=content,
        node_type="custom",
    )
    return node
```

### Pattern 4: Custom Auth Integration

Integrate with existing authentication system.

```python
from contextforge import ContextForge
from contextforge.protocols import AuthProvider, AuthContext
from fastapi import Request, HTTPException

class MyAuthProvider(AuthProvider):
    """Custom auth provider using existing auth service."""
    
    def __init__(self, auth_service):
        self.auth_service = auth_service
    
    async def get_current_user(self, request: Request) -> AuthContext:
        """Extract user from existing auth system."""
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        
        if not token:
            raise HTTPException(status_code=401, detail="Missing token")
        
        # Use existing auth service
        user = await self.auth_service.validate_token(token)
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return AuthContext(
            email=user.email,
            tenant_ids=user.accessible_tenants,
            roles=user.roles,
            is_admin="admin" in user.roles,
        )
    
    async def check_tenant_access(
        self, 
        user: AuthContext, 
        tenant_id: str,
    ) -> bool:
        """Check tenant access using existing logic."""
        return tenant_id in user.tenant_ids or user.is_admin

# Use custom auth provider
cf = ContextForge(
    database_url="postgresql+asyncpg://localhost/mydb",
    auth_provider=MyAuthProvider(my_auth_service),
)
```

### Pattern 5: Shared Database Connection

Reuse existing database connection pool.

```python
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from contextforge import ContextForge

app = FastAPI()

# Existing database setup
engine = create_async_engine(
    "postgresql+asyncpg://localhost/mydb",
    pool_size=20,
    max_overflow=40,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Share connection with ContextForge
cf = ContextForge(
    database_url="postgresql+asyncpg://localhost/mydb",
    engine=engine,  # Reuse existing engine
    session_factory=SessionLocal,  # Reuse existing session factory
)

app.include_router(cf.router, prefix="/api/kb")
```

## Database Migrations

### CLI Commands

ContextForge includes Alembic-based migrations accessible via CLI.

```bash
# Initialize migrations (first time setup)
contextforge db init

# Generate migration from model changes
contextforge db revision --autogenerate -m "Add new field"

# Apply all pending migrations
contextforge db upgrade

# Apply specific migration
contextforge db upgrade <revision>

# Rollback one migration
contextforge db downgrade -1

# Rollback to specific revision
contextforge db downgrade <revision>

# Show current version
contextforge db current

# Show migration history
contextforge db history

# Show pending migrations
contextforge db pending
```

### Programmatic Migration

Run migrations from Python code (useful for testing or automated deployments).

```python
from contextforge import ContextForge

cf = ContextForge(database_url="postgresql+asyncpg://localhost/mydb")

# Run migrations on startup (dev only)
await cf.run_migrations()

# Check migration status
status = await cf.get_migration_status()
if status.pending_migrations:
    raise RuntimeError(
        f"Database migrations required: {status.pending_migrations}"
    )

# Get current version
current = await cf.get_current_migration()
print(f"Current migration: {current}")
```

### Integration with Host App Alembic

If your application already uses Alembic, you can include ContextForge models in your migrations.

```python
# In your alembic/env.py
from contextforge.models import Base as ContextForgeBase
from myapp.models import Base as MyAppBase

# Include both metadata objects
target_metadata = [MyAppBase.metadata, ContextForgeBase.metadata]

# Configure schema for ContextForge tables
def include_object(object, name, type_, reflected, compare_to):
    """Filter tables by schema."""
    if type_ == "table":
        # ContextForge tables go to 'agent' schema
        if hasattr(object, 'schema'):
            return True
    return True
```

### Schema Isolation

ContextForge uses a separate schema (default: `agent`) to avoid conflicts.

```sql
-- Tables are created in the configured schema
CREATE SCHEMA IF NOT EXISTS agent;

CREATE TABLE agent.tenants (...);
CREATE TABLE agent.nodes (...);
CREATE TABLE agent.edges (...);
```

## Admin UI Integration

### Bundled Static Files

The Admin UI is bundled with the library and served automatically.

```python
cf = ContextForge(
    config=ContextForgeConfig(
        admin_ui_enabled=True,
        admin_ui_path="/admin",
    ),
)

# Admin UI served at /admin
# API calls from Admin UI go to /api/*
```

### Customization

Customize the Admin UI appearance and behavior.

```python
cf = ContextForge(
    config=ContextForgeConfig(
        admin_ui_enabled=True,
        admin_ui_path="/admin",
        admin_ui_title="My Knowledge Base",
        admin_ui_logo_url="/static/logo.png",
        admin_ui_theme="dark",  # light, dark, auto
    ),
)
```

### Separate Deployment (npm package)

For advanced use cases, deploy the Admin UI separately.

```html
<!DOCTYPE html>
<html>
<head>
    <title>Knowledge Base</title>
    <script type="module" src="https://unpkg.com/@contextforge/admin-ui"></script>
</head>
<body>
    <contextforge-admin
        api-base-url="https://api.example.com/knowledge"
        tenant-id="my-tenant"
        theme="dark"
    ></contextforge-admin>
</body>
</html>
```

### Disable Admin UI

For production API-only deployments.

```python
cf = ContextForge(
    config=ContextForgeConfig(
        admin_ui_enabled=False,  # No Admin UI
    ),
)
```

## Default Providers

### SentenceTransformers (Default Embedding)

Local embedding provider using HuggingFace models. No API key required.

```python
from contextforge.providers.embedding import SentenceTransformersProvider

# Uses all-MiniLM-L6-v2 by default (384 dimensions)
provider = SentenceTransformersProvider()

# Or specify model
provider = SentenceTransformersProvider(
    model_name="all-mpnet-base-v2",  # 768 dimensions, better quality
    device="cuda",                    # Use GPU if available
    normalize_embeddings=True,        # L2 normalization
)

# Popular models:
# - all-MiniLM-L6-v2: 384 dims, fast, good quality
# - all-mpnet-base-v2: 768 dims, slower, better quality
# - all-MiniLM-L12-v2: 384 dims, balanced
```

### OpenAI Provider

Cloud-based embedding and LLM provider.

```python
from contextforge.providers.embedding import OpenAIEmbeddingProvider
from contextforge.providers.llm import OpenAILLMProvider

cf = ContextForge(
    database_url="postgresql+asyncpg://localhost/mydb",
    embedding_provider=OpenAIEmbeddingProvider(
        api_key="sk-...",
        model="text-embedding-3-small",  # 1536 dimensions
        # model="text-embedding-3-large",  # 3072 dimensions
    ),
    llm_provider=OpenAILLMProvider(
        api_key="sk-...",
        model="gpt-4o-mini",
        # model="gpt-4o",
    ),
)
```

### Mock Provider (Testing)

Deterministic provider for testing.

```python
from contextforge.providers.embedding import MockEmbeddingProvider
from contextforge.providers.llm import MockLLMProvider

cf = ContextForge(
    database_url="postgresql+asyncpg://localhost/test_db",
    embedding_provider=MockEmbeddingProvider(
        dimensions=384,
        seed=42,  # Deterministic embeddings
    ),
    llm_provider=MockLLMProvider(
        responses={
            "generate_sql": "SELECT * FROM users WHERE id = 1",
        },
    ),
)
```

### Cached Embedding Provider

Wrapper that adds caching to any embedding provider.

```python
from contextforge.providers.embedding import (
    CachedEmbeddingProvider,
    OpenAIEmbeddingProvider,
)

cf = ContextForge(
    database_url="postgresql+asyncpg://localhost/mydb",
    embedding_provider=CachedEmbeddingProvider(
        provider=OpenAIEmbeddingProvider(api_key="sk-..."),
        cache_backend="redis",
        cache_url="redis://localhost:6379",
        cache_ttl=86400,  # 24 hours
        cache_prefix="cf:embed:",
    ),
)
```

## Multi-Tenancy

### Tenant Isolation

All queries are automatically filtered by tenant_id to prevent data leakage.

```python
# Create tenant
POST /api/tenants
{
    "id": "acme",
    "name": "Acme Corp",
    "description": "Acme Corporation tenant"
}

# All subsequent operations are scoped to tenant
POST /api/nodes
{
    "tenant_id": "acme",
    "title": "Product Guide",
    "content": "..."
}

# Search only returns results from authorized tenants
GET /api/search?q=product&tenant_id=acme
```

### Tenant Setup

```python
# Via API
POST /api/tenants
{
    "id": "acme",
    "name": "Acme Corp",
    "description": "Acme Corporation tenant",
    "metadata": {
        "industry": "manufacturing",
        "region": "us-west"
    }
}

# Via service
tenant_service = cf.get_tenant_service()
await tenant_service.create_tenant(
    id="acme",
    name="Acme Corp",
    description="Acme Corporation tenant",
    metadata={"industry": "manufacturing"},
)
```

### Cross-Tenant Edges

Admins can create edges between nodes in different tenants for shared knowledge.

```python
# Create cross-tenant edge (requires admin role)
edge_service = cf.get_edge_service()
await edge_service.create_edge(
    source_node_id="acme:node1",
    target_node_id="shared:node2",
    edge_type="references",
    created_by="admin@example.com",
)
```

### Tenant Access Control

```python
class MyAuthProvider(AuthProvider):
    async def get_current_user(self, request: Request) -> AuthContext:
        user = await self.validate_token(request)
        
        return AuthContext(
            email=user.email,
            tenant_ids=["acme", "shared"],
            is_admin=user.is_admin,
        )
    
    async def check_tenant_access(
        self, 
        user: AuthContext, 
        tenant_id: str,
    ) -> bool:
        # Admins can access all tenants
        if user.is_admin:
            return True
        
        # Regular users only access their tenants
        return tenant_id in user.tenant_ids
```

## Error Handling

### Exception Hierarchy

```python
from contextforge.exceptions import (
    ContextForgeError,           # Base exception
    TenantNotFoundError,
    NodeNotFoundError,
    EdgeNotFoundError,
    UnauthorizedError,
    ForbiddenError,
    EmbeddingError,
    LLMError,
    MigrationError,
    ValidationError,
)

try:
    result = await cf.search("query", tenant_id="unknown")
except TenantNotFoundError as e:
    # Handle missing tenant
    return {"error": "Tenant not found", "tenant_id": e.tenant_id}
except EmbeddingError as e:
    # Handle embedding provider failure
    logger.error(f"Embedding failed: {e}")
    return {"error": "Search temporarily unavailable"}
except UnauthorizedError as e:
    # Handle auth failure
    return {"error": "Authentication required"}
```

### Error Response Format

All API errors follow a consistent format:

```json
{
    "error": {
        "type": "TenantNotFoundError",
        "message": "Tenant 'unknown' not found",
        "details": {
            "tenant_id": "unknown"
        }
    }
}
```

### Custom Error Handlers

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextforge import ContextForge
from contextforge.exceptions import ContextForgeError

app = FastAPI()
cf = ContextForge(database_url="...")

@app.exception_handler(ContextForgeError)
async def contextforge_error_handler(
    request: Request, 
    exc: ContextForgeError,
):
    """Custom error handler for ContextForge errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
                "details": exc.details,
            }
        },
    )

app.include_router(cf.router, prefix="/api/kb")
```

## Testing

### Test Configuration

```python
import pytest
from contextforge import ContextForge, ContextForgeConfig
from contextforge.providers.embedding import MockEmbeddingProvider
from contextforge.providers.auth import NoopAuthProvider

@pytest.fixture
async def contextforge():
    """ContextForge instance for testing."""
    cf = ContextForge(
        config=ContextForgeConfig(
            database_url="postgresql+asyncpg://localhost/test_db",
            db_schema="test_agent",
            admin_ui_enabled=False,
        ),
        embedding_provider=MockEmbeddingProvider(dimensions=384),
        auth_provider=NoopAuthProvider(),  # No auth checks
    )
    
    # Run migrations
    await cf.run_migrations()
    
    yield cf
    
    # Cleanup
    await cf.dispose()

@pytest.fixture
async def tenant(contextforge):
    """Create test tenant."""
    tenant_service = contextforge.get_tenant_service()
    tenant = await tenant_service.create_tenant(
        id="test",
        name="Test Tenant",
    )
    return tenant
```

### Service Testing

```python
async def test_node_creation(contextforge, tenant):
    """Test node creation."""
    node_service = contextforge.get_node_service()
    
    node = await node_service.create_node(
        tenant_id=tenant.id,
        title="Test Node",
        content="Test content",
        node_type="document",
    )
    
    assert node.id is not None
    assert node.title == "Test Node"
    assert node.embedding is not None  # Auto-generated

async def test_hybrid_search(contextforge, tenant):
    """Test hybrid search."""
    node_service = contextforge.get_node_service()
    search_service = contextforge.get_search_service()
    
    # Create test nodes
    await node_service.create_node(
        tenant_id=tenant.id,
        title="Python Tutorial",
        content="Learn Python programming",
    )
    await node_service.create_node(
        tenant_id=tenant.id,
        title="JavaScript Guide",
        content="Learn JavaScript programming",
    )
    
    # Search
    results = await search_service.hybrid_search(
        query_text="python",
        tenant_ids=[tenant.id],
        limit=10,
    )
    
    assert len(results) > 0
    assert "python" in results[0].title.lower()
```

### API Testing

```python
from fastapi.testclient import TestClient

def test_search_api(contextforge):
    """Test search API endpoint."""
    client = TestClient(contextforge.app)
    
    response = client.get(
        "/api/search",
        params={"q": "python", "tenant_id": "test"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
```

## Performance Considerations

### Connection Pooling

Configure database connection pool for optimal performance.

```python
cf = ContextForge(
    config=ContextForgeConfig(
        database_url="postgresql+asyncpg://localhost/mydb",
        db_pool_size=20,        # Connections in pool
        db_max_overflow=40,     # Additional connections
        db_echo=False,          # Disable SQL logging
    ),
)
```

### Embedding Caching

Cache embeddings to reduce API calls and improve response time.

```python
from contextforge.providers.embedding import CachedEmbeddingProvider

cf = ContextForge(
    embedding_provider=CachedEmbeddingProvider(
        provider=OpenAIEmbeddingProvider(...),
        cache_backend="redis",
        cache_url="redis://localhost:6379",
        cache_ttl=86400,  # 24 hours
    ),
)
```

### Batch Operations

Use batch operations for bulk data processing.

```python
node_service = cf.get_node_service()

# Batch create nodes
nodes = [
    {"tenant_id": "acme", "title": f"Node {i}", "content": f"Content {i}"}
    for i in range(1000)
]
await node_service.create_nodes_batch(nodes, batch_size=100)

# Batch update embeddings
node_ids = [node.id for node in nodes]
await node_service.update_embeddings_batch(node_ids, batch_size=50)
```

### Query Optimization

```python
# Use pagination for large result sets
results = await search_service.hybrid_search(
    query_text="python",
    tenant_ids=["acme"],
    limit=20,
    offset=0,
)

# Filter by node type to reduce search space
results = await search_service.hybrid_search(
    query_text="python",
    tenant_ids=["acme"],
    node_types=["document", "tutorial"],
)

# Use vector search only for semantic queries
results = await search_service.vector_search(
    query_text="how to handle errors",
    tenant_ids=["acme"],
)

# Use BM25 only for keyword queries
results = await search_service.bm25_search(
    query_text="error handling",
    tenant_ids=["acme"],
)
```

### Monitoring

```python
# Enable SQL query logging (dev only)
cf = ContextForge(
    config=ContextForgeConfig(
        database_url="...",
        db_echo=True,  # Log all SQL queries
    ),
)

# Track search performance
from contextforge.services import AnalyticsService

analytics_service = cf.get_analytics_service()
stats = await analytics_service.get_search_stats(
    tenant_id="acme",
    start_date="2025-01-01",
    end_date="2025-01-31",
)
print(f"Avg search time: {stats.avg_duration_ms}ms")
```

## Roadmap

### v1.0 (Initial Release)

**Target: Q2 2025**

- Core knowledge management (nodes, edges, search)
- Hybrid search (BM25 + Vector)
- Admin UI bundled
- SentenceTransformers default provider
- Multi-tenant support
- PostgreSQL with pgvector
- FastAPI integration
- Alembic migrations
- CLI commands

### v1.1

**Target: Q3 2025**

- QueryForge NL-to-SQL integration
- Staging workflow (draft/review/publish)
- Analytics dashboard
- Search history and recommendations
- Bulk import/export
- API rate limiting

### v1.2

**Target: Q4 2025**

- Graph visualization in Admin UI
- Auto-suggest relationships
- Gap detection (missing knowledge)
- Duplicate detection
- Knowledge quality scoring
- Advanced filtering

### v2.0

**Target: Q1 2026**

- Plugin architecture
- Custom node types
- Webhook integrations
- Real-time collaboration
- Version control for nodes
- Advanced access control (field-level)
- Multi-language support

### Future Considerations

- Support for other databases (MySQL, SQLite)
- Alternative vector stores (Qdrant, Weaviate)
- GraphQL API
- gRPC API for high-performance clients
- Kubernetes operator
- Terraform provider
- Docker Compose templates

## Migration Guide

### From Standalone App to Library

If you have an existing ContextForge standalone deployment:

1. **Install library**: `pip install contextforge`
2. **Update imports**: Change from local imports to library imports
3. **Configure**: Use `ContextForgeConfig` instead of environment variables
4. **Integrate**: Mount into existing FastAPI app
5. **Migrate data**: Database schema remains compatible

```python
# Before (standalone)
from app.main import app

# After (library)
from fastapi import FastAPI
from contextforge import ContextForge

app = FastAPI()
cf = ContextForge(database_url="...")
app.mount("/kb", cf.app)
```

### From Other Knowledge Management Systems

Migration utilities for common systems:

```bash
# From Notion
contextforge import notion --token <token> --tenant acme

# From Confluence
contextforge import confluence --url <url> --user <user> --tenant acme

# From Markdown files
contextforge import markdown --dir ./docs --tenant acme

# From JSON
contextforge import json --file data.json --tenant acme
```

## Security Considerations

### Authentication

- Always use a real AuthProvider in production
- Never use NoopAuthProvider outside of testing
- Validate JWT tokens properly
- Use HTTPS in production

### Authorization

- Enforce tenant isolation at the database level
- Check tenant access on every request
- Audit cross-tenant operations
- Log all admin actions

### Data Protection

- Encrypt sensitive data at rest
- Use connection pooling with SSL
- Sanitize user inputs
- Rate limit API endpoints

### Secrets Management

```python
# Use environment variables for secrets
cf = ContextForge(
    config=ContextForgeConfig(
        database_url=os.getenv("DATABASE_URL"),
    ),
    embedding_provider=OpenAIEmbeddingProvider(
        api_key=os.getenv("OPENAI_API_KEY"),
    ),
)

# Or use a secrets manager
from my_secrets import get_secret

cf = ContextForge(
    database_url=get_secret("database_url"),
)
```

## Support and Community

### Documentation

- Full API reference: https://docs.contextforge.ai
- Tutorials: https://docs.contextforge.ai/tutorials
- Examples: https://github.com/contextforge/examples

### Getting Help

- GitHub Issues: https://github.com/contextforge/contextforge/issues
- Discord: https://discord.gg/contextforge
- Stack Overflow: Tag `contextforge`

### Contributing

- Contributing guide: CONTRIBUTING.md
- Code of conduct: CODE_OF_CONDUCT.md
- Development setup: DEVELOPMENT.md

## License

MIT License - see LICENSE file for details.
