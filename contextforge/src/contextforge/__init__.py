"""
ContextForge - Knowledge Management Library for FastAPI

A comprehensive knowledge management library that provides:
- Hybrid search (BM25 + Vector)
- Knowledge graph with typed relationships
- NL-to-SQL query generation (QueryForge)
- Multi-tenant isolation
- Bundled Admin UI

Quick Start:
    from contextforge import ContextForge
    
    cf = ContextForge(context_db_url="postgresql+asyncpg://...")
    app.include_router(cf.router, prefix="/api/kb")

Full Configuration:
    from contextforge import ContextForge, ContextForgeConfig
    from contextforge.providers.embedding import SentenceTransformersProvider
    
    cf = ContextForge(
        config=ContextForgeConfig(
            context_db_url="postgresql+asyncpg://...",
            db_schema="agent",
            admin_ui_enabled=True,
        ),
        embedding_provider=SentenceTransformersProvider(),
    )
    app.mount("/knowledge", cf.app)
"""

from contextforge.core.app import ContextForge
from contextforge.core.config import ContextForgeConfig
from contextforge.core.exceptions import (
    ContextForgeError,
    ConfigurationError,
    DatabaseError,
    TenantNotFoundError,
    NodeNotFoundError,
    EmbeddingError,
    AuthenticationError,
    AuthorizationError,
)

try:
    from app.schemas.context import (
        ContextRequest,
        ContextResponse,
        EntryPointResult,
        ContextNodeResult,
        EntityResult,
        ContextStats,
    )
    from app.models.enums import NodeType, EdgeType
    _CONTEXT_API_AVAILABLE = True
except ImportError:
    _CONTEXT_API_AVAILABLE = False

__version__ = "1.0.0"

__all__ = [
    "ContextForge",
    "ContextForgeConfig",
    "ContextForgeError",
    "ConfigurationError", 
    "DatabaseError",
    "TenantNotFoundError",
    "NodeNotFoundError",
    "EmbeddingError",
    "AuthenticationError",
    "AuthorizationError",
    "__version__",
]

if _CONTEXT_API_AVAILABLE:
    __all__.extend([
        "ContextRequest",
        "ContextResponse",
        "EntryPointResult",
        "ContextNodeResult",
        "EntityResult",
        "ContextStats",
        "NodeType",
        "EdgeType",
    ])
