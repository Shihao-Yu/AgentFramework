# ContextForge Quick Start Guide

Get started with ContextForge in 10 minutes. This guide walks you through installation, database setup, and onboarding your first dataset.

## Prerequisites

Before you begin, ensure you have:

- Python 3.11 or higher
- PostgreSQL 15 or higher
- PostgreSQL pgvector extension
- Virtual environment tool (venv, conda, etc.)

## Installation

### 1. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

### 2. Install ContextForge

```bash
# Install with pip
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

### 3. Set Up PostgreSQL Database

```bash
# Create database
createdb faq_knowledge_base

# Enable pgvector extension (requires superuser privileges)
psql -d faq_knowledge_base -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env
```

Edit `.env` with your database credentials:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/faq_knowledge_base
```

### 5. Run Database Migrations

```bash
alembic upgrade head
```

### 6. Start the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

Access the interactive API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Quick Start: 5-Minute Tutorial

This tutorial demonstrates the core workflow: onboard a dataset, generate a query, and add an example.

### Step 1: Initialize the Service

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.queryforge_service import QueryForgeService
from app.clients.embedding_client import EmbeddingClient

# Initialize service (typically done via dependency injection)
service = QueryForgeService(
    session=session,  # AsyncSession instance
    embedding_client=embedding_client,  # Your embedding client
    llm_client=llm_client,  # Your LLM client (optional)
)
```

### Step 2: Onboard Your First Dataset

```python
# Onboard a PostgreSQL table
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders",
    source_type="postgres",
    raw_schema="""
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            order_number VARCHAR(50) NOT NULL,
            customer_id INTEGER REFERENCES customers(id),
            status VARCHAR(20) DEFAULT 'pending',
            total_amount DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """,
    description="E-commerce orders table",
    tags=["ecommerce", "orders"],
    enable_enrichment=False,
)

print(f"Status: {result['status']}")
print(f"Dataset: {result['dataset_name']}")
print(f"Schema Index ID: {result['schema_index_id']}")
print(f"Fields Created: {result['field_count']}")
```

### Step 3: Generate Your First Query

```python
# Generate a SQL query from natural language
result = await service.generate_query(
    tenant_id="acme",
    dataset_name="orders",
    question="Show all pending orders from the last 7 days",
    include_explanation=True,
)

print(f"Status: {result['status']}")
print(f"Query: {result['query']}")
print(f"Type: {result['query_type']}")
if result.get('explanation'):
    print(f"Explanation: {result['explanation']}")
```

### Step 4: Add a Q&A Example

```python
# Add a verified example to improve future query generation
result = await service.add_example(
    tenant_id="acme",
    dataset_name="orders",
    question="Show pending orders",
    query="SELECT * FROM orders WHERE status = 'pending'",
    query_type="sql",
    explanation="Filters orders by pending status",
    verified=True,
)

print(f"Status: {result['status']}")
print(f"Example ID: {result['node_id']}")
```

## Onboarding Different Data Sources

ContextForge supports multiple data source types. Each requires a different schema format.

### PostgreSQL

Use SQL DDL (CREATE TABLE statements):

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="customers",
    source_type="postgres",
    raw_schema="""
        CREATE TABLE customers (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """,
    description="Customer records",
    tags=["crm", "customers"],
)
```

### OpenSearch / Elasticsearch

Use JSON mapping from `GET /_mapping`:

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="products",
    source_type="opensearch",
    raw_schema={
        "mappings": {
            "properties": {
                "product_id": {"type": "keyword"},
                "name": {"type": "text"},
                "description": {"type": "text"},
                "price": {"type": "float"},
                "category": {"type": "keyword"},
                "in_stock": {"type": "boolean"},
                "created_at": {"type": "date"}
            }
        }
    },
    description="Product catalog",
    tags=["ecommerce", "products"],
)
```

### REST API

Use OpenAPI/Swagger specification:

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="users_api",
    source_type="rest_api",
    raw_schema={
        "openapi": "3.0.0",
        "info": {"title": "Users API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "summary": "List users",
                    "parameters": [
                        {"name": "status", "in": "query", "schema": {"type": "string"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/User"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "username": {"type": "string"},
                        "email": {"type": "string"},
                        "status": {"type": "string"}
                    }
                }
            }
        }
    },
    description="User management API",
    tags=["api", "users"],
)
```

### ClickHouse

