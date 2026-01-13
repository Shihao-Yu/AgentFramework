# Schema Onboarding Guide

## Overview

### What is Schema Onboarding?

Schema onboarding is the process of importing data source schemas (database tables, search indices, API specifications) into ContextForge's knowledge graph. This enables the system to understand your data structures and generate accurate queries based on natural language questions.

### Why Onboard Schemas?

- **Better Query Generation**: The system understands your data model and can generate syntactically correct queries (SQL, OpenSearch DSL, API requests)
- **Improved Context Retrieval**: Schema metadata is embedded and retrieved alongside documentation to provide complete context
- **Semantic Understanding**: Field descriptions and business meanings help map user questions to the right data fields
- **Query Pattern Learning**: The system learns common query patterns for each dataset

### Node Types Created

Schema onboarding creates two types of nodes in the knowledge graph:

1. **SCHEMA_INDEX**: Represents the dataset, table, or index as a whole
2. **SCHEMA_FIELD**: Represents individual fields, columns, or properties within the schema

These nodes are connected via PARENT edges, forming a hierarchical structure that mirrors your data model.

## Supported Source Types

| Source Type | Schema Format | Query Type Generated |
|-------------|---------------|---------------------|
| postgres | SQL DDL | SQL |
| mysql | SQL DDL | SQL |
| clickhouse | ClickHouse DDL | SQL |
| opensearch | JSON Mapping | OpenSearch DSL |
| elasticsearch | JSON Mapping | Elasticsearch DSL |
| rest_api | OpenAPI Spec | API Requests |

## PostgreSQL Onboarding

### Basic Example

```python
from app.contextforge.services.schema_service import SchemaService

service = SchemaService(graph_store, embedding_service)

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        );
    """,
    description="E-commerce orders table containing all customer orders",
    tags=["ecommerce", "transactional"],
)

print(f"Created schema_index: {result['schema_index_id']}")
print(f"Created {len(result['field_ids'])} field nodes")
```

### Multi-Table Schema

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="ecommerce_schema",
    source_type="postgres",
    raw_schema="""
        CREATE TABLE customers (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            created_at TIMESTAMP
        );
        
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id),
            order_number VARCHAR(50),
            status VARCHAR(20),
            total_amount DECIMAL(10,2)
        );
        
        CREATE TABLE order_items (
            id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(id),
            product_id INTEGER,
            quantity INTEGER,
            unit_price DECIMAL(10,2)
        );
    """,
    description="Complete e-commerce database schema",
    tags=["ecommerce", "relational"],
)
```

## MySQL Onboarding

MySQL schemas follow the same pattern as PostgreSQL:

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="products",
    source_type="mysql",
    raw_schema="""
        CREATE TABLE products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sku VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            category VARCHAR(100),
            price DECIMAL(10,2),
            stock_quantity INT DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """,
    description="Product catalog",
    tags=["inventory", "catalog"],
)
```

## ClickHouse Onboarding

ClickHouse schemas support analytical table structures:

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="events",
    source_type="clickhouse",
    raw_schema="""
        CREATE TABLE events (
            event_id UUID,
            event_type String,
            user_id UInt64,
            timestamp DateTime,
            properties String,
            session_id String
        ) ENGINE = MergeTree()
        ORDER BY (event_type, timestamp);
    """,
    description="User event tracking data",
    tags=["analytics", "events"],
)
```

## OpenSearch Onboarding

### Single Index

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders-2024",
    source_type="opensearch",
    raw_schema={
        "orders-2024": {
            "mappings": {
                "properties": {
                    "order_id": {"type": "keyword"},
                    "customer_id": {"type": "keyword"},
                    "status": {
                        "type": "keyword",
                        "fields": {
                            "raw": {"type": "keyword"}
                        }
                    },
                    "total_amount": {"type": "float"},
                    "items": {
                        "type": "nested",
                        "properties": {
                            "product_id": {"type": "keyword"},
                            "quantity": {"type": "integer"},
                            "price": {"type": "float"}
                        }
                    },
                    "created_at": {"type": "date"},
                    "customer_email": {"type": "text"}
                }
            }
        }
    },
    description="Order documents for 2024",
    tags=["orders", "search"],
)
```

