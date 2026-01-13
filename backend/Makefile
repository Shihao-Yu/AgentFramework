.PHONY: setup install migrate run dev clean

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

setup: $(VENV)/bin/activate

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

install: setup

migrate: setup
	$(VENV)/bin/alembic upgrade head

run: setup
	$(VENV)/bin/uvicorn app.main:app --reload

dev: migrate run

clean:
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
