# FAQ Knowledge Base System

A comprehensive knowledge management system with hybrid search, knowledge graphs, and an admin UI for content management.

## Architecture

```
faq/
├── contextforge/    # Backend API (FastAPI + PostgreSQL)
├── admin-ui/        # Frontend (React + Vite)
└── Makefile         # Development orchestration
```

| Component | Port | Description |
|-----------|------|-------------|
| **contextforge** | 8000 | REST API with hybrid search (BM25 + vector) |
| **admin-ui** | 5173 | Admin panel for managing knowledge base |

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with pgvector extension

## Quick Start

### First Time Setup (Ubuntu/Debian/WSL)

```bash
# 1. Install PostgreSQL and pgvector
make db-install

# 2. Create database and enable extensions
make db-setup

# 3. Install application dependencies
make setup

# 4. Configure environment (optional - defaults work for local dev)
cp contextforge/.env.example contextforge/.env

# 5. Run migrations and seed test data
make db-reset

# 6. Start API (terminal 1)
make api

# 7. Start UI (terminal 2)
make ui

# 8. Open http://localhost:5173
```

### Daily Development

```bash
# Start PostgreSQL (if not running)
make db-start

# Start API (terminal 1)
make api

# Start UI (terminal 2)
make ui

# Check status of all services
make status
```

## Make Commands

```bash
make help         # Show all commands
```

### Database Setup

| Command | Description |
|---------|-------------|
| `make db-install` | Install PostgreSQL + pgvector (requires sudo) |
| `make db-setup` | Create database and enable extensions |
| `make db-start` | Start PostgreSQL service |
| `make db-stop` | Stop PostgreSQL service |
| `make db-status` | Check PostgreSQL status and connection |

### Application

| Command | Description |
|---------|-------------|
| `make setup` | Install all dependencies (API + UI) |
| `make api` | Start API server (port 8000) |
| `make ui` | Start UI dev server (port 5173) |
| `make status` | Check if services are running |

### Database Operations

| Command | Description |
|---------|-------------|
| `make migrate` | Run database migrations |
| `make seed` | Seed database with test data |
| `make db-reset` | Reset database (migrate + seed) |

### Cleanup

| Command | Description |
|---------|-------------|
| `make clean` | Remove all build artifacts and dependencies |

## Manual PostgreSQL Setup

If you're not on Ubuntu/Debian/WSL, install PostgreSQL manually:

```bash
# macOS
brew install postgresql@15 pgvector
brew services start postgresql@15

# Create database
createdb faq_knowledge_base
psql -d faq_knowledge_base -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Test Data

The seed script (`contextforge/scripts/seed_test_data.sql`) creates:

- **Tenants**: purchasing, finance, shared
- **12 Knowledge Nodes**: entities, FAQs, playbooks, permissions, schemas
- **12 Edges**: relationships between nodes
- **5 Staging Items**: pending review queue items
- **Sample Analytics**: hit tracking data

## API Documentation

With the API running, access:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Details

- [contextforge/README.md](contextforge/README.md) - Backend API documentation
- [admin-ui/README.md](admin-ui/README.md) - Frontend documentation

## License

Internal use only.
