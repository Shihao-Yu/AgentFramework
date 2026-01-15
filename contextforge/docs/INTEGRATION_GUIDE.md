# ContextForge Integration Guide

How to integrate ContextForge as a backend API for your application's admin UI.

## Overview

ContextForge is a pip-installable library that provides:
- REST API for knowledge management (CRUD, search, graph)
- Bundled Admin UI (React-based, optional)
- Multi-tenant isolation
- Hybrid search (BM25 + vector)

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- `DATABASE_URL` environment variable

## Installation

```bash
pip install contextforge

# With local embeddings (recommended)
pip install contextforge[embeddings]

# With OpenAI providers
pip install contextforge[openai]

# With JWT authentication
pip install contextforge[jwt]

# Everything
pip install contextforge[all]
```

## Quick Start

### 1. Set Environment Variable

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/dbname"
```

### 2. Initialize Database

```bash
contextforge db init
contextforge db upgrade
```

### 3. Add to Your FastAPI App

```python
from fastapi import FastAPI
from contextforge import ContextForge
from contextforge.providers.embedding import SentenceTransformersProvider

app = FastAPI()

cf = ContextForge(
    embedding_provider=SentenceTransformersProvider(),
)

# Add API routes at /api/kb
app.include_router(cf.router, prefix="/api/kb")
```

## Integration Patterns

### Pattern 1: API Routes Only

Add ContextForge API to your existing FastAPI app without the bundled Admin UI.

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from contextforge import ContextForge
from contextforge.providers.embedding import SentenceTransformersProvider

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await cf.dispose()

app = FastAPI(lifespan=lifespan)

cf = ContextForge(
    embedding_provider=SentenceTransformersProvider(),
)

app.include_router(cf.router, prefix="/api/kb")

# Your app's routes
@app.get("/")
async def root():
    return {"status": "ok"}
```

**Endpoints available:**
- `GET /api/kb/nodes` - List knowledge nodes
- `POST /api/kb/nodes` - Create node
- `GET /api/kb/search` - Hybrid search
- `GET /api/kb/graph` - Graph queries
- See full API at `/docs`

### Pattern 2: Full App with Admin UI

Mount ContextForge as a sub-application with the bundled Admin UI.

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from contextforge import ContextForge, ContextForgeConfig
from contextforge.providers.embedding import SentenceTransformersProvider