Use SQL DDL (CREATE TABLE statements):

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="events",
    source_type="clickhouse",
    raw_schema="""
        CREATE TABLE events (
            event_id UUID,
            user_id UInt64,
            event_type String,
            event_data String,
            timestamp DateTime
        ) ENGINE = MergeTree()
        ORDER BY (timestamp, user_id);
    """,
    description="Analytics events",
    tags=["analytics", "events"],
)
```

### MySQL

Use SQL DDL (CREATE TABLE statements):

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="inventory",
    source_type="mysql",
    raw_schema="""
        CREATE TABLE inventory (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sku VARCHAR(50) NOT NULL,
            quantity INT DEFAULT 0,
            warehouse_id INT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """,
    description="Inventory tracking",
    tags=["warehouse", "inventory"],
)
```

## Using the REST API

You can also interact with ContextForge via HTTP endpoints.

### Onboard a Dataset

```bash
curl -X POST http://localhost:8000/api/datasets \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "acme",
    "dataset_name": "orders",
    "source_type": "postgres",
    "raw_schema": "CREATE TABLE orders (id SERIAL PRIMARY KEY, status VARCHAR(20));",
    "description": "Orders table",
    "tags": ["ecommerce"]
  }'
```

### Generate a Query

```bash
curl -X POST http://localhost:8000/api/datasets/query \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "acme",
    "dataset_name": "orders",
    "question": "Show all pending orders",
    "include_explanation": true
  }'
```

### Add an Example

```bash
curl -X POST http://localhost:8000/api/datasets/examples \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "acme",
    "dataset_name": "orders",
    "question": "Show pending orders",
    "query": "SELECT * FROM orders WHERE status = '\''pending'\''",
    "query_type": "sql",
    "verified": true
  }'
```

### List Datasets

```bash
curl "http://localhost:8000/api/datasets?tenant_id=acme"
```

## Understanding the Data Model

ContextForge stores schemas as KnowledgeNode objects in PostgreSQL:

### Node Types

- **SCHEMA_INDEX**: Represents a dataset (table, index, API)
- **SCHEMA_FIELD**: Represents individual fields/columns
- **EXAMPLE**: Stores Q&A pairs for learning

### Relationships

- Fields are linked to their parent dataset via PARENT edges
- Examples are linked to datasets via EXAMPLE_OF edges

### Multi-Tenancy

All data is isolated by `tenant_id`, ensuring secure multi-tenant operation.

### Embeddings

The service automatically generates embeddings for:
- Dataset descriptions
- Field names and descriptions
- Q&A examples

Embeddings are stored in PostgreSQL using the pgvector extension for efficient similarity search.

## Configuration Options

### Onboarding Options

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders",
    source_type="postgres",
    raw_schema="...",
    description="Optional description",  # Defaults to "Schema for {dataset_name}"
    tags=["tag1", "tag2"],              # Optional tags for categorization
    enable_enrichment=False,             # Use LLM to enrich metadata (requires llm_client)
    created_by="user@example.com",       # Optional user ID for audit trail
)
```

### Query Generation Options

```python
result = await service.generate_query(
    tenant_id="acme",
    dataset_name="orders",
    question="Show pending orders",
    include_explanation=True,  # Include query explanation
    use_pipeline=True,         # Use QueryGenerationPipeline (default)
)
```

### Example Options

```python
result = await service.add_example(
    tenant_id="acme",
    dataset_name="orders",
    question="Show pending orders",
    query="SELECT * FROM orders WHERE status = 'pending'",
    query_type="sql",          # Must be: sql, elasticsearch, or api
    explanation="Optional explanation of the query",
    verified=True,             # Mark as verified (published) or draft
    created_by="user@example.com",
)
```

## Supported Source Types

ContextForge supports the following data source types:

| Source Type | Description | Schema Format |
|-------------|-------------|---------------|
| `postgres` | PostgreSQL databases | SQL DDL (CREATE TABLE) |
| `mysql` | MySQL databases | SQL DDL (CREATE TABLE) |
| `clickhouse` | ClickHouse databases | SQL DDL (CREATE TABLE) |
| `opensearch` | OpenSearch indices | JSON mapping |
| `elasticsearch` | Elasticsearch indices | JSON mapping |
| `rest_api` | REST APIs | OpenAPI/Swagger spec |
| `graphql` | GraphQL APIs | GraphQL schema |
| `mongodb` | MongoDB collections | JSON schema |

Check available sources programmatically:

```python
from app.contextforge.sources import list_sources

