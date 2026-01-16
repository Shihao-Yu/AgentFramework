# ContextForge Features & Architecture

## System Overview

ContextForge is a Knowledge Verse system designed for AI agent context management. It evolved from a simple FAQ system into a comprehensive knowledge graph platform that combines multiple advanced techniques:

- **Knowledge Graph**: Structured representation using nodes and edges with NetworkX in-memory operations
- **Hybrid Search**: BM25 full-text search combined with vector similarity using Reciprocal Rank Fusion (RRF)
- **Query Generation**: Natural language to SQL/DSL/API query translation with schema-aware context injection
- **Multi-Tenant Isolation**: Tenant-based data partitioning with cross-tenant knowledge sharing capabilities

The system serves as a bridge between unstructured knowledge (FAQs, playbooks, documentation) and structured data sources (databases, APIs, search engines), enabling AI agents to retrieve relevant context for query generation and decision-making.

## Core Features

### 1. Knowledge Graph

The knowledge graph provides a flexible, typed graph structure for representing and connecting different types of knowledge.

**Node Types (11 types)**:
- `FAQ`: Question and answer pairs
- `PLAYBOOK`: Step-by-step procedures and workflows
- `PERMISSION_RULE`: Access control and authorization rules
- `SCHEMA_INDEX`: Dataset/table metadata
- `SCHEMA_FIELD`: Individual field/column definitions
- `EXAMPLE`: Verified Q&A examples for query generation
- `ENTITY`: Business entities and domain concepts
- `CONCEPT`: Abstract concepts that fields map to
- `QUERY_PLAN`: Saved query execution plans
- `PLAN_VERSION`: Versioned query plan snapshots
- `PROMPT_TEMPLATE`: Reusable prompt templates

**Edge Types (5 types)**:
- `RELATED`: General bidirectional semantic relationship
- `PARENT`: Hierarchical parent-child relationship (e.g., schema_index → schema_field)
- `EXAMPLE_OF`: Links examples to schemas they demonstrate
- `SHARED_TAG`: Auto-generated edges based on tag overlap
- `SIMILAR`: Auto-generated edges based on embedding similarity

**Graph Operations**:
- N-hop expansion from entry points
- Bidirectional traversal (both incoming and outgoing edges)
- NetworkX in-memory representation for fast graph algorithms
- Event-driven synchronization between PostgreSQL and in-memory graph
- Tenant-aware graph loading and filtering

**Implementation**:
- PostgreSQL as source of truth (knowledge_nodes, knowledge_edges tables)
- NetworkX DiGraph for in-memory operations
- GraphService (app/services/graph_service.py) manages graph lifecycle
- GraphSyncService handles DB-to-graph synchronization

### 2. Hybrid Search

Combines lexical and semantic search methods using Reciprocal Rank Fusion for optimal retrieval quality.

**Search Methods**:
- **BM25 (40% default weight)**: PostgreSQL full-text search with ts_vector
- **Vector Similarity (60% default weight)**: pgvector cosine similarity with 1024-dimensional embeddings

**Performance**:
- +18% NDCG improvement over vector-only search
- Configurable weights per request
- Support for filtering by knowledge type, tags, visibility, and status

**Features**:
- Query embedding generation via EmbeddingClient
- Reciprocal Rank Fusion (RRF) score combination
- Match source tracking (which method found each result)
- Analytics integration with hit tracking

**Implementation**:
- SearchService (app/services/search_service.py)
- PostgreSQL function: agent.search_knowledge_hybrid()
- Embedding storage in knowledge_nodes.embedding column (vector(1024))

### 3. Multi-Dialect Query Generation

Translates natural language questions into executable queries across multiple data source types.

**Supported Dialects**:
- **SQL**: PostgreSQL, MySQL, ClickHouse
- **DSL**: OpenSearch, Elasticsearch
- **API**: REST API request generation

**Schema-Aware Context Injection**:
- Retrieves relevant schema nodes (SCHEMA_INDEX, SCHEMA_FIELD)
- Finds similar examples (EXAMPLE nodes) for few-shot learning
- Injects field descriptions, data types, and relationships
- Uses concept mapping to understand business entities

**Query Generation Pipeline**:
1. Parse natural language question
2. Retrieve relevant schemas via hybrid search
3. Expand graph to find related fields and examples
4. Inject context into prompt template
5. Generate query using LLM
6. Validate and return structured query

