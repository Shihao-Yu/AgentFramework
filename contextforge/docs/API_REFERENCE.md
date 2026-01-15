# ContextForge API Reference

Complete API reference for ContextForge services, adapters, and database functions.

## Table of Contents

- [QueryForgeService](#queryforgeservice)
  - [Initialization](#initialization)
  - [Static Methods](#static-methods)
  - [Schema Onboarding](#schema-onboarding)
  - [Query Generation](#query-generation)
  - [Example Management](#example-management)
  - [Dataset Management](#dataset-management)
- [KnowledgeVerseAdapter](#knowledgeverseadapter)
  - [Initialization](#initialization-1)
  - [Schema Field Retrieval](#schema-field-retrieval)
  - [Q&A Example Retrieval](#qa-example-retrieval)
  - [Master Config](#master-config)
  - [Utility Methods](#utility-methods)
- [Database Functions](#database-functions)
  - [hybrid_search_nodes](#hybrid_search_nodes)
- [Enumerations](#enumerations)
  - [Node Types](#node-types)
  - [Edge Types](#edge-types)

---

## QueryForgeService

**Location:** `app/services/queryforge_service.py`

The QueryForgeService provides comprehensive functionality for schema onboarding, query generation, and example management. All methods are asynchronous and must be called with `await`.

### Initialization

```python
QueryForgeService(
    session: AsyncSession,
    embedding_client: EmbeddingClient,
    vector_store: Optional[Any] = None,
    llm_client: Optional[Any] = None,
)
```

**Parameters:**
- `session` (AsyncSession): SQLAlchemy async database session
- `embedding_client` (EmbeddingClient): Client for generating embeddings
- `vector_store` (Optional[Any]): Optional vector store instance (defaults to None)
- `llm_client` (Optional[Any]): Optional LLM client for query generation (defaults to None)

**Example:**
```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.queryforge_service import QueryForgeService
from app.services.embedding_client import EmbeddingClient

async def create_service(session: AsyncSession):
    embedding_client = EmbeddingClient()
    service = QueryForgeService(
        session=session,
        embedding_client=embedding_client
    )
    return service
```

---

### Static Methods

#### is_available

```python
@staticmethod
def is_available() -> bool
```

Check if QueryForge/ContextForge is available in the current environment.

**Returns:**
- `bool`: True if QueryForge is available, False otherwise

**Example:**
```python
if QueryForgeService.is_available():
    print("QueryForge is ready to use")
else:
    print("QueryForge is not available")
```

---

#### list_available_sources

```python
@staticmethod
def list_available_sources() -> List[str]
```

List all available source types that can be onboarded.

**Returns:**
- `List[str]`: List of available source type identifiers (e.g., ["postgresql", "mongodb", "api"])

**Example:**
```python
sources = QueryForgeService.list_available_sources()
print(f"Available sources: {sources}")
```

---

### Schema Onboarding

#### onboard_dataset

```python
async def onboard_dataset(
    tenant_id: str,
    dataset_name: str,
    source_type: str,
    raw_schema: Dict[str, Any],
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    enable_enrichment: bool = True,
    created_by: Optional[str] = None
) -> Dict[str, Any]
```

Onboard a new dataset schema into the knowledge graph for query generation.

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant
- `dataset_name` (str): Name of the dataset to onboard
- `source_type` (str): Type of data source (e.g., "postgresql", "mongodb")
- `raw_schema` (Dict[str, Any]): Raw schema definition from the source
- `description` (Optional[str]): Human-readable description of the dataset
- `tags` (Optional[List[str]]): Tags for categorization
- `enable_enrichment` (bool): Whether to enrich schema with AI-generated metadata (default: True)
- `created_by` (Optional[str]): User identifier who created the dataset

**Returns:**
- `Dict[str, Any]` with keys:
  - `status` (str): "success" or "error"
  - `dataset_name` (str): Name of the onboarded dataset
  - `source_type` (str): Source type identifier
  - `schema_index_id` (str): Unique ID of the schema index node
  - `field_count` (int): Number of fields indexed
  - `fields` (List[Dict]): List of indexed field specifications
  - `errors` (Optional[List[str]]): Any errors encountered during onboarding

**Example:**
```python
# Onboard a PostgreSQL table schema
raw_schema = {
    "table_name": "users",
    "columns": [
        {"name": "id", "type": "integer", "primary_key": True},
        {"name": "email", "type": "varchar", "nullable": False},
        {"name": "created_at", "type": "timestamp", "nullable": False}
    ]
}

result = await service.onboard_dataset(
    tenant_id="tenant_123",
    dataset_name="users_table",
    source_type="postgresql",
    raw_schema=raw_schema,
    description="User account information",
    tags=["users", "authentication"],
    enable_enrichment=True,
    created_by="admin@example.com"
)

if result["status"] == "success":
    print(f"Onboarded {result['field_count']} fields")
    print(f"Schema ID: {result['schema_index_id']}")
```

---

### Query Generation

#### generate_query

```python
async def generate_query(
    tenant_id: str,
    dataset_name: str,
    question: str,
    include_explanation: bool = True,
    use_pipeline: bool = True
) -> Dict[str, Any]
```

Generate a query (SQL, MongoDB, etc.) from a natural language question.

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant
- `dataset_name` (str): Name of the dataset to query
- `question` (str): Natural language question
- `include_explanation` (bool): Whether to include explanation of the query (default: True)
- `use_pipeline` (bool): Whether to use the full QueryGenerationPipeline (default: True)

**Returns:**
- `Dict[str, Any]` with keys:
  - `status` (str): "success" or "error"
  - `query` (str): Generated query string
  - `query_type` (str): Type of query (e.g., "SELECT", "AGGREGATE")
  - `explanation` (Optional[str]): Human-readable explanation of the query
  - `confidence` (float): Confidence score (0.0 to 1.0)

**Example:**
```python
result = await service.generate_query(
    tenant_id="tenant_123",
    dataset_name="users_table",
    question="How many users signed up last month?",
    include_explanation=True,
    use_pipeline=True
)

if result["status"] == "success":
    print(f"Query: {result['query']}")
    print(f"Type: {result['query_type']}")
    print(f"Confidence: {result['confidence']}")
    if result.get("explanation"):
        print(f"Explanation: {result['explanation']}")
```

---

### Example Management

#### add_example

```python
async def add_example(
    tenant_id: str,
    dataset_name: str,
    question: str,
    query: str,
    query_type: Optional[str] = None,
    explanation: Optional[str] = None,
    verified: bool = False,
    created_by: Optional[str] = None
) -> Dict[str, Any]
```

Add a question-query example pair to improve future query generation.

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant
- `dataset_name` (str): Name of the dataset
- `question` (str): Natural language question
- `query` (str): Corresponding query string
- `query_type` (Optional[str]): Type of query (e.g., "SELECT", "AGGREGATE")
- `explanation` (Optional[str]): Explanation of the query
- `verified` (bool): Whether the example has been verified (default: False)
- `created_by` (Optional[str]): User identifier who created the example

**Returns:**
- `Dict[str, Any]` with keys:
  - `status` (str): "success" or "error"
  - `example_id` (str): Unique ID of the created example
  - `message` (str): Success or error message

**Example:**
```python
result = await service.add_example(
    tenant_id="tenant_123",
    dataset_name="users_table",
    question="Show me all active users",
    query="SELECT * FROM users WHERE status = 'active'",
    query_type="SELECT",
    explanation="Filters users table for active status",
    verified=True,
    created_by="admin@example.com"
)

if result["status"] == "success":
    print(f"Example added with ID: {result['example_id']}")
```

---

#### verify_example

```python
async def verify_example(
    example_id: str,
    verified: bool,
    updated_by: Optional[str] = None
) -> Dict[str, Any]
```

Mark an example as verified or unverified.

**Parameters:**
- `example_id` (str): Unique ID of the example
- `verified` (bool): Verification status to set
- `updated_by` (Optional[str]): User identifier who updated the example

**Returns:**
- `Dict[str, Any]` with keys:
  - `status` (str): "success" or "error"
  - `example_id` (str): ID of the updated example
  - `verified` (bool): New verification status
  - `message` (str): Success or error message

**Example:**
```python
result = await service.verify_example(
    example_id="example_456",
    verified=True,
    updated_by="admin@example.com"
)

if result["status"] == "success":
    print(f"Example {result['example_id']} verified")
```

---

#### list_examples

```python
async def list_examples(
    tenant_id: str,
    dataset_name: Optional[str] = None,
    verified_only: bool = False,
    limit: int = 100
) -> List[Dict[str, Any]]
```

List examples for a tenant, optionally filtered by dataset and verification status.

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant
- `dataset_name` (Optional[str]): Filter by specific dataset (default: None for all datasets)
- `verified_only` (bool): Only return verified examples (default: False)
- `limit` (int): Maximum number of examples to return (default: 100)

**Returns:**
- `List[Dict[str, Any]]`: List of example dictionaries, each containing:
  - `example_id` (str): Unique ID
  - `question` (str): Natural language question
  - `query` (str): Query string
  - `query_type` (str): Type of query
  - `explanation` (Optional[str]): Query explanation
  - `verified` (bool): Verification status
  - `created_at` (str): Creation timestamp
  - `created_by` (Optional[str]): Creator identifier

**Example:**
```python
examples = await service.list_examples(
    tenant_id="tenant_123",
    dataset_name="users_table",
    verified_only=True,
    limit=50
)

for example in examples:
    print(f"Q: {example['question']}")
    print(f"A: {example['query']}")
    print(f"Verified: {example['verified']}")
```

---

### Dataset Management

#### get_dataset

```python
async def get_dataset(
    tenant_id: str,
    dataset_name: str
) -> Optional[Dict[str, Any]]
```

Retrieve information about a specific dataset.

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant
- `dataset_name` (str): Name of the dataset

**Returns:**
- `Optional[Dict[str, Any]]`: Dataset information dictionary or None if not found, containing:
  - `dataset_name` (str): Name of the dataset
  - `source_type` (str): Source type identifier
  - `description` (Optional[str]): Dataset description
  - `tags` (List[str]): Associated tags
  - `field_count` (int): Number of fields
  - `created_at` (str): Creation timestamp
  - `created_by` (Optional[str]): Creator identifier

**Example:**
```python
dataset = await service.get_dataset(
    tenant_id="tenant_123",
    dataset_name="users_table"
)

if dataset:
    print(f"Dataset: {dataset['dataset_name']}")
    print(f"Source: {dataset['source_type']}")
    print(f"Fields: {dataset['field_count']}")
else:
    print("Dataset not found")
```

---

#### list_datasets

```python
async def list_datasets(
    tenant_id: str,
    source_type: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]
```

List all datasets for a tenant, optionally filtered by source type.

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant
- `source_type` (Optional[str]): Filter by source type (default: None for all types)
- `limit` (int): Maximum number of datasets to return (default: 100)

**Returns:**
- `List[Dict[str, Any]]`: List of dataset dictionaries with same structure as get_dataset

**Example:**
```python
datasets = await service.list_datasets(
    tenant_id="tenant_123",
    source_type="postgresql",
    limit=50
)

for dataset in datasets:
    print(f"{dataset['dataset_name']} ({dataset['source_type']})")
```

---

#### delete_dataset

```python
async def delete_dataset(
    tenant_id: str,
    dataset_name: str
) -> Dict[str, Any]
```

Delete a dataset and all associated data (fields, examples, etc.).

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant
- `dataset_name` (str): Name of the dataset to delete

**Returns:**
- `Dict[str, Any]` with keys:
  - `status` (str): "success" or "error"
  - `dataset_name` (str): Name of the deleted dataset
  - `message` (str): Success or error message

**Example:**
```python
result = await service.delete_dataset(
    tenant_id="tenant_123",
    dataset_name="old_users_table"
)

if result["status"] == "success":
    print(f"Deleted dataset: {result['dataset_name']}")
```

---

## KnowledgeVerseAdapter

**Location:** `app/services/queryforge_adapter.py`

The KnowledgeVerseAdapter bridges PostgreSQL storage with QueryForge's QueryGenerationPipeline. It provides retrieval methods for schema fields, Q&A examples, and master configurations using hybrid search.

### Initialization

```python
KnowledgeVerseAdapter(
    session: AsyncSession,
    embedding_client: EmbeddingClient,
)
```

**Parameters:**
- `session` (AsyncSession): SQLAlchemy async database session
- `embedding_client` (EmbeddingClient): Client for generating embeddings

**Example:**
```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.queryforge_adapter import KnowledgeVerseAdapter
from app.services.embedding_client import EmbeddingClient

async def create_adapter(session: AsyncSession):
    embedding_client = EmbeddingClient()
    adapter = KnowledgeVerseAdapter(
        session=session,
        embedding_client=embedding_client
    )
    return adapter
```

---

### Schema Field Retrieval

#### get_similar_fields

```python
async def get_similar_fields(
    tenant_id: str,
    document_name: str,
    question: str,
    top_k: int = 10,
    similarity_threshold: float = 0.5
) -> List[FieldSpec]
```

Retrieve schema fields most relevant to a natural language question using hybrid search.

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant
- `document_name` (str): Name of the dataset/document
- `question` (str): Natural language question
- `top_k` (int): Maximum number of fields to return (default: 10)
- `similarity_threshold` (float): Minimum similarity score (0.0 to 1.0, default: 0.5)

**Returns:**
- `List[FieldSpec]`: List of field specifications, each containing:
  - `field_name` (str): Name of the field
  - `field_type` (str): Data type
  - `description` (Optional[str]): Field description
  - `sample_values` (Optional[List]): Example values
  - `constraints` (Optional[Dict]): Field constraints
  - `relevance_score` (float): Similarity score

**Example:**
```python
fields = await adapter.get_similar_fields(
    tenant_id="tenant_123",
    document_name="users_table",
    question="How many users signed up last month?",
    top_k=5,
    similarity_threshold=0.6
)

for field in fields:
    print(f"{field.field_name} ({field.field_type})")
    print(f"Relevance: {field.relevance_score}")
    if field.description:
        print(f"Description: {field.description}")
```

---

#### get_all_fields

```python
async def get_all_fields(
    tenant_id: str,
    document_name: str
) -> List[FieldSpec]
```

Retrieve all schema fields for a dataset without filtering.

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant
- `document_name` (str): Name of the dataset/document

**Returns:**
- `List[FieldSpec]`: List of all field specifications with same structure as get_similar_fields

**Example:**
```python
all_fields = await adapter.get_all_fields(
    tenant_id="tenant_123",
    document_name="users_table"
)

print(f"Total fields: {len(all_fields)}")
for field in all_fields:
    print(f"- {field.field_name}: {field.field_type}")
```

---

### Q&A Example Retrieval

#### get_similar_qa_examples

```python
async def get_similar_qa_examples(
    tenant_id: str,
    document_name: str,
    question: str,
    top_n: int = 5,
    only_reviewed: bool = False,
    min_confidence: float = 0.0
) -> List[ExampleSpec]
```

Retrieve Q&A examples most similar to a given question using hybrid search.

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant
- `document_name` (str): Name of the dataset/document
- `question` (str): Natural language question
- `top_n` (int): Maximum number of examples to return (default: 5)
- `only_reviewed` (bool): Only return verified examples (default: False)
- `min_confidence` (float): Minimum confidence score (0.0 to 1.0, default: 0.0)

**Returns:**
- `List[ExampleSpec]`: List of example specifications, each containing:
  - `question` (str): Natural language question
  - `query` (str): Corresponding query
  - `query_type` (str): Type of query
  - `explanation` (Optional[str]): Query explanation
  - `verified` (bool): Verification status
  - `confidence` (float): Confidence score
  - `similarity_score` (float): Similarity to input question

**Example:**
```python
examples = await adapter.get_similar_qa_examples(
    tenant_id="tenant_123",
    document_name="users_table",
    question="Show me all active users",
    top_n=3,
    only_reviewed=True,
    min_confidence=0.7
)

for example in examples:
    print(f"Similar Q: {example.question}")
    print(f"Query: {example.query}")
    print(f"Similarity: {example.similarity_score}")
    print(f"Verified: {example.verified}")
```

---

### Master Config

#### load_master_config

```python
async def load_master_config(
    tenant_id: str,
    document_name: str,
    version: Optional[str] = None
) -> Optional[DocumentMasterConfig]
```

Load the master configuration for a dataset, including metadata and generation settings.

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant
- `document_name` (str): Name of the dataset/document
- `version` (Optional[str]): Specific version to load (default: None for latest)

**Returns:**
- `Optional[DocumentMasterConfig]`: Configuration object or None if not found, containing:
  - `document_name` (str): Name of the dataset
  - `source_type` (str): Source type identifier
  - `description` (Optional[str]): Dataset description
  - `generation_settings` (Dict): Settings for query generation
  - `metadata` (Dict): Additional metadata
  - `version` (str): Configuration version

**Example:**
```python
config = await adapter.load_master_config(
    tenant_id="tenant_123",
    document_name="users_table",
    version="v1.2"
)

if config:
    print(f"Document: {config.document_name}")
    print(f"Source: {config.source_type}")
    print(f"Version: {config.version}")
    print(f"Settings: {config.generation_settings}")
else:
    print("Configuration not found")
```

---

### Utility Methods

#### list_tenant_documents

```python
async def list_tenant_documents(
    tenant_id: str
) -> List[str]
```

List all document names available for a tenant.

**Parameters:**
- `tenant_id` (str): Unique identifier for the tenant

**Returns:**
- `List[str]`: List of document names

**Example:**
```python
documents = await adapter.list_tenant_documents(
    tenant_id="tenant_123"
)

print(f"Available documents: {', '.join(documents)}")
```

---

## Database Functions

### hybrid_search_nodes

**Location:** PostgreSQL database function

Performs hybrid search combining BM25 full-text search and vector similarity search on knowledge nodes.

```sql
hybrid_search_nodes(
    query_text TEXT,
    query_embedding vector,
    tenant_ids TEXT[],
    node_types TEXT[],
    top_k INTEGER DEFAULT 10,
    bm25_weight FLOAT DEFAULT 0.5,
    vector_weight FLOAT DEFAULT 0.5
) RETURNS TABLE (
    node_id TEXT,
    bm25_score FLOAT,
    vector_score FLOAT,
    combined_score FLOAT
)
```

**Parameters:**
- `query_text` (TEXT): Full-text search query
- `query_embedding` (vector): Query embedding vector
- `tenant_ids` (TEXT[]): Array of tenant IDs to filter by
- `node_types` (TEXT[]): Array of node types to filter by
- `top_k` (INTEGER): Maximum number of results (default: 10)
- `bm25_weight` (FLOAT): Weight for BM25 score (default: 0.5)
- `vector_weight` (FLOAT): Weight for vector similarity score (default: 0.5)

**Returns:**
- Table with columns:
  - `node_id` (TEXT): Unique node identifier
  - `bm25_score` (FLOAT): BM25 full-text search score
  - `vector_score` (FLOAT): Vector similarity score
  - `combined_score` (FLOAT): Weighted combination of both scores

**Example:**
```sql
-- Search for schema fields related to "user email"
SELECT * FROM hybrid_search_nodes(
    'user email address',
    '[0.1, 0.2, ..., 0.9]'::vector,
    ARRAY['tenant_123'],
    ARRAY['SCHEMA_FIELD'],
    10,
    0.4,
    0.6
)
ORDER BY combined_score DESC;
```

**Usage in Python:**
```python
from sqlalchemy import text

async def search_nodes(session, query_text, query_embedding, tenant_id):
    result = await session.execute(
        text("""
            SELECT * FROM hybrid_search_nodes(
                :query_text,
                :query_embedding,
                ARRAY[:tenant_id],
                ARRAY['SCHEMA_FIELD', 'EXAMPLE'],
                :top_k,
                :bm25_weight,
                :vector_weight
            )
            ORDER BY combined_score DESC
        """),
        {
            "query_text": query_text,
            "query_embedding": query_embedding,
            "tenant_id": tenant_id,
            "top_k": 10,
            "bm25_weight": 0.5,
            "vector_weight": 0.5
        }
    )
    return result.fetchall()
```

---

## ContextForge Library API

### get_context

**Location:** `contextforge.ContextForge.get_context()`

Direct method for context retrieval without HTTP. Designed for framework integrations.

```python
async def get_context(
    self,
    query: Optional[str] = None,
    tenant_ids: Optional[List[str]] = None,
    entry_types: Optional[List[NodeType]] = None,
    tags: Optional[List[str]] = None,
    max_depth: int = 2,
    expand: bool = True,
    entry_limit: int = 10,
    context_limit: int = 50,
    include_entities: bool = True,
    include_schemas: bool = False,
    include_examples: bool = False,
    search_method: Literal["hybrid", "bm25", "vector"] = "hybrid",
    bm25_weight: float = 0.4,
    vector_weight: float = 0.6,
    min_score: Optional[float] = None,
    max_tokens: Optional[int] = None,
    token_model: str = "gpt-4",
    expansion_types: Optional[List[NodeType]] = None,
    *,
    request: Optional[ContextRequest] = None,
) -> ContextResponse
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | None | Search query (required unless `request` provided) |
| `tenant_ids` | List[str] | None | Tenant IDs (required unless `request` provided) |
| `entry_types` | List[NodeType] | None | Filter entry points by type |
| `tags` | List[str] | None | Filter by tags |
| `search_method` | Literal | "hybrid" | Search method: "hybrid", "bm25", or "vector" |
| `bm25_weight` | float | 0.4 | BM25 weight (0.0-1.0, hybrid mode) |
| `vector_weight` | float | 0.6 | Vector weight (0.0-1.0, hybrid mode) |
| `min_score` | float | None | Minimum score threshold |
| `max_depth` | int | 2 | Graph expansion depth (1-10) |
| `expand` | bool | True | Enable graph expansion |
| `entry_limit` | int | 10 | Max entry points (1-100) |
| `context_limit` | int | 50 | Max expanded nodes (1-200) |
| `include_entities` | bool | True | Include related entities |
| `include_schemas` | bool | False | Include schema nodes |
| `include_examples` | bool | False | Include example nodes |
| `max_tokens` | int | None | Token budget (100-128000) |
| `token_model` | str | "gpt-4" | Model for token counting |
| `expansion_types` | List[NodeType] | None | Node types for expansion |
| `request` | ContextRequest | None | Full request (overrides params) |

**Returns:**
- `ContextResponse` with:
  - `entry_points`: List of direct search matches
  - `context`: List of graph-expanded nodes
  - `entities`: List of related entities
  - `stats`: Retrieval statistics

**Example:**
```python
from contextforge import ContextForge, NodeType

cf = ContextForge(database_url="postgresql+asyncpg://...")

# Simple query
results = await cf.get_context(
    query="purchase order",
    tenant_ids=["acme"],
)

# Shallow planner context
results = await cf.get_context(
    query="how to approve PO?",
    tenant_ids=["acme"],
    entry_types=[NodeType.FAQ, NodeType.PLAYBOOK],
    max_depth=1,
    max_tokens=3000,
)

# Keyword search with quality threshold
results = await cf.get_context(
    query="error PO-4501",
    tenant_ids=["acme"],
    search_method="bm25",
    min_score=0.3,
)

# Filter by tags
results = await cf.get_context(
    query="workflow",
    tenant_ids=["acme"],
    tags=["procurement"],
)

# Full request object
from contextforge import ContextRequest
request = ContextRequest(
    query="...",
    tenant_ids=["acme"],
    bm25_weight=0.3,
    vector_weight=0.7,
)
results = await cf.get_context(request=request)
```

---

### ContextRequest

**Location:** `contextforge.ContextRequest` (also `app.schemas.context.ContextRequest`)

Request schema for context retrieval.

```python
class ContextRequest(BaseModel):
    query: str = ""
    tenant_ids: List[str] = []
    
    entry_types: Optional[List[NodeType]] = None
    entry_limit: int = 10  # 1-100
    tags: Optional[List[str]] = None
    
    search_method: Literal["hybrid", "bm25", "vector"] = "hybrid"
    bm25_weight: float = 0.4  # 0.0-1.0
    vector_weight: float = 0.6  # 0.0-1.0
    min_score: Optional[float] = None  # 0.0-1.0
    
    expand: bool = True
    expansion_types: Optional[List[NodeType]] = None
    max_depth: int = 2  # 1-10
    context_limit: int = 50  # 1-200
    
    include_entities: bool = True
    include_schemas: bool = False
    include_examples: bool = False
    
    max_tokens: Optional[int] = None  # 100-128000
    token_model: str = "gpt-4"
```

---

### ContextResponse

**Location:** `contextforge.ContextResponse` (also `app.schemas.context.ContextResponse`)

Response schema for context retrieval.

```python
class ContextResponse(BaseModel):
    entry_points: List[EntryPointResult]  # Direct search matches
    context: List[ContextNodeResult]       # Graph-expanded nodes
    entities: List[EntityResult]           # Related entities
    stats: ContextStats                    # Retrieval statistics
```

---

## Enumerations

### Node Types

Node types available in the knowledge graph:

- `FAQ`: Frequently asked questions
- `PLAYBOOK`: Procedural guides and workflows
- `PERMISSION_RULE`: Access control rules
- `SCHEMA_INDEX`: Dataset schema index
- `SCHEMA_FIELD`: Individual schema field
- `EXAMPLE`: Question-query example pair
- `ENTITY`: Business entity or concept
- `CONCEPT`: Abstract concept or category

**Example:**
```python
from app.models.knowledge_node import NodeType

# Filter by specific node types
node_types = [NodeType.SCHEMA_FIELD, NodeType.EXAMPLE]
```

---

### Edge Types

Edge types representing relationships between nodes:

- `RELATED`: General relationship between nodes
- `PARENT`: Parent-child hierarchical relationship
- `EXAMPLE_OF`: Example demonstrates a concept or pattern
- `SHARED_TAG`: Nodes share common tags
- `SIMILAR`: Nodes are semantically similar

**Example:**
```python
from app.models.knowledge_edge import EdgeType

# Create a relationship between nodes
edge_type = EdgeType.EXAMPLE_OF
```

---

## Notes

### Async Usage

All service methods are asynchronous and must be called with `await`:

```python
# Correct
result = await service.generate_query(tenant_id, dataset_name, question)

# Incorrect - will not work
result = service.generate_query(tenant_id, dataset_name, question)
```

### Error Handling

All methods return dictionaries with a `status` field. Always check the status:

```python
result = await service.onboard_dataset(...)

if result["status"] == "success":
    # Process successful result
    print(f"Success: {result['message']}")
else:
    # Handle error
    print(f"Error: {result.get('message', 'Unknown error')}")
    if "errors" in result:
        for error in result["errors"]:
            print(f"- {error}")
```

### Embeddings and Vector Storage

The adapter uses the `hybrid_search_nodes()` PostgreSQL function for retrieval. Embeddings are stored in the `embedding` column (vector type) of the `knowledge_nodes` table. The hybrid search combines:

1. BM25 full-text search on node content
2. Vector similarity search on embeddings
3. Weighted combination of both scores

### Tenant Isolation

All operations are tenant-scoped. Always provide the correct `tenant_id` to ensure data isolation and security.

---

## Additional Resources

- [ContextForge Architecture](./ARCHITECTURE.md)
- [Setup Guide](./SETUP.md)
- [Examples](./EXAMPLES.md)
