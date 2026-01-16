.PHONY: setup install migrate run dev test lint format clean cli help

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
ALEMBIC := $(VENV)/bin/alembic
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff

setup: $(VENV)/bin/activate

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@echo "\n✓ Setup complete. Run 'make dev' to start."

install: setup

migrate:
	$(ALEMBIC) upgrade head

run:
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

dev: setup migrate run

test:
	$(PYTEST) tests/ -v

test-cov:
	$(PYTEST) tests/ -v --cov=app --cov-report=term-missing

lint:
	$(RUFF) check app/ pipeline/ jobs/

format:
	$(RUFF) format app/ pipeline/ jobs/
	$(RUFF) check --fix app/ pipeline/ jobs/

cli:
	$(PYTHON) -m app.contextforge.cli.commands $(ARGS)

cli-help:
	$(PYTHON) -m app.contextforge.cli.commands --help

cli-status:
	$(PYTHON) -m app.contextforge.cli.commands status

onboard:
	@test -n "$(TYPE)" || (echo "Usage: make onboard TYPE=postgres CONN='...' NAME=mydb" && exit 1)
	@test -n "$(CONN)" || (echo "Usage: make onboard TYPE=postgres CONN='...' NAME=mydb" && exit 1)
	@test -n "$(NAME)" || (echo "Usage: make onboard TYPE=postgres CONN='...' NAME=mydb" && exit 1)
	$(PYTHON) -m app.contextforge.cli.commands onboard $(TYPE) "$(CONN)" -n $(NAME)

generate:
	@test -n "$(DATASET)" || (echo "Usage: make generate DATASET=mydb Q='your question'" && exit 1)
	@test -n "$(Q)" || (echo "Usage: make generate DATASET=mydb Q='your question'" && exit 1)
	$(PYTHON) -m app.contextforge.cli.commands generate $(DATASET) "$(Q)"

test-retrieval:
	@test -n "$(DATASET)" || (echo "Usage: make test-retrieval DATASET=mydb Q='your question'" && exit 1)
	@test -n "$(Q)" || (echo "Usage: make test-retrieval DATASET=mydb Q='your question'" && exit 1)
	$(PYTHON) -m app.contextforge.cli.commands test-retrieval $(DATASET) "$(Q)" --show-scores --show-examples

shell:
	$(PYTHON)

db-shell:
	psql $(CONTEXT_DB_URL)

seed:
	@echo "Seeding test data..."
	psql $(CONTEXT_DB_URL) < scripts/seed_test_data.sql

clean:
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

help:
	@echo "ContextForge Makefile"
	@echo ""
	@echo "Setup & Run:"
	@echo "  make setup      - Create venv and install dependencies"
	@echo "  make dev        - Setup + migrate + run server"
	@echo "  make run        - Run API server (port 8000)"
	@echo "  make migrate    - Run database migrations"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test       - Run tests"
	@echo "  make test-cov   - Run tests with coverage"
	@echo "  make lint       - Check code with ruff"
	@echo "  make format     - Format code with ruff"
	@echo ""
	@echo "ContextForge CLI:"
	@echo "  make cli-help   - Show CLI help"
	@echo "  make cli-status - Show ContextForge status"
	@echo "  make cli ARGS='...' - Run CLI with arguments"
	@echo ""
	@echo "  make onboard TYPE=postgres CONN='postgresql://...' NAME=mydb"
	@echo "  make generate DATASET=mydb Q='Show all users'"
	@echo "  make test-retrieval DATASET=mydb Q='Show all users'"
	@echo ""
	@echo "Database:"
	@echo "  make seed       - Seed database with test data"
	@echo "  make db-shell   - Open psql to database"
	@echo ""
	@echo "Utilities:"
	@echo "  make shell      - Python REPL with project context"
	@echo "  make clean      - Remove venv and cache files"