**Implementation**:
- QueryForgeService (app/services/queryforge_service.py)
- KnowledgeVerseAdapter bridges Knowledge Verse and QueryForge
- ContextForge modules (app/contextforge/) provide source-specific parsers
- Prompt templates in app/contextforge/generation/prompt_templates.py

### 4. Multi-Tenant Architecture

Provides data isolation and access control across organizational boundaries.

**Tenant Isolation**:
- tenant_id column on all knowledge_nodes
- Tenant filtering at query level
- Cross-tenant edges possible for shared knowledge (e.g., "shared" tenant)

**Access Control**:
- User-tenant membership via tenant_users table
- Role-based access (VIEWER, EDITOR, ADMIN)
- Automatic inclusion of "shared" tenant for all users

**Visibility Levels**:
- `PUBLIC`: Accessible to all
- `INTERNAL`: Accessible within tenant
- `RESTRICTED`: Limited access

**Implementation**:
- TenantService (app/services/tenant_service.py)
- Tenant filtering in all search and retrieval operations
- Multi-tenant graph loading in GraphService

### 5. Q&A Example Learning

Stores verified question-answer-query triplets to improve query generation quality through few-shot learning.

**Example Storage**:
- EXAMPLE nodes contain: question, query, explanation, metadata
- Linked to schemas via EXAMPLE_OF edges
- Searchable via hybrid search for similar questions

**Learning Workflow**:
1. User submits question and receives generated query
2. User verifies query correctness
3. System stores as EXAMPLE node if verified
4. Future similar questions retrieve examples for context

**Benefits**:
- Improved query generation accuracy
- Domain-specific query patterns
- Reduced hallucination in generated queries

**Implementation**:
- Example nodes stored in knowledge_nodes table
- QueryForgeService manages example creation and retrieval
- ContextForge learning modules (app/contextforge/learning/)

### 6. Question Variants

Supports multiple phrasings of the same question to improve search coverage and matching.

**Variant Types**:
- Manual: User-created alternative phrasings
- Pipeline: Auto-generated from ticket analysis
- Import: Loaded from external sources

**Relationship**:
- 1:N relationship (one FAQ → many variants)
- Variants stored in question_variants table
- Linked to parent knowledge item via knowledge_item_id

**Search Integration**:
- Variants included in full-text search
- Improves recall for diverse user phrasings
- Automatic variant suggestion during staging

**Implementation**:
- VariantService (app/services/variant_service.py)
- question_variants table with source tracking
- Integration with staging workflow for auto-variant creation

### 7. Staging Workflow

Review queue for AI-generated content before publication, ensuring quality control.

**Staging Actions**:
- `NEW`: Create new knowledge item
- `MERGE`: Merge with existing item
- `ADD_VARIANT`: Add as question variant to existing item

**Workflow States**:
- `PENDING`: Awaiting review
- `APPROVED`: Accepted and published
- `REJECTED`: Declined

**Decision Logic**:
- Similarity ≥0.95: Auto-skip (near duplicate)
- Similarity ≥0.85: Suggest ADD_VARIANT
- Similarity ≥0.70: LLM decides MERGE vs NEW
- Similarity <0.70: Suggest NEW

**Features**:
- Batch approval/rejection
- Similarity-based duplicate detection
- Automatic variant extraction
- Audit trail of decisions

**Implementation**:
- StagingService (app/services/staging_service.py)
- staging_items table with action and status tracking
- Integration with ticket pipeline for automated content generation

### 8. Version History

Maintains historical snapshots of knowledge items with rollback capability.

**Retention**:
- 90-day retention period (configurable)
- Automatic snapshot on every update
- Version number incremented on each change

**Capabilities**:
- View version history
- Compare versions
- Rollback to previous version
- Audit trail of changes

**Stored Data**:
- Full content snapshot
- Metadata (title, tags, etc.)
- Change timestamp and author
- Version number

**Implementation**:
- VersionService (app/services/version_service.py)
- knowledge_versions table
- Automatic versioning on update operations

## Architecture Components

### Storage Layer

**PostgreSQL 15+ with pgvector**:
- `knowledge_nodes`: Core node storage with JSONB content and vector embeddings
- `knowledge_edges`: Relationship storage with metadata
- `question_variants`: Alternative question phrasings
- `knowledge_versions`: Historical snapshots
- `staging_items`: Review queue
- `knowledge_hits`: Analytics and usage tracking
- `tenant_users`: Multi-tenant access control