### Index Pattern with Multiple Indices

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders-*",
    source_type="opensearch",
    raw_schema={
        "orders-2024-01": {
            "mappings": {
                "properties": {
                    "order_id": {"type": "keyword"},
                    "status": {"type": "keyword"},
                    "created_at": {"type": "date"}
                }
            }
        },
        "orders-2024-02": {
            "mappings": {
                "properties": {
                    "order_id": {"type": "keyword"},
                    "status": {"type": "keyword"},
                    "created_at": {"type": "date"}
                }
            }
        }
    },
    description="Monthly order indices",
    tags=["orders", "time-series"],
)
```

## Elasticsearch Onboarding

Elasticsearch follows the same format as OpenSearch:

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="products",
    source_type="elasticsearch",
    raw_schema={
        "products": {
            "mappings": {
                "properties": {
                    "sku": {"type": "keyword"},
                    "name": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "description": {"type": "text"},
                    "price": {"type": "float"},
                    "category": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                    "in_stock": {"type": "boolean"}
                }
            }
        }
    },
    description="Product search index",
    tags=["products", "search"],
)
```

## REST API Onboarding

### OpenAPI 3.0 Specification

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders-api",
    source_type="rest_api",
    raw_schema={
        "openapi": "3.0.0",
        "info": {
            "title": "Orders API",
            "version": "1.0.0"
        },
        "paths": {
            "/orders": {
                "get": {
                    "summary": "List orders",
                    "parameters": [
                        {
                            "name": "status",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["pending", "completed", "cancelled"]}
                        },
                        {
                            "name": "customer_id",
                            "in": "query",
                            "schema": {"type": "integer"}
                        },
                        {
                            "name": "start_date",
                            "in": "query",
                            "schema": {"type": "string", "format": "date"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of orders",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "order_id": {"type": "string"},
                                                "status": {"type": "string"},
                                                "total": {"type": "number"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/orders/{order_id}": {
                "get": {
                    "summary": "Get order by ID",
                    "parameters": [
                        {
                            "name": "order_id",
                            "in": "path",
                            "required": true,
                            "schema": {"type": "string"}
                        }
                    ]
                }
            }
        }
    },
    description="Orders REST API",
    tags=["api", "orders"],
)
```

## What Gets Created

### 1. SCHEMA_INDEX Node

Represents the dataset, table, or index as a whole.

**Properties:**
- `title`: "Schema: {dataset_name}"
- `content`: JSON containing:
  - `source_type`: Type of data source (postgres, opensearch, etc.)
  - `description`: Human-readable description
  - `query_patterns`: Common query patterns for this dataset
  - `raw_schema`: Original schema definition
- `tags`: List including "source:{source_type}" plus any custom tags
- `tenant_id`: Tenant identifier for multi-tenancy
- `dataset_name`: Unique name within the tenant

**Example:**
```json
{
  "node_id": "schema_idx_abc123",
  "node_type": "SCHEMA_INDEX",
  "title": "Schema: orders",
  "content": {
    "source_type": "postgres",
    "description": "E-commerce orders table",
    "query_patterns": ["SELECT * FROM orders WHERE status = ?"],
    "raw_schema": "CREATE TABLE orders (...)"
  },
  "tags": ["source:postgres", "ecommerce", "transactional"]
}
```

### 2. SCHEMA_FIELD Nodes

One node per field, column, or property in the schema.

**Properties:**
- `title`: Field path (e.g., "customer.email", "items.product_id")
- `content`: JSON containing:
  - `description`: What this field represents
  - `business_meaning`: Business context and usage
  - `allowed_values`: Valid values or ranges
  - `nullable`: Whether the field can be null
  - `indexed`: Whether the field is indexed for search
  - `is_pii`: Whether the field contains personally identifiable information
- `field_path`: Qualified field path for nested structures
- `data_type`: Field type (string, integer, float, date, boolean, etc.)
- `tags`: Inherited from parent plus field-specific tags

**Example:**
```json
{
  "node_id": "schema_fld_xyz789",
  "node_type": "SCHEMA_FIELD",
  "title": "status",
  "content": {
    "description": "Current order status",
    "business_meaning": "Tracks order lifecycle from pending to completed",
    "allowed_values": ["pending", "processing", "shipped", "completed", "cancelled"],
    "nullable": false,
    "indexed": true,
    "is_pii": false
  },
  "field_path": "status",
  "data_type": "string"
}
```

### 3. PARENT Edges

Connect the SCHEMA_INDEX node to each SCHEMA_FIELD node, creating a hierarchical structure.

**Properties:**
- `from_node`: SCHEMA_INDEX node ID
- `to_node`: SCHEMA_FIELD node ID
- `edge_type`: "PARENT"

## Schema Enrichment

Schema enrichment uses LLM to automatically add semantic information to your schemas.

### Enabling Enrichment

```python
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders",
    source_type="postgres",
    raw_schema="CREATE TABLE orders (...)",
    description="E-commerce orders",
    enable_enrichment=True,  # Enable LLM enrichment
)
```

### What Gets Enriched

1. **Field Descriptions**: Human-readable explanations of what each field contains
2. **Business Meanings**: Context about how the field is used in business processes
3. **Value Synonyms**: Alternative terms users might use to refer to field values
4. **PII Flagging**: Automatic detection of sensitive fields (email, phone, SSN, etc.)

### Example Enrichment Output

**Before Enrichment:**
```json
{
  "field_path": "customer_email",
  "data_type": "string",
  "content": {}
}
```

**After Enrichment:**
```json
{
  "field_path": "customer_email",
  "data_type": "string",
  "content": {
    "description": "Customer's email address for communication",
    "business_meaning": "Primary contact method for order updates and marketing",
    "is_pii": true,
    "value_synonyms": {
      "email": ["email address", "contact email", "user email"]
    }
  }
}
```

### Enrichment Best Practices

1. **Provide Context**: Include a detailed description when onboarding to help the LLM understand your domain
2. **Review Results**: Check enriched fields for accuracy, especially for domain-specific terminology
3. **Iterative Refinement**: Re-run enrichment after adding more documentation or Q&A examples
4. **PII Compliance**: Verify PII flags match your data governance policies

## Best Practices

### 1. Provide Clear Descriptions

Always include a comprehensive description when onboarding:

```python
# Good
description="E-commerce orders table containing all customer orders with status tracking, payment information, and shipping details"

# Less helpful
description="Orders table"
```

### 2. Use Consistent Naming

Maintain consistent naming conventions across datasets:

```python
# Good - consistent naming
await service.onboard_dataset(dataset_name="orders", ...)
await service.onboard_dataset(dataset_name="order_items", ...)
await service.onboard_dataset(dataset_name="order_shipments", ...)

# Inconsistent
await service.onboard_dataset(dataset_name="orders", ...)
await service.onboard_dataset(dataset_name="OrderItems", ...)
await service.onboard_dataset(dataset_name="shipment-data", ...)
```

### 3. Add Tags for Categorization

Use tags to organize and filter datasets:

```python
# Transactional data
tags=["ecommerce", "transactional", "orders"]

# Analytics data
tags=["analytics", "events", "clickstream"]

# Search indices
tags=["search", "products", "catalog"]

# APIs
tags=["api", "rest", "external"]
```

### 4. Verify After Onboarding

Always verify that your schema was onboarded correctly:

```python
# List all datasets for a tenant
datasets = await service.list_datasets(tenant_id="acme")
print(f"Found {len(datasets)} datasets")

# Get detailed information about a specific dataset
dataset_info = await service.get_dataset(
    tenant_id="acme",
    dataset_name="orders"
)
print(f"Schema index: {dataset_info['schema_index']}")
print(f"Fields: {len(dataset_info['fields'])}")

# Inspect individual fields
for field in dataset_info['fields']:
    print(f"  - {field['field_path']}: {field['data_type']}")
```

### 5. Add Q&A Examples After Onboarding

Enhance query generation by adding example questions and answers:

```python
from app.contextforge.services.qa_service import QAService

qa_service = QAService(graph_store, embedding_service)

# Add Q&A examples that reference your schema
await qa_service.add_qa_pair(
    tenant_id="acme",
    question="How many orders were placed last month?",
    answer="""
    SELECT COUNT(*) 
    FROM orders 
    WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
      AND created_at < DATE_TRUNC('month', CURRENT_DATE)
    """,
    tags=["orders", "analytics"],
)

await qa_service.add_qa_pair(
    tenant_id="acme",
    question="Show me pending orders",
    answer="""
    SELECT order_id, customer_id, total_amount, created_at
    FROM orders
    WHERE status = 'pending'
    ORDER BY created_at DESC
    """,
    tags=["orders", "status"],
)
```

### 6. Update Schemas When They Change

When your data model evolves, update the schema in ContextForge:

```python
# Option 1: Re-onboard with the same dataset_name (replaces existing)
await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders",  # Same name replaces old schema
    source_type="postgres",
    raw_schema="CREATE TABLE orders (...new columns...)",
)

# Option 2: Delete and re-create
await service.delete_dataset(tenant_id="acme", dataset_name="orders")
await service.onboard_dataset(...)
```

### 7. Organize Related Schemas

Group related schemas using consistent naming and tags:

```python
# E-commerce domain
await service.onboard_dataset(dataset_name="ecom_orders", tags=["ecommerce", "domain:orders"])
await service.onboard_dataset(dataset_name="ecom_customers", tags=["ecommerce", "domain:customers"])
await service.onboard_dataset(dataset_name="ecom_products", tags=["ecommerce", "domain:products"])

# Analytics domain
await service.onboard_dataset(dataset_name="analytics_events", tags=["analytics", "domain:events"])
await service.onboard_dataset(dataset_name="analytics_sessions", tags=["analytics", "domain:sessions"])
```

## Workflow Example

Complete workflow for onboarding a new data source:

```python
from app.contextforge.services.schema_service import SchemaService
from app.contextforge.services.qa_service import QAService

# Step 1: Initialize services
schema_service = SchemaService(graph_store, embedding_service)
qa_service = QAService(graph_store, embedding_service)

# Step 2: Onboard the schema with enrichment
result = await schema_service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders",
    source_type="postgres",
    raw_schema="""
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            order_number VARCHAR(50) NOT NULL,
            customer_id INTEGER,
            status VARCHAR(20),
            total_amount DECIMAL(10,2),
            created_at TIMESTAMP
        );
    """,
    description="E-commerce orders table with customer and payment information",
    tags=["ecommerce", "transactional"],
    enable_enrichment=True,
)

