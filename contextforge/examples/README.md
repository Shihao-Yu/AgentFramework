# ContextForge Examples

This directory contains working examples demonstrating ContextForge features.

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- ContextForge installed (`pip install -e .`)
- Database configured (see .env.example)

## Example Files

| File | Description | Complexity |
|------|-------------|------------|
| `complete_workflow.py` | End-to-end lifecycle demo | Intermediate |
| `test_hybrid_search.py` | Hybrid search testing | Intermediate |
| `sample_schemas/` | Example schema files | Beginner |

## Quick Start

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env with your database credentials

# 2. Run complete workflow
python examples/complete_workflow.py

# 3. Test hybrid search
python examples/test_hybrid_search.py
```

## Sample Schemas

The `sample_schemas/` directory contains:
- `orders_postgres.sql` - PostgreSQL DDL example
- `orders_opensearch.json` - OpenSearch mapping example
- `orders_openapi.yaml` - REST API OpenAPI spec

## Example Organization

**Beginner Examples:**
- Sample schema files - Reference schemas

**Intermediate Examples:**
- complete_workflow.py - Full onboarding and query generation
- test_hybrid_search.py - Search functionality testing

## Running Examples

Each example can be run standalone:
```bash
python examples/<example_file>.py
```

Environment variables required:
- DATABASE_URL - PostgreSQL connection string
- EMBEDDING_API_URL - Embedding service URL (optional, uses mock)
- INFERENCE_API_URL - LLM service URL (optional, uses mock)

## Common Patterns

See the examples for these common patterns:
1. Service initialization
2. Dataset onboarding
3. Query generation
4. Example management
5. Hybrid search
