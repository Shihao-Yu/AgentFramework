"""
ContextForge Storage Layer

PostgreSQL-backed storage using existing KnowledgeNode/KnowledgeEdge models.

Components:
- PostgresAdapter: Vector store interface for schema/example retrieval
- SchemaStore: Schema versioning and persistence
- PlanStorage: Query plan persistence with version history

Node Type Mapping:
| ContextForge Type     | KnowledgeNode node_type |
|-----------------------|-------------------------|
| DocumentMasterConfig  | schema_index            |
| FieldSpec             | schema_field            |
| ExampleSpec           | example                 |
| QueryPlan             | (uses separate table)   |
"""

from .postgres_adapter import (
    PostgresAdapter,
    create_postgres_adapter,
)
from .schema_store import (
    SchemaStoreProtocol,
    SchemaStore,
    SchemaVersion,
    InMemorySchemaStore,
)
from .plan_storage import (
    PlanStorage,
)

__all__ = [
    # Postgres Adapter
    "PostgresAdapter",
    "create_postgres_adapter",
    # Schema Store
    "SchemaStoreProtocol",
    "SchemaStore",
    "SchemaVersion",
    "InMemorySchemaStore",
    # Plan Storage
    "PlanStorage",
]
