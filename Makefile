.PHONY: help setup dev api ui seed migrate clean install-api install-ui db-install db-setup db-start db-stop db-status

# Default database configuration (override with environment variables)
FRAMEWORK_DB_URL ?= postgresql://postgres:password@localhost:5432/knowledge_base
DB_NAME ?= knowledge_base
DB_USER ?= postgres
DB_PASS ?= password

help:
	@echo "FAQ Knowledge Base - Development Commands"
	@echo ""
	@echo "Quick Start (first time):"
	@echo "  make db-install - Install PostgreSQL (Ubuntu/Debian/WSL)"
	@echo "  make db-setup   - Create database and enable pgvector"
	@echo "  make setup      - Install all dependencies (API + UI)"
	@echo "  make db-reset   - Run migrations and seed test data"
	@echo ""
	@echo "Daily Development:"
	@echo "  make db-start   - Start PostgreSQL service"
	@echo "  make api        - Start API server (port 8000)"
	@echo "  make ui         - Start UI dev server (port 5173)"
	@echo "  make status     - Check running services"
	@echo ""
	@echo "Database:"
	@echo "  make db-install - Install PostgreSQL + pgvector"
	@echo "  make db-setup   - Create database and extensions"
	@echo "  make db-start   - Start PostgreSQL service"
	@echo "  make db-stop    - Stop PostgreSQL service"
	@echo "  make db-status  - Check PostgreSQL status"
	@echo "  make migrate    - Run database migrations"
	@echo "  make seed       - Seed database with test data"
	@echo "  make db-reset   - Reset database (migrate + seed)"
	@echo ""
	@echo "Installation:"
	@echo "  make install-api - Install API dependencies"
	@echo "  make install-ui  - Install UI dependencies"

# =============================================================================
# Database Setup (Ubuntu/Debian/WSL)
# =============================================================================

db-install:
	@echo "Installing PostgreSQL and pgvector..."
	@echo "This requires sudo access."
	sudo apt update
	sudo apt install -y postgresql postgresql-contrib
	@# Try to install pgvector for common PostgreSQL versions
	@sudo apt install -y postgresql-16-pgvector 2>/dev/null || \
		sudo apt install -y postgresql-15-pgvector 2>/dev/null || \
		sudo apt install -y postgresql-14-pgvector 2>/dev/null || \
		echo "Note: pgvector package not found. You may need to install it manually."
	@echo ""
	@echo "✓ PostgreSQL installed!"
	@echo "  Next: run 'make db-setup' to create the database"

db-setup: db-start
	@echo "Creating database and enabling extensions..."
	@sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$(DB_NAME)'" | grep -q 1 || \
		sudo -u postgres psql -c "CREATE DATABASE $(DB_NAME);"
	@sudo -u postgres psql -d $(DB_NAME) -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || \
		echo "Warning: pgvector extension not available. Vector search will not work."
	@sudo -u postgres psql -c "ALTER USER $(DB_USER) PASSWORD '$(DB_PASS)';"
	@echo ""
	@echo "✓ Database setup complete!"
	@echo "  Database: $(DB_NAME)"
	@echo "  User: $(DB_USER)"
	@echo "  Next: run 'make db-reset' to run migrations and seed data"

db-start:
	@echo "Starting PostgreSQL..."
	@sudo service postgresql start
	@echo "✓ PostgreSQL started"

db-stop:
	@echo "Stopping PostgreSQL..."
	@sudo service postgresql stop
	@echo "✓ PostgreSQL stopped"

db-status:
	@sudo service postgresql status || true
	@echo ""
	@echo "Connection test:"
	@psql -h localhost -U $(DB_USER) -d $(DB_NAME) -c "SELECT 1;" 2>/dev/null && \
		echo "✓ Database connection OK" || \
		echo "✗ Cannot connect to database"

# =============================================================================
# Application Setup
# =============================================================================

setup: install-api install-ui
	@echo ""
	@echo "✓ Setup complete!"
	@echo ""
	@echo "If this is your first time:"
	@echo "  1. make db-install   # Install PostgreSQL"
	@echo "  2. make db-setup     # Create database"
	@echo "  3. make db-reset     # Run migrations + seed"
	@echo "  4. make api          # Start API (terminal 1)"
	@echo "  5. make ui           # Start UI (terminal 2)"
	@echo "  6. Open http://localhost:5173"

install-api:
	@echo "Installing API dependencies..."
	cd contextforge && make setup

install-ui:
	@echo "Installing UI dependencies..."
	cd admin-ui && npm install

# =============================================================================
# Run Services
# =============================================================================

api:
	cd contextforge && make run

ui:
	cd admin-ui && npm run dev

# =============================================================================
# Database Operations
# =============================================================================

migrate:
	cd contextforge && make migrate

seed:
	@echo "Seeding database with test data..."
	cd contextforge && FRAMEWORK_DB_URL=$(FRAMEWORK_DB_URL) make seed

db-reset: migrate seed
	@echo ""
	@echo "✓ Database reset complete!"

# =============================================================================
# Utilities
# =============================================================================

clean:
	cd contextforge && make clean
	cd admin-ui && rm -rf node_modules dist dist-wc

status:
	@echo "Checking services..."
	@echo ""
	@echo "PostgreSQL:"
	@sudo service postgresql status 2>/dev/null | head -3 || echo "  Status unknown"
	@echo ""
	@echo "API:"
	@curl -s http://localhost:8000/health > /dev/null 2>&1 && \
		echo "  ✓ Running at http://localhost:8000" || \
		echo "  ✗ Not running"
	@echo ""
	@echo "UI:"
	@curl -s http://localhost:5173 > /dev/null 2>&1 && \
		echo "  ✓ Running at http://localhost:5173" || \
		echo "  ✗ Not running"