**Key Features**:
- pgvector extension for vector similarity search
- Full-text search with ts_vector
- JSONB for flexible content storage
- Async SQLAlchemy 2.0 with SQLModel

### Service Layer

**15 Core Services**:

1. **NodeService**: CRUD operations for knowledge nodes
2. **EdgeService**: Edge creation and management
3. **GraphService**: NetworkX graph operations and traversal
4. **GraphSyncService**: DB-to-graph synchronization
5. **SearchService**: Hybrid search implementation
6. **ContextService**: Agent context retrieval with graph expansion
7. **QueryForgeService**: Query generation and schema onboarding
8. **KnowledgeService**: High-level knowledge management (legacy)
9. **VariantService**: Question variant management
10. **VersionService**: Version history and rollback
11. **StagingService**: Review queue workflow
12. **RelationshipService**: Relationship management (legacy)
13. **TenantService**: Multi-tenant access control
14. **SettingsService**: System configuration
15. **MetricsService**: Analytics and reporting

**Service Patterns**:
- Dependency injection via FastAPI
- Async/await throughout
- Session-per-request pattern
- Service composition for complex operations

### API Layer

**13 Route Modules (75+ endpoints)**:

- `/api/nodes/*`: Node CRUD operations
  - GET /api/nodes - List nodes with filtering
  - POST /api/nodes - Create node
  - GET /api/nodes/{id} - Get node details
  - PUT /api/nodes/{id} - Update node
  - DELETE /api/nodes/{id} - Delete node

- `/api/edges/*`: Edge operations
  - GET /api/edges - List edges
  - POST /api/edges - Create edge
  - DELETE /api/edges/{id} - Delete edge

- `/api/graph/*`: Graph operations
  - POST /api/graph/expand - N-hop expansion
  - GET /api/graph/neighbors/{id} - Get neighbors
  - POST /api/graph/path - Find paths between nodes

- `/api/datasets/*`: Schema management
  - POST /api/datasets/onboard - Onboard new dataset
  - GET /api/datasets - List datasets
  - GET /api/datasets/{name}/fields - Get schema fields

- `/api/search`: Hybrid search
  - POST /api/search - Execute hybrid search

- `/api/context`: Agent context retrieval
  - POST /api/context - Get structured context for agents

- `/api/knowledge/*`: Legacy knowledge operations
  - GET /api/knowledge - List knowledge items
  - POST /api/knowledge - Create item
  - GET /api/knowledge/{id}/variants - Manage variants
  - GET /api/knowledge/{id}/versions - Version history

- `/api/staging/*`: Staging workflow
  - GET /api/staging - List pending items
  - POST /api/staging/{id}/approve - Approve item
  - POST /api/staging/{id}/reject - Reject item

- `/api/metrics/*`: Analytics
  - GET /api/metrics/summary - Overall statistics
  - GET /api/metrics/top-items - Top performing items
  - GET /api/metrics/daily-trend - Usage trends

- `/api/settings`: System configuration
- `/api/tenants/*`: Tenant management
- `/api/sync`: Graph synchronization

**API Features**:
- OpenAPI/Swagger documentation
- Request validation with Pydantic
- Async request handling
- Error handling and logging

### Client Layer

**Abstract Clients**:

1. **EmbeddingClient**: Generate vector embeddings
   - Abstract interface for embedding generation
   - Mock implementation for development
   - Supports batch embedding
   - Returns 1024-dimensional vectors

2. **InferenceClient**: LLM inference calls
   - Abstract interface for LLM calls
   - Mock implementation for development
   - Supports structured output
   - Used for query generation and enrichment

**Customization**:
- Replace mock clients with production implementations
- Dependency injection via app/core/dependencies.py
- Support for multiple embedding models
- Configurable via environment variables

## Design Principles

### 1. PostgreSQL as Source of Truth

All knowledge state is persisted in PostgreSQL. In-memory structures (NetworkX graph) are derived from the database and can be rebuilt at any time.

**Benefits**:
- ACID guarantees for knowledge updates
- Reliable backup and recovery
- SQL query capabilities
- Mature ecosystem

### 2. NetworkX for Fast In-Memory Graph Operations

Graph traversal and algorithms use NetworkX for performance, while PostgreSQL stores the canonical graph state.

**Benefits**:
- Fast graph algorithms (BFS, DFS, shortest path)
- Rich graph analysis capabilities
- Python-native API
- Separation of concerns (storage vs. computation)