sources = list_sources()
print(sources)  # ['postgres', 'opensearch', 'rest_api', ...]
```

## Troubleshooting

### Import Error: Neither AgenticSearch nor ContextForge Available

If you see this error, ensure ContextForge is properly installed:

```bash
pip install -e .
```

### Database Connection Error

Verify your `DATABASE_URL` in `.env`:

```bash
# Test connection
psql postgresql://postgres:password@localhost:5432/faq_knowledge_base
```

### pgvector Extension Not Found

Install the pgvector extension:

```bash
# On Ubuntu/Debian
sudo apt install postgresql-15-pgvector

# On macOS with Homebrew
brew install pgvector

# Enable in database
psql -d faq_knowledge_base -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Unknown Source Type Error

Check available sources:

```python
from app.contextforge.sources import list_sources
print(list_sources())
```

Ensure you're using a supported source type from the list.

## Next Steps

Now that you've completed the quick start, explore these topics:

- **[API Reference](http://localhost:8000/docs)**: Complete API documentation
- **[Architecture Guide](../README.md)**: Understanding ContextForge internals
- **[Advanced Usage](../README.md#customization)**: Custom embedding and LLM clients
- **[Multi-Tenant Setup](../README.md#multi-tenancy)**: Configuring tenant isolation
- **[Production Deployment](../README.md#deployment)**: Best practices for production

## Getting Help

- Check the [main README](../README.md) for detailed documentation
- Review the [API documentation](http://localhost:8000/docs) for endpoint details
- Examine the [test files](../tests/) for usage examples

## Example: Complete Workflow

Here's a complete example showing the full workflow:

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.queryforge_service import QueryForgeService
from app.clients.embedding_client import EmbeddingClient
from app.clients.inference_client import InferenceClient

async def main():
    # Set up database connection
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:password@localhost:5432/faq_knowledge_base"
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Initialize clients
        embedding_client = EmbeddingClient()  # Replace with your implementation
        llm_client = InferenceClient()        # Replace with your implementation
        
        # Initialize service
        service = QueryForgeService(
            session=session,
            embedding_client=embedding_client,
            llm_client=llm_client,
        )
        
        # 1. Onboard dataset
        print("Onboarding dataset...")
        onboard_result = await service.onboard_dataset(
            tenant_id="acme",
            dataset_name="orders",
            source_type="postgres",
            raw_schema="""
                CREATE TABLE orders (
                    id SERIAL PRIMARY KEY,
                    order_number VARCHAR(50) NOT NULL,
                    customer_id INTEGER,
                    status VARCHAR(20) DEFAULT 'pending',
                    total_amount DECIMAL(10,2),
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """,
            description="E-commerce orders",
            tags=["ecommerce", "orders"],
        )
        print(f"Onboarded: {onboard_result['dataset_name']}")
        print(f"Fields: {onboard_result['field_count']}")
        
        # 2. Add examples
        print("\nAdding examples...")
        examples = [
            {
                "question": "Show all pending orders",
                "query": "SELECT * FROM orders WHERE status = 'pending'",
            },
            {
                "question": "Get orders from last week",
                "query": "SELECT * FROM orders WHERE created_at >= NOW() - INTERVAL '7 days'",
            },
            {
                "question": "Find high-value orders",
                "query": "SELECT * FROM orders WHERE total_amount > 1000 ORDER BY total_amount DESC",
            },
        ]
        
        for example in examples:
            await service.add_example(
                tenant_id="acme",
                dataset_name="orders",
                question=example["question"],
                query=example["query"],
                query_type="sql",
                verified=True,
            )
            print(f"Added: {example['question']}")
        
        # 3. Generate queries
        print("\nGenerating queries...")
        questions = [
            "Show pending orders from today",
            "What are the top 5 orders by amount?",
            "List all orders for customer 123",
        ]
        
        for question in questions:
            result = await service.generate_query(
                tenant_id="acme",
                dataset_name="orders",
                question=question,
                include_explanation=True,
            )
            print(f"\nQuestion: {question}")
            print(f"Query: {result['query']}")
            if result.get('explanation'):
                print(f"Explanation: {result['explanation']}")
        
        # Commit changes
        await session.commit()

if __name__ == "__main__":
    asyncio.run(main())
```

This example demonstrates the complete workflow from onboarding to query generation.
