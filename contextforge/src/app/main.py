"""
FAQ/Knowledge Base System - FastAPI Application

Main application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.dependencies import (
    EmbeddingClientNotConfiguredError,
    InferenceClientNotConfiguredError,
)
from app.services.node_service import EmbeddingClientRequiredError
from app.core.logging import setup_logging
from app.routes import (
    nodes_router,
    edges_router,
    tenants_router,
    graph_router,
    context_router,
    sync_router,
    datasets_router,
    search_router,
    metrics_router,
    settings_router,
    health_router,
    onboarding_router,
    staging_router,
)


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME}...")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


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


app.include_router(nodes_router, prefix="/api")
app.include_router(edges_router, prefix="/api")
app.include_router(tenants_router, prefix="/api")
app.include_router(graph_router, prefix="/api")
app.include_router(context_router, prefix="/api")
app.include_router(sync_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(onboarding_router, prefix="/api")
app.include_router(staging_router, prefix="/api")
app.include_router(health_router)


@app.exception_handler(EmbeddingClientNotConfiguredError)
async def embedding_not_configured_handler(request: Request, exc: EmbeddingClientNotConfiguredError):
    logger.warning(f"Embedding service not configured: {request.url.path}")
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Embedding service not configured",
            "help": "Set OPENAI_API_KEY or install sentence-transformers",
        },
    )


@app.exception_handler(InferenceClientNotConfiguredError)
async def inference_not_configured_handler(request: Request, exc: InferenceClientNotConfiguredError):
    logger.warning(f"LLM service not configured: {request.url.path}")
    return JSONResponse(
        status_code=503,
        content={
            "detail": "LLM service not configured",
            "help": "Set OPENAI_API_KEY environment variable",
        },
    )


@app.exception_handler(EmbeddingClientRequiredError)
async def embedding_required_handler(request: Request, exc: EmbeddingClientRequiredError):
    logger.warning(f"Embedding client required: {request.url.path}")
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Embedding service required for this operation",
            "help": "Set OPENAI_API_KEY or install sentence-transformers",
        },
    )


@app.get("/", tags=["root"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health/ready",
    }