**Why not Neo4j?** Evaluated Neo4j but chose PostgreSQL + NetworkX because:
- Primary workload is **hybrid search** (BM25 + vector), not graph traversal—Neo4j lacks native BM25/pgvector equivalents
- Graph traversals are **shallow** (2-3 hops max for context expansion)—NetworkX handles this efficiently in-memory
- Graph **fits in memory** and is cached in Redis—no need for a dedicated graph database
- Avoids **operational complexity** of maintaining two databases and keeping them in sync

Neo4j would make sense if we needed deep traversals (5+ hops), complex pattern matching (Cypher), or graph algorithms (PageRank, community detection) at scale.

### 3. Event-Driven Sync Between DB and Graph

Changes to nodes/edges trigger graph updates to maintain consistency.

**Mechanisms**:
- GraphSyncService monitors graph_version
- Incremental updates for efficiency
- Force reload option for full refresh
- Tenant-aware synchronization

### 4. Async/Await Throughout

All I/O operations use async/await for scalability and performance.

**Benefits**:
- Non-blocking database queries
- Concurrent request handling
- Efficient resource utilization
- FastAPI native async support

### 5. Multi-Tenant by Default

All data models include tenant_id, enforcing isolation at the data layer.

**Benefits**:
- Data isolation guarantees
- Simplified access control
- Shared knowledge support
- Scalable multi-organization deployment

## Data Flow

### Context Retrieval Flow

1. **User submits question** via POST /api/context
2. **Hybrid search** retrieves relevant entry point nodes
   - BM25 full-text search (40%)
   - Vector similarity search (60%)
   - RRF score combination
3. **Graph expansion** finds related context
   - N-hop traversal from entry points
   - Filter by node types and edge types
   - Collect related entities, schemas, examples
4. **Context assembly** structures results
   - Entry points (direct matches)
   - Context nodes (graph expansion)
   - Entities (business concepts)
   - Statistics (search and expansion metrics)
5. **Response returned** with confidence scores

### Query Generation Flow

1. **User submits natural language question** via QueryForge API
2. **Schema retrieval** finds relevant datasets
   - Hybrid search for SCHEMA_INDEX nodes
   - Graph expansion to SCHEMA_FIELD nodes
3. **Example retrieval** finds similar Q&A pairs
   - Search EXAMPLE nodes by question similarity
   - Filter by dataset and query type
4. **Context injection** builds prompt
   - Schema descriptions and field metadata
   - Similar examples for few-shot learning
   - Business entity mappings (CONCEPT nodes)
5. **Query generation** via LLM
   - Structured prompt with context
   - Source-specific query syntax
   - Validation and error handling
6. **Query returned** with explanation and confidence

### Staging Workflow Flow

1. **Pipeline analyzes ticket** and extracts knowledge
2. **Similarity search** finds existing items
3. **Decision logic** determines action
   - High similarity (≥0.95): Skip
   - Medium-high (≥0.85): Add variant
   - Medium (≥0.70): LLM decides merge vs new
   - Low (<0.70): Create new
4. **Staging item created** with suggested action
5. **Human reviewer** approves or rejects
6. **Action executed** on approval
   - NEW: Create knowledge node
   - MERGE: Update existing node
   - ADD_VARIANT: Add to variants table
7. **Analytics updated** with decision outcome

## Evolution from FAQ to Knowledge Verse

### Original FAQ System
- Simple question-answer pairs
- Keyword-based search
- Flat structure
- Single knowledge type

### Knowledge Verse Transformation
- **Graph-based context**: Relationships between knowledge items
- **Hybrid search**: BM25 + vector similarity
- **Multiple node types**: FAQs, playbooks, schemas, examples, entities
- **Schema integration**: Bridge to structured data sources
- **Query generation**: Natural language to SQL/DSL/API
- **Multi-tenant**: Organizational isolation
- **Staging workflow**: Quality control for AI-generated content

### Key Innovation

The primary innovation is **graph-based context expansion** rather than simple FAQ lookup. Instead of returning a single FAQ answer, the system:

1. Finds relevant entry points via hybrid search
2. Expands the graph to discover related knowledge
3. Assembles a rich context package including:
   - Direct answers (FAQs, playbooks)
   - Related concepts and entities
   - Schema information for query generation
   - Examples for few-shot learning
4. Enables AI agents to make informed decisions with comprehensive context

This approach transforms ContextForge from a simple FAQ retrieval system into a comprehensive knowledge platform that bridges unstructured knowledge and structured data sources.
