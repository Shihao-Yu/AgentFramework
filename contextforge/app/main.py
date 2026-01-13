"""
FAQ/Knowledge Base System - FastAPI Application

Main application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes import (
    knowledge_router,
    staging_router,
    search_router,
    metrics_router,
    settings_router,
    nodes_router,
    edges_router,
    tenants_router,
    graph_router,
    context_router,
    sync_router,
    datasets_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print(f"Starting {settings.APP_NAME}...")
    yield
    # Shutdown
    print(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="""
    FAQ/Knowledge Base System API
    
    A comprehensive knowledge management system with:
    - Hybrid search (BM25 + Vector similarity)
    - Knowledge graph relationships
    - Question variants for improved matching
    - Staging workflow for content review
    - Analytics and metrics
    
    ## Features
    
    ### Knowledge Management
    - Create, read, update, delete knowledge items
    - Support for multiple knowledge types (FAQ, Business Rule, Procedure, etc.)
    - Hierarchical categories
    - Version history with rollback capability
    
    ### Search
    - Hybrid search combining full-text (BM25) and semantic (vector) search
    - Configurable weights for search components
    - Filter by type, tags, visibility, status
    
    ### Staging & Review
    - Pipeline-generated content goes to staging
    - Review workflow with approve/reject actions
    - Support for merge and variant addition
    
    ### Analytics
    - Hit tracking and usage metrics
    - Top performing items
    - Daily trends
    - Tag statistics
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ORIGINS != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers (legacy)
app.include_router(knowledge_router, prefix="/api")
app.include_router(staging_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(settings_router, prefix="/api")

# Include routers (Knowledge Verse)
app.include_router(nodes_router, prefix="/api")
app.include_router(edges_router, prefix="/api")
app.include_router(tenants_router, prefix="/api")
app.include_router(graph_router, prefix="/api")
app.include_router(context_router, prefix="/api")
app.include_router(sync_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")


@app.get("/", tags=["health"])
async def root():
    """Root endpoint - health check."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0"
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "database": "connected",  # TODO: Add actual DB health check
        "embedding_service": "available",  # TODO: Add actual service check
    }
