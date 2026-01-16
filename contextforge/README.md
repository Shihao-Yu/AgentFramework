# FAQ/Knowledge Base System - Backend

A comprehensive knowledge management system with hybrid search, knowledge graphs, and automated ticket-to-knowledge conversion.

## Features

- **Hybrid Search**: Combines BM25 full-text search with vector similarity search using Reciprocal Rank Fusion (RRF)
- **Knowledge Graph**: Relationships between knowledge items with support for graph traversal
- **Question Variants**: Multiple phrasings for improved matching
- **Staging Workflow**: Review queue for pipeline-generated content
- **Analytics**: Usage tracking, hit statistics, and performance metrics


## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Virtual environment tool (venv, conda, etc.)

### Installation

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
# Using pip with pyproject.toml
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

4. Set up database:
```bash
# Create database
createdb knowledge_base

# Enable pgvector extension (as superuser)
psql -d knowledge_base -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run migrations
alembic upgrade head
```

5. Start the server:
```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

## API Documentation

Once running, access the interactive API docs:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
├── alembic/                  # Database migrations
│   └── versions/             # Migration files (001-011)
├── app/
│   ├── core/                 # Configuration, database, dependencies
│   ├── models/               # SQLModel entities
│   ├── schemas/              # Pydantic request/response models
│   ├── services/             # Business logic layer
│   ├── routes/               # API endpoints
│   ├── clients/              # Abstract embedding/inference interfaces
│   └── main.py               # FastAPI application
├── pipeline/                 # Ticket-to-knowledge conversion
│   ├── models.py             # Pipeline data models
│   ├── prompts.py            # LLM prompts
│   └── service.py            # Pipeline orchestration
├── tests/                    # Test files
├── alembic.ini               # Alembic configuration
├── pyproject.toml            # Python project configuration
├── .env.example              # Environment template
└── README.md                 # This file
```

## Knowledge Types

The system supports multiple knowledge types:

| Type | Description |
|------|-------------|
| FAQ | Question and answer pairs |
| Business Rule | Conditions and actions |
| Procedure | Step-by-step instructions |
| Policy | Organizational policies |
| Troubleshooting | Problem/solution pairs |
| Context | Background information |
| Permission | Access control rules |
| Glossary | Term definitions |

## Search

The hybrid search combines two methods:

1. **BM25 (Full-text)**: Traditional keyword-based search using PostgreSQL's built-in text search
2. **Vector Similarity**: Semantic search using pgvector with 1024-dimensional embeddings

Default weights are 40% BM25 and 60% vector, configurable per request.

## Customization

### Embedding Client

Replace the mock embedding client in `app/core/dependencies.py`:

```python
from your_embedding_module import YourEmbeddingClient

def get_embedding_client_instance() -> EmbeddingClient:
    return YourEmbeddingClient(
        api_url=settings.EMBEDDING_API_URL,
        api_key=settings.EMBEDDING_API_KEY,
        model=settings.EMBEDDING_MODEL,
    )
```

### Inference Client

Replace the mock inference client similarly:

```python
from your_inference_module import YourInferenceClient

def get_inference_client_instance() -> InferenceClient:
    return YourInferenceClient(
        api_url=settings.INFERENCE_API_URL,
        api_key=settings.INFERENCE_API_KEY,
        model=settings.INFERENCE_MODEL,
    )
```

## API Endpoints

### Knowledge Items
- `GET /api/knowledge` - List items with filtering
- `GET /api/knowledge/{id}` - Get item details
- `POST /api/knowledge` - Create item
- `PUT /api/knowledge/{id}` - Update item
- `DELETE /api/knowledge/{id}` - Delete item

### Variants
- `GET /api/knowledge/{id}/variants` - List variants
- `POST /api/knowledge/{id}/variants` - Add variant
- `DELETE /api/knowledge/{id}/variants/{variant_id}` - Delete variant

### Relationships
- `GET /api/knowledge/{id}/relationships` - List relationships
- `POST /api/knowledge/{id}/relationships` - Create relationship
- `DELETE /api/knowledge/{id}/relationships/{rel_id}` - Delete relationship

### Versions
- `GET /api/knowledge/{id}/versions` - List version history
- `POST /api/knowledge/{id}/versions/{version}/rollback` - Rollback to version

### Staging
- `GET /api/staging` - List staging items
- `GET /api/staging/counts` - Get counts by action type
- `POST /api/staging/{id}/approve` - Approve item
- `POST /api/staging/{id}/reject` - Reject item

### Search
- `POST /api/search` - Hybrid search

### LLM Context (Agent API)
- `POST /api/llm-context` - Get LLM-optimized hierarchical context

### Metrics
- `GET /api/metrics/summary` - Overall statistics
- `GET /api/metrics/top-items` - Top performing items
- `GET /api/metrics/daily-trend` - Daily hit trend
- `GET /api/metrics/tags` - Tag statistics

### Settings
- `GET /api/settings` - Get current settings
- `PATCH /api/settings` - Update settings

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

```bash
black app/ pipeline/
ruff check app/ pipeline/
```

### Type Checking

```bash
mypy app/ pipeline/
```

## Environment Variables

See `.env.example` for all available configuration options.

## License

[Your License Here]