cf = ContextForge(
    config=ContextForgeConfig(
        admin_ui_enabled=True,
        admin_ui_title="My Knowledge Base",
    ),
    embedding_provider=SentenceTransformersProvider(),
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await cf.dispose()

app = FastAPI(lifespan=lifespan)

# Mount at /kb - includes API and Admin UI
app.mount("/kb", cf.app)

@app.get("/")
async def root():
    return {
        "api": "/kb/api",
        "admin": "/kb/admin",
    }
```

**Access points:**
- API: `http://localhost:8000/kb/api/*`
- Admin UI: `http://localhost:8000/kb/admin`
- Swagger: `http://localhost:8000/kb/docs`

### Pattern 3: Custom Frontend with ContextForge Backend

Use ContextForge purely as an API backend for your own frontend.

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from contextforge import ContextForge, ContextForgeConfig
from contextforge.providers.embedding import SentenceTransformersProvider

cf = ContextForge(
    config=ContextForgeConfig(
        admin_ui_enabled=False,  # Disable bundled UI
        cors_origins="http://localhost:3000",  # Your frontend origin
    ),
    embedding_provider=SentenceTransformersProvider(),
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await cf.dispose()

app = FastAPI(lifespan=lifespan)

# ContextForge API
app.include_router(cf.router, prefix="/api/kb")

# Your custom frontend
app.mount("/", StaticFiles(directory="frontend/dist", html=True))
```

## Authentication

### Header-Based Auth (Behind Gateway)

Use when your app is behind an auth gateway that sets user headers.

```python
from contextforge import ContextForge
from contextforge.providers.auth import HeaderAuthProvider

cf = ContextForge(
    embedding_provider=...,
    auth_provider=HeaderAuthProvider(
        user_id_header="X-User-ID",
        tenant_id_header="X-Tenant-ID",
        roles_header="X-User-Roles",
    ),
)
```

### JWT Authentication

Validate JWT tokens directly.

```python
from contextforge import ContextForge
from contextforge.providers.auth import JWTAuthProvider

cf = ContextForge(
    embedding_provider=...,
    auth_provider=JWTAuthProvider(
        secret_key="your-secret-key",  # Or set JWT_SECRET_KEY env var
        algorithms=["HS256"],
    ),
)
```

**Expected JWT payload:**
```json
{
  "sub": "user-123",
  "tenants": ["tenant-a", "tenant-b"],
  "roles": ["editor"],
  "exp": 1699999999
}
```

### Custom Auth Provider

Integrate with your existing auth system.

```python
from contextforge import ContextForge
from contextforge.protocols.auth import AuthProvider, AuthContext
from fastapi import Request

class MyAuthProvider:
    def __init__(self, auth_service):
        self.auth_service = auth_service
    
    async def get_current_user(self, request: Request) -> AuthContext:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        user = await self.auth_service.validate(token)
        
        return AuthContext(
            user_id=user.id,
            tenant_ids=user.tenants,
            roles=user.roles,
            is_admin="admin" in user.roles,
        )
    
    async def check_tenant_access(self, user: AuthContext, tenant_id: str) -> bool:
        return user.can_access_tenant(tenant_id)

cf = ContextForge(
    embedding_provider=...,
    auth_provider=MyAuthProvider(my_auth_service),
)
```

## Embedding Providers

### Local Embeddings (Default)

No API key needed. Runs locally.

```python
from contextforge.providers.embedding import SentenceTransformersProvider

cf = ContextForge(
    embedding_provider=SentenceTransformersProvider(
        model_name="all-MiniLM-L6-v2",  # 384 dims, fast
        # model_name="all-mpnet-base-v2",  # 768 dims, better quality
    ),
)
```

### OpenAI Embeddings

```python
from contextforge.providers.embedding import OpenAIEmbeddingProvider

cf = ContextForge(
    embedding_provider=OpenAIEmbeddingProvider(
        model="text-embedding-3-small",  # Set OPENAI_API_KEY env var
    ),
)
```

## Configuration Reference

```python
from contextforge import ContextForgeConfig

config = ContextForgeConfig(
    # Database (required via DATABASE_URL env var)
    db_schema="agent",           # PostgreSQL schema name
    db_pool_size=10,             # Connection pool size
    db_max_overflow=20,          # Max overflow connections
    
    # Search
    search_bm25_weight=0.4,      # Keyword search weight
    search_vector_weight=0.6,    # Semantic search weight
    
    # Admin UI
    admin_ui_enabled=True,       # Serve bundled Admin UI
    admin_ui_path="/admin",      # Admin UI URL path
    admin_ui_title="My KB",      # Browser title
    
    # Features
    enable_queryforge=True,      # NL-to-SQL generation
    enable_staging=True,         # Review workflow
    enable_analytics=True,       # Usage tracking
    
    # API
    api_prefix="/api",           # API route prefix
    cors_origins="*",            # CORS origins (comma-separated)
)
```

## CLI Commands

```bash
# Database
contextforge db init           # Create schema and extensions
contextforge db upgrade        # Run migrations
contextforge db status         # Show migration status
contextforge db check          # Verify connection

# Info
contextforge version           # Show version
contextforge info              # Show configuration
```

## API Endpoints

When you include `cf.router`, these endpoints are available:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/nodes` | List nodes with filtering |
| POST | `/nodes` | Create a node |
| GET | `/nodes/{id}` | Get node by ID |
| PUT | `/nodes/{id}` | Update node |
| DELETE | `/nodes/{id}` | Delete node |
| GET | `/search` | Hybrid search |
| POST | `/context` | Context retrieval with graph expansion |
| GET | `/graph` | Graph traversal |
| GET | `/tenants` | List tenants |
| POST | `/tenants` | Create tenant |

Full API documentation at `/docs` when running.

## Library API (Direct Usage)

For framework integrations, you can use the `get_context()` method directly without going through HTTP:

```python
from contextforge import ContextForge, NodeType

cf = ContextForge(database_url="postgresql+asyncpg://...")

# Simple query
results = await cf.get_context(
    query="purchase order approval",
    tenant_ids=["acme"],
)

# Shallow context for planners (1-hop, limited types)
results = await cf.get_context(
    query="how do I approve a PO?",
    tenant_ids=["acme"],
    entry_types=[NodeType.FAQ, NodeType.PLAYBOOK],
    max_depth=1,
    max_tokens=3000,
)

# Keyword-heavy search (BM25 only)
results = await cf.get_context(
    query="error code PO-4501",
    tenant_ids=["acme"],
    search_method="bm25",
)

# Filter by tags with quality threshold
results = await cf.get_context(
    query="approval workflow",
    tenant_ids=["acme"],
    tags=["procurement"],
    min_score=0.3,
)

# Advanced: full request object
from contextforge import ContextRequest
request = ContextRequest(
    query="...",
    tenant_ids=["acme"],
    entry_types=[NodeType.FAQ],
    search_method="hybrid",
    bm25_weight=0.3,
    vector_weight=0.7,
)
results = await cf.get_context(request=request)
```

### get_context() Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | required | Search query text |
| `tenant_ids` | List[str] | required | Tenant IDs to search within |
| `entry_types` | List[NodeType] | None | Filter entry points by node type |
| `tags` | List[str] | None | Filter by tags |
| `search_method` | "hybrid"\|"bm25"\|"vector" | "hybrid" | Search method |
| `bm25_weight` | float | 0.4 | BM25 keyword weight (hybrid mode) |
| `vector_weight` | float | 0.6 | Vector semantic weight (hybrid mode) |
| `min_score` | float | None | Minimum score threshold |
| `max_depth` | int | 2 | Graph expansion depth |
| `expand` | bool | True | Enable graph expansion |
| `entry_limit` | int | 10 | Max entry points |
| `context_limit` | int | 50 | Max expanded nodes |
| `include_entities` | bool | True | Include related entities |
| `include_schemas` | bool | False | Include schema nodes |
| `include_examples` | bool | False | Include example nodes |
| `max_tokens` | int | None | Token budget limit |
| `token_model` | str | "gpt-4" | Model for token counting |
| `expansion_types` | List[NodeType] | None | Node types for expansion |
| `request` | ContextRequest | None | Full request object (overrides params) |

## Example: Complete Integration

```python
#!/usr/bin/env python3
"""Complete example of ContextForge integration."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from contextforge import ContextForge, ContextForgeConfig
from contextforge.providers.embedding import SentenceTransformersProvider
from contextforge.providers.auth import JWTAuthProvider

# Validate required config
if not os.environ.get("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL environment variable is required")

# Initialize ContextForge
cf = ContextForge(
    config=ContextForgeConfig(
        db_schema="knowledge",
        admin_ui_enabled=True,
        admin_ui_title="Acme Knowledge Base",
        cors_origins="https://app.acme.com",
    ),
    embedding_provider=SentenceTransformersProvider(),
    auth_provider=JWTAuthProvider(
        secret_key=os.environ["JWT_SECRET_KEY"],
    ),
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify database
    status = await cf.check_database()
    if not status["connected"]:
        raise RuntimeError("Database connection failed")
    yield
    # Shutdown: cleanup
    await cf.dispose()

app = FastAPI(
    title="Acme API",
    lifespan=lifespan,
)

# Mount ContextForge
app.mount("/kb", cf.app)

# Your application routes
@app.get("/")
async def root():
    return {
        "app": "Acme API",
        "knowledge_base": "/kb/api",
        "admin_ui": "/kb/admin",
    }

@app.get("/health")
async def health():
    db_status = await cf.check_database()
    return {"status": "healthy", "database": db_status}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Troubleshooting

### "DATABASE_URL environment variable is required"

Set the environment variable:
```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db"
```

### "No embedding provider configured"

Either pass an embedding provider or install sentence-transformers:
```bash
pip install sentence-transformers
```

### "pgvector extension not found"

Install and enable pgvector:
```bash
# Ubuntu/Debian
sudo apt install postgresql-15-pgvector

# Enable in database
psql -d yourdb -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### CORS errors from frontend

Configure CORS origins:
```python
cf = ContextForge(
    config=ContextForgeConfig(
        cors_origins="http://localhost:3000,https://app.example.com",
    ),
    ...
)
```
