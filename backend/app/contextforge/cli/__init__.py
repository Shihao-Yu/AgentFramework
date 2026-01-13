"""
ContextForge CLI Module.

Provides Click-based command-line interface for:
- Data source onboarding
- Training example management
- Schema export
- Query generation

Usage:
    python -m app.contextforge.cli --help
    python -m app.contextforge.cli onboard postgres "postgresql://..." -n mydb
    python -m app.contextforge.cli train mydb -q "Question" -Q "Query"
"""

from .commands import cli, main

__all__ = [
    "cli",
    "main",
]
