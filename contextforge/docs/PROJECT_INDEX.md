# ContextForge Project Index

**Version:** 1.1  
**Last Updated:** January 14, 2026

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Project Overview](#project-overview)
3. [Documentation Index](#documentation-index)
4. [Module Reference](#module-reference)
5. [Key Concepts](#key-concepts)
6. [API Overview](#api-overview)
7. [Examples Reference](#examples-reference)
8. [Technology Stack](#technology-stack)
9. [Development Guide](#development-guide)

---

## Quick Start

New to ContextForge? Start here:

- [QUICKSTART.md](QUICKSTART.md) - Get up and running in 5 minutes
- [Installation Guide](#installation) - Detailed setup instructions
- [API Documentation](http://localhost:8000/docs) - Interactive Swagger UI (when server is running)

### Installation

```bash
# 1. Clone and navigate
cd /path/to/contextforge

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or .\venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Set up database
createdb faq_knowledge_base
psql -d faq_knowledge_base -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 5. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 6. Run migrations
alembic upgrade head

# 7. Start server
uvicorn app.main:app --reload
```

Access the API at http://localhost:8000

---

## Project Overview

### What is ContextForge?

ContextForge is a **Knowledge Verse** system designed for AI agent context management. It evolved from a simple FAQ system into a sophisticated knowledge graph platform that combines:

- **Hybrid Search**: BM25 full-text search (40%) + Vector similarity (60%) with Reciprocal Rank Fusion
- **Knowledge Graph**: Multi-type nodes connected by typed edges with graph traversal capabilities
- **Multi-tenant Architecture**: Tenant-based isolation for enterprise deployments
- **Schema Onboarding**: Automated dataset ingestion and schema indexing
- **Query Generation**: Natural language to SQL/DSL/API query translation
- **Staging Workflow**: Review queue for AI-generated content

### Key Features

- **8 Node Types**: FAQ, Playbook, Permission Rule, Schema Index, Schema Field, Example, Entity, Concept
- **5 Edge Types**: Related, Parent, Example Of, Shared Tag, Similar
- **75+ API Endpoints**: Comprehensive REST API for all operations
- **PostgreSQL + pgvector**: Native vector similarity search without external dependencies
- **FastAPI Framework**: Modern async Python web framework with automatic OpenAPI docs
- **SQLModel ORM**: Type-safe database operations with Pydantic integration

### Project Statistics

| Metric | Count |
|--------|-------|
| Total Python Files | 100+ |
| Services | 15 |
| API Routes | 12 modules |
| API Endpoints | 75+ |
| Node Types | 8 |
| Edge Types | 5 |
| Database Tables | 20+ |
| Lines of Code (routes) | 2,267 |

---

## Documentation Index

### Core Documentation

| Document | Description | Status |
|----------|-------------|--------|
| [QUICKSTART.md](QUICKSTART.md) | Getting started guide with examples | Complete |
| [API_REFERENCE.md](API_REFERENCE.md) | Complete API endpoint documentation | Complete |
| [RETRIEVAL_DESIGN.md](RETRIEVAL_DESIGN.md) | Hybrid search architecture and algorithms | Complete |
| [SCHEMA_ONBOARDING.md](SCHEMA_ONBOARDING.md) | Dataset onboarding workflow and examples | Complete |
| [FEATURES_ARCHITECTURE.md](FEATURES_ARCHITECTURE.md) | Feature overview and system architecture | Complete |
| [COMPLETE_WORKFLOW.md](COMPLETE_WORKFLOW.md) | End-to-end workflow examples | Complete |
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | Developer reference and contribution guide | Complete |
| [QUERY_GENERATION.md](QUERY_GENERATION.md) | How NL-to-SQL query generation works | Complete |
| [CONTEXT_RAG.md](CONTEXT_RAG.md) | Context assembly pipeline for AI agents | Complete |
| [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) | How to integrate ContextForge as a library | Complete |
| [LIBRARY_DESIGN.md](LIBRARY_DESIGN.md) | Library architecture and design decisions | Complete |

### Additional Resources

- [README.md](../README.md) - Project overview and quick start
- [API Docs (Swagger)](http://localhost:8000/docs) - Interactive API documentation
- [API Docs (ReDoc)](http://localhost:8000/redoc) - Alternative API documentation
- [Alembic Migrations](../alembic/versions/) - Database schema evolution

---

## Module Reference

### Core Application (`app/`)

#### Services (`app/services/`)

Business logic layer with 15 service classes:

| Service | Purpose | Key Methods |
|---------|---------|-------------|
| `QueryForgeService` | Schema onboarding and query generation | `onboard_dataset()`, `generate_query()` |
| `KnowledgeVerseAdapter` | Adapter for ContextForge integration | `store_schema()`, `retrieve_context()` |
| `NodeService` | Node CRUD operations | `create()`, `get()`, `update()`, `delete()` |
| `EdgeService` | Edge CRUD operations | `create_edge()`, `get_edges()`, `delete_edge()` |
| `GraphService` | Graph traversal and analysis | `get_neighbors()`, `find_path()`, `get_stats()` |
| `SearchService` | Hybrid search implementation | `hybrid_search()`, `vector_search()`, `bm25_search()` |
| `ContextService` | Context retrieval for AI agents | `get_context()`, `build_context()` |
| `KnowledgeService` | Legacy knowledge item management | `create_item()`, `search_items()` |
| `TenantService` | Multi-tenancy management | `create_tenant()`, `manage_access()` |
| `StagingService` | Review queue for AI-generated content | `approve()`, `reject()`, `list_pending()` |
| `MetricsService` | Analytics and usage tracking | `get_summary()`, `track_hit()` |
| `VariantService` | Question variant management | `add_variant()`, `list_variants()` |
| `VersionService` | Version history and rollback | `create_version()`, `rollback()` |
| `RelationshipService` | Legacy relationship management | `create_relationship()` |
| `SettingsService` | System configuration | `get_settings()`, `update_settings()` |

#### Models (`app/models/`)

SQLModel entities for database tables:

| Model | Description | Key Fields |
|-------|-------------|------------|
| `KnowledgeNode` | Graph nodes (8 types) | `id`, `node_type`, `title`, `content`, `embedding` |
| `KnowledgeEdge` | Graph edges (5 types) | `id`, `edge_type`, `source_id`, `target_id`, `weight` |
| `KnowledgeItem` | Legacy knowledge items | `id`, `knowledge_type`, `question`, `answer` |
| `Tenant` | Multi-tenant isolation | `id`, `name`, `slug`, `settings` |
| `StagingItem` | Review queue items | `id`, `action`, `status`, `source_data` |
| `Analytics` | Usage tracking | `id`, `item_id`, `hit_count`, `timestamp` |

#### Schemas (`app/schemas/`)

Pydantic request/response models:

- `nodes.py` - Node API schemas
- `edges.py` - Edge API schemas
- `search.py` - Search request/response
- `context.py` - Context retrieval schemas
- `knowledge.py` - Legacy knowledge schemas
- `tenant.py` - Tenant management schemas
- `staging.py` - Staging workflow schemas
- `metrics.py` - Analytics schemas
- `datasets.py` - Dataset onboarding schemas
- `common.py` - Shared schemas and utilities

#### Routes (`app/routes/`)

API endpoint definitions (12 modules, 75+ endpoints):

| Route Module | Endpoints | Purpose |
|--------------|-----------|---------|
| `nodes.py` | 7 | Node CRUD, search, versioning |
| `edges.py` | 6 | Edge CRUD, bulk operations |
| `graph.py` | 7 | Graph stats, traversal, suggestions |
| `search.py` | 1 | Hybrid search |
| `context.py` | 1 | Context retrieval for AI agents |
| `datasets.py` | 10 | Schema onboarding, query generation, examples |
| `knowledge.py` | 13 | Legacy knowledge CRUD, variants, relationships, versions |
| `tenants.py` | 9 | Tenant management, access control |
| `staging.py` | 7 | Review queue management |
| `metrics.py` | 5 | Analytics and statistics |
| `settings.py` | 2 | System configuration |
| `sync.py` | 6 | Graph synchronization, edge generation |

#### Core (`app/core/`)

Configuration and infrastructure:

- `config.py` - Environment configuration and settings
- `database.py` - Database connection and session management
- `dependencies.py` - FastAPI dependency injection

#### Clients (`app/clients/`)

Abstract interfaces for external services:

- `embedding_client.py` - Embedding generation interface
- `inference_client.py` - LLM inference interface
- `base.py` - Base client protocols

### ContextForge Module (`app/contextforge/`)

Migrated from AgenticSearch QueryForge, adapted for Knowledge Verse:

#### Core (`app/contextforge/core/`)

- `models.py` - Core data models
- `protocols.py` - Protocol definitions
- `constants.py` - System constants
- `utils.py` - Utility functions
- `planning_models.py` - Query planning models

#### Schema (`app/contextforge/schema/`)

- `yaml_schema.py` - YAML schema parsing
- `api_schema.py` - API schema definitions
- `field_schema.py` - Field specification models
- `example_schema.py` - Example schema handling
- `node_mapping.py` - Schema to node mapping

#### Retrieval (`app/contextforge/retrieval/`)

- `graph_retriever.py` - Graph-based context retrieval
- `example_retriever.py` - Example-based retrieval
- `context.py` - Context building and formatting

#### Storage (`app/contextforge/storage/`)

- `postgres_adapter.py` - PostgreSQL storage adapter

#### Prompts (`app/contextforge/prompts/`)

- `manager.py` - Prompt template management
- `store.py` - Prompt storage and versioning
- `models.py` - Prompt data models
- `langfuse_sync.py` - Langfuse integration

#### Sources (`app/contextforge/sources/`)

- `base.py` - Base source interface

#### Generation (`app/contextforge/generation/`)

Query generation pipeline components

#### Graph (`app/contextforge/graph/`)

Graph analysis and traversal utilities

#### Learning (`app/contextforge/learning/`)

Learning and adaptation components

#### CLI (`app/contextforge/cli/`)

Command-line interface tools

### Pipeline (`pipeline/`)

Ticket-to-knowledge conversion pipeline:

- `service.py` - Pipeline orchestration
- `prompts.py` - LLM prompts for extraction
- `models.py` - Pipeline data models

### Jobs (`jobs/`)

Background job implementations:

- `ticket_pipeline_job.py` - Automated ticket processing

### Database (`alembic/`)

Database migrations:

- `versions/001_initial_schema.py` - Initial database schema
- `versions/002_add_system_settings.py` - System settings table
- Additional migrations for schema evolution

---

## Key Concepts

### Node Types

ContextForge supports 8 node types in the Knowledge Verse:

| Node Type | Description | Use Case |
|-----------|-------------|----------|
| `FAQ` | Question and answer pairs | Customer support, documentation |
| `PLAYBOOK` | Step-by-step procedures | Operational guides, runbooks |
| `PERMISSION_RULE` | Access control rules | Authorization, security policies |
| `SCHEMA_INDEX` | Dataset schema metadata | Database tables, API endpoints |
| `SCHEMA_FIELD` | Individual field specifications | Table columns, API parameters |
| `EXAMPLE` | Query examples with results | Training data, test cases |
| `ENTITY` | Business entities | Customers, products, orders |
| `CONCEPT` | Abstract concepts | Domain knowledge, terminology |

Additional node types (planned):
- `QUERY_PLAN` - Saved query execution plans
- `PLAN_VERSION` - Query plan versions
- `PROMPT_TEMPLATE` - LLM prompt templates

### Edge Types

5 edge types connect nodes in the graph:

| Edge Type | Direction | Description | Auto-Generated |
|-----------|-----------|-------------|----------------|
| `RELATED` | Bidirectional | General semantic relationship | No |
| `PARENT` | Directional | Hierarchical parent-child | No |
| `EXAMPLE_OF` | Directional | Example demonstrates schema | No |
| `SHARED_TAG` | Bidirectional | Computed from tag overlap | Yes |
| `SIMILAR` | Bidirectional | Computed from embedding similarity | Yes |

### Hybrid Search

ContextForge implements a sophisticated hybrid search combining:

1. **BM25 Full-Text Search (40%)**
   - PostgreSQL's built-in `ts_vector` and `ts_query`
   - Keyword-based ranking with term frequency
   - Fast and efficient for exact matches

2. **Vector Similarity Search (60%)**
   - pgvector extension for cosine similarity
   - 1024-dimensional embeddings
   - Semantic understanding of queries

3. **Reciprocal Rank Fusion (RRF)**
   - Combines rankings from both methods
   - Formula: `RRF(d) = Σ 1/(k + rank(d))` where k=60
   - Configurable weights per request

### Knowledge Graph

The graph structure enables:

- **Traversal**: Find related nodes via edges
- **Path Finding**: Discover connections between nodes
- **Component Analysis**: Identify isolated subgraphs
- **Orphan Detection**: Find unconnected nodes
- **Suggestion Engine**: Recommend related content

### Multi-Tenant Architecture

Tenant-based isolation ensures:

- **Data Separation**: Each tenant has isolated data
- **Access Control**: Role-based permissions (viewer, editor, admin)
- **Custom Settings**: Per-tenant configuration
- **Shared Resources**: Optional cross-tenant sharing

---

## API Overview

### Endpoint Categories

**75+ endpoints** organized into 12 functional categories:

#### 1. Nodes (7 endpoints)

- `GET /api/nodes` - List nodes with filtering and pagination
- `GET /api/nodes/search` - Search nodes by query
- `GET /api/nodes/{node_id}` - Get node details
- `POST /api/nodes` - Create new node
- `PUT /api/nodes/{node_id}` - Update node
- `DELETE /api/nodes/{node_id}` - Delete node
- `GET /api/nodes/{node_id}/versions` - Get version history

#### 2. Edges (6 endpoints)

- `GET /api/edges` - List edges with filtering
- `GET /api/edges/{edge_id}` - Get edge details
- `POST /api/edges` - Create edge
- `POST /api/edges/bulk` - Bulk create edges
- `PUT /api/edges/{edge_id}` - Update edge
- `DELETE /api/edges/{edge_id}` - Delete edge

#### 3. Graph (7 endpoints)

- `GET /api/graph/stats` - Graph statistics
- `GET /api/graph/neighbors/{node_id}` - Get neighbors
- `GET /api/graph/paths` - Find paths between nodes
- `GET /api/graph/component/{node_id}` - Get connected component
- `GET /api/graph/orphans` - Find orphaned nodes
- `GET /api/graph/suggestions/{node_id}` - Get relationship suggestions
- `POST /api/graph/reload` - Reload graph cache

#### 4. Search (1 endpoint)

- `POST /api/search` - Hybrid search with BM25 + vector

#### 5. Context (1 endpoint)

- `POST /api/context` - Get context for AI agents

#### 6. Datasets (10 endpoints)

- `GET /api/datasets/status` - QueryForge status
- `POST /api/datasets/onboard` - Onboard new dataset
- `GET /api/datasets` - List datasets
- `GET /api/datasets/{dataset_name}` - Get dataset details
- `DELETE /api/datasets/{dataset_name}` - Delete dataset
- `POST /api/datasets/generate` - Generate query from NL
- `POST /api/datasets/examples` - Add query example
- `GET /api/datasets/examples` - List examples
- `PATCH /api/datasets/examples/{example_id}/verify` - Verify example

#### 7. Knowledge (13 endpoints - Legacy)

- `GET /api/knowledge` - List knowledge items
- `GET /api/knowledge/{item_id}` - Get item details
- `POST /api/knowledge` - Create item
- `PUT /api/knowledge/{item_id}` - Update item
- `DELETE /api/knowledge/{item_id}` - Delete item
- `GET /api/knowledge/{item_id}/variants` - List variants
- `POST /api/knowledge/{item_id}/variants` - Add variant
- `DELETE /api/knowledge/{item_id}/variants/{variant_id}` - Delete variant
- `GET /api/knowledge/{item_id}/relationships` - List relationships
- `POST /api/knowledge/{item_id}/relationships` - Create relationship
- `DELETE /api/knowledge/{item_id}/relationships/{rel_id}` - Delete relationship
- `GET /api/knowledge/{item_id}/versions` - List versions
- `POST /api/knowledge/{item_id}/versions/{version}/rollback` - Rollback

#### 8. Tenants (9 endpoints)

- `GET /api/tenants` - List tenants
- `GET /api/tenants/me` - Get user's tenants
- `GET /api/tenants/{tenant_id}` - Get tenant details
- `POST /api/tenants` - Create tenant
- `PUT /api/tenants/{tenant_id}` - Update tenant
- `DELETE /api/tenants/{tenant_id}` - Delete tenant
- `POST /api/tenants/{tenant_id}/access` - Grant access
- `PUT /api/tenants/{tenant_id}/access/{user_id}` - Update access
- `DELETE /api/tenants/{tenant_id}/access/{user_id}` - Revoke access

#### 9. Staging (7 endpoints)

- `GET /api/staging` - List staging items
- `GET /api/staging/counts` - Get counts by status
- `GET /api/staging/{staging_id}` - Get staging item
- `GET /api/staging/{staging_id}/merge-target` - Get merge target
- `PATCH /api/staging/{staging_id}` - Update staging item
- `POST /api/staging/{staging_id}/approve` - Approve item
- `POST /api/staging/{staging_id}/reject` - Reject item

#### 10. Metrics (5 endpoints)

- `GET /api/metrics/summary` - Overall statistics
- `GET /api/metrics/top-items` - Top performing items
- `GET /api/metrics/daily-trend` - Daily hit trend
- `GET /api/metrics/tags` - Tag statistics
- `GET /api/metrics/items/{item_id}` - Item-specific stats

#### 11. Settings (2 endpoints)

- `GET /api/settings` - Get system settings
- `PATCH /api/settings` - Update settings

#### 12. Sync (6 endpoints)

- `GET /api/sync/status` - Sync status
- `POST /api/sync/process` - Process sync events
- `POST /api/sync/generate/shared-tags` - Generate shared tag edges
- `POST /api/sync/generate/similar` - Generate similarity edges
- `POST /api/sync/generate/all` - Generate all auto edges
- `DELETE /api/sync/events/cleanup` - Cleanup old events

### Authentication

All endpoints support tenant-based authentication via headers:

```http
X-Tenant-ID: tenant_uuid
X-User-ID: user_uuid
```

### Response Format

Standard response envelope:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "metadata": {
    "timestamp": "2026-01-13T12:00:00Z",
    "request_id": "req_123"
  }
}
```

Paginated responses:

```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

---

## Examples Reference

### Sample Schemas

Located in `examples/sample_schemas/`:

- Database schema examples
- API schema examples
- YAML schema definitions

### Code Examples

See [QUICKSTART.md](QUICKSTART.md) and [COMPLETE_WORKFLOW.md](COMPLETE_WORKFLOW.md) for:

- Creating nodes and edges
- Performing hybrid search
- Onboarding datasets
- Generating queries
- Managing tenants
- Using the staging workflow

---

## Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Primary language |
| **FastAPI** | Latest | Web framework |
| **SQLModel** | Latest | ORM with Pydantic integration |
| **PostgreSQL** | 15+ | Primary database |
| **pgvector** | Latest | Vector similarity search |
| **Alembic** | Latest | Database migrations |
| **Pydantic** | 2.x | Data validation |
| **SQLAlchemy** | 2.0 | Database toolkit |

### Key Dependencies

- `asyncpg` - Async PostgreSQL driver
- `uvicorn` - ASGI server
- `python-dotenv` - Environment configuration
- `httpx` - Async HTTP client
- `pytest` - Testing framework

### Database Extensions

- `pgvector` - Vector similarity search
- `pg_trgm` - Trigram similarity for fuzzy matching
- `uuid-ossp` - UUID generation

### Storage

- **Primary**: PostgreSQL with pgvector
- **No ChromaDB**: Unlike the original agentic_search, ContextForge uses PostgreSQL exclusively
- **No External Vector DB**: All vector operations via pgvector

### Architecture Patterns

- **Async/Await**: Full async support with SQLAlchemy 2.0
- **Dependency Injection**: FastAPI's DI system
- **Service Layer**: Business logic separated from routes
- **Repository Pattern**: Data access abstraction
- **Multi-tenancy**: Tenant-based data isolation

---

## Development Guide

### Project Structure

```
contextforge/
├── alembic/                    # Database migrations
│   ├── versions/               # Migration files
│   └── env.py                  # Alembic configuration
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── core/                   # Configuration and infrastructure
│   │   ├── config.py           # Settings and environment
│   │   ├── database.py         # Database connection
│   │   └── dependencies.py     # DI providers
│   ├── models/                 # SQLModel database models
│   │   ├── nodes.py            # KnowledgeNode model
│   │   ├── edges.py            # KnowledgeEdge model
│   │   ├── knowledge.py        # Legacy KnowledgeItem model
│   │   ├── tenant.py           # Tenant model
│   │   ├── staging.py          # StagingItem model
│   │   ├── analytics.py        # Analytics model
│   │   ├── enums.py            # Enumerations
│   │   └── base.py             # Base model classes
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/               # Business logic layer (15 services)
│   ├── routes/                 # API endpoints (12 modules)
│   ├── clients/                # External service interfaces
│   └── contextforge/           # ContextForge module (migrated from AgenticSearch)
│       ├── core/               # Core models and protocols
│       ├── schema/             # Schema parsing and mapping
│       ├── retrieval/          # Context retrieval
│       ├── storage/            # Storage adapters
│       ├── prompts/            # Prompt management
│       ├── sources/            # Data source interfaces
│       ├── generation/         # Query generation
│       ├── graph/              # Graph utilities
│       ├── learning/           # Learning components
│       └── cli/                # CLI tools
├── pipeline/                   # Ticket-to-knowledge pipeline
├── jobs/                       # Background jobs
├── tests/                      # Test suite
├── examples/                   # Example schemas and code
├── docs/                       # Documentation
├── pyproject.toml              # Python project configuration
├── alembic.ini                 # Alembic configuration
├── .env.example                # Environment template
└── README.md                   # Project overview
```

### Development Workflow

1. **Setup Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   ```

2. **Database Setup**
   ```bash
   createdb faq_knowledge_base
   psql -d faq_knowledge_base -c "CREATE EXTENSION IF NOT EXISTS vector;"
   alembic upgrade head
   ```

3. **Run Tests**
   ```bash
   pytest tests/ -v
   pytest tests/ -v --cov=app --cov-report=html
   ```

4. **Code Quality**
   ```bash
   black app/ pipeline/ jobs/
   ruff check app/ pipeline/ jobs/
   mypy app/ pipeline/ jobs/
   ```

5. **Create Migration**
   ```bash
   alembic revision --autogenerate -m "description"
   alembic upgrade head
   ```

6. **Run Server**
   ```bash
   uvicorn app.main:app --reload
   ```

### Adding New Features

See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for detailed instructions on:

- Adding new node types
- Creating new services
- Adding API endpoints
- Writing database migrations
- Implementing custom retrievers
- Extending the graph

### Testing

- Unit tests in `tests/`
- Integration tests with test database
- API tests with TestClient
- Coverage reports with pytest-cov

### Contributing

1. Create feature branch
2. Write tests
3. Implement feature
4. Run code quality checks
5. Submit pull request

---

## Additional Resources

### External Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)

### Related Projects

- **agentic_search**: Original QueryForge implementation (deprecated for ContextForge)
- **admin-ui**: React-based admin interface for ContextForge

### Support

For questions and issues:

- Check existing documentation
- Review API documentation at http://localhost:8000/docs
- Consult the developer guide
- Review test cases for examples

---

**Last Updated:** January 13, 2026  
**Maintained By:** ContextForge Team