print(f"Created schema_index: {result['schema_index_id']}")
print(f"Created {len(result['field_ids'])} fields")

# Step 3: Verify the schema
dataset_info = await schema_service.get_dataset(
    tenant_id="acme",
    dataset_name="orders"
)

print("\nFields:")
for field in dataset_info['fields']:
    print(f"  - {field['field_path']}: {field['data_type']}")
    if field.get('content', {}).get('description'):
        print(f"    Description: {field['content']['description']}")

# Step 4: Add Q&A examples
await qa_service.add_qa_pair(
    tenant_id="acme",
    question="Show me all pending orders",
    answer="SELECT * FROM orders WHERE status = 'pending'",
    tags=["orders", "sql"],
)

await qa_service.add_qa_pair(
    tenant_id="acme",
    question="What is the total revenue from completed orders?",
    answer="SELECT SUM(total_amount) FROM orders WHERE status = 'completed'",
    tags=["orders", "analytics"],
)

print("\nSchema onboarding complete!")
```

## Troubleshooting

### Schema Parsing Errors

If schema parsing fails, check:

1. **SQL Syntax**: Ensure DDL statements are valid for the specified source type
2. **JSON Format**: For OpenSearch/Elasticsearch, verify the mappings structure
3. **OpenAPI Version**: REST APIs must use OpenAPI 3.0+ format

### Missing Fields

If fields are not created:

1. Check that the schema contains valid field definitions
2. Verify the source type matches the schema format
3. Review logs for parsing errors

### Enrichment Issues

If enrichment produces unexpected results:

1. Provide more context in the dataset description
2. Add domain-specific tags
3. Review and manually update enriched fields if needed

## Related Documentation

- [Query Generation Guide](./QUERY_GENERATION.md) - How schemas are used to generate queries
- [Context Retrieval](./CONTEXT_RETRIEVAL.md) - How schema nodes are retrieved during search
- [Source Plugins](../sources/README.md) - Technical details on source type implementations
