"""API route exports."""

from app.routes.nodes import router as nodes_router
from app.routes.edges import router as edges_router
from app.routes.tenants import router as tenants_router
from app.routes.graph import router as graph_router
from app.routes.context import router as context_router
from app.routes.sync import router as sync_router
from app.routes.datasets import router as datasets_router
from app.routes.search import router as search_router
from app.routes.metrics import router as metrics_router
from app.routes.settings import router as settings_router
from app.routes.health import router as health_router
from app.routes.onboarding import router as onboarding_router
from app.routes.staging import router as staging_router

__all__ = [
    "nodes_router",
    "edges_router",
    "tenants_router",
    "graph_router",
    "context_router",
    "sync_router",
    "datasets_router",
    "search_router",
    "metrics_router",
    "settings_router",
    "health_router",
    "onboarding_router",
    "staging_router",
]
