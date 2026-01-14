#!/usr/bin/env python3
"""
Example: Integrating ContextForge into an existing FastAPI application.

REQUIRED: Set DATABASE_URL environment variable before running.

    export DATABASE_URL="postgresql+asyncpg://user:pass@host/db"
    python examples/library_integration.py [basic|full|openai|jwt]
"""

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from pydantic import BaseModel


def _require_database_url() -> str:
    """Get DATABASE_URL or exit with helpful message."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL environment variable is required.")
        print("\nExample:")
        print('  export DATABASE_URL="postgresql+asyncpg://user:pass@host/db"')
        sys.exit(1)
    return url


# =============================================================================
# Example 1: Basic Integration
# =============================================================================

def create_basic_app() -> FastAPI:
    """Minimal integration - ContextForge API routes only."""
    from contextforge import ContextForge
    from contextforge.providers.embedding import SentenceTransformersProvider
    
    database_url = _require_database_url()
    
    cf = ContextForge(
        database_url=database_url,
        embedding_provider=SentenceTransformersProvider(),
    )
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await cf.dispose()
    
    app = FastAPI(title="My App with ContextForge", lifespan=lifespan)
    app.include_router(cf.router, prefix="/api/kb", tags=["Knowledge Base"])
    
    @app.get("/")
    async def root():
        return {"message": "ContextForge API at /api/kb"}
    
    return app


# =============================================================================
# Example 2: Full Integration with Admin UI
# =============================================================================

def create_full_app() -> FastAPI:
    """Full integration - API + Admin UI."""
    from contextforge import ContextForge, ContextForgeConfig
    from contextforge.providers.embedding import SentenceTransformersProvider
    
    database_url = _require_database_url()
    
    cf = ContextForge(
        config=ContextForgeConfig(
            database_url=database_url,
            admin_ui_enabled=True,
            admin_ui_title="My Knowledge Base",
        ),
        embedding_provider=SentenceTransformersProvider(),
    )
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await cf.dispose()
    
    app = FastAPI(title="My App", lifespan=lifespan)
    app.mount("/knowledge", cf.app)
    
    @app.get("/")
    async def root():
        return {"knowledge_base": "/knowledge", "admin_ui": "/knowledge/admin"}
    
    return app


# =============================================================================
# Example 3: Using OpenAI Providers
# =============================================================================

def create_openai_app() -> FastAPI:
    """Integration using OpenAI for embeddings and LLM."""
    from contextforge import ContextForge, ContextForgeConfig
    from contextforge.providers.embedding import OpenAIEmbeddingProvider
    from contextforge.providers.llm import OpenAILLMProvider
    
    database_url = _require_database_url()
    
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable is required for this example.")
        sys.exit(1)
    
    cf = ContextForge(
        config=ContextForgeConfig(database_url=database_url, enable_queryforge=True),
        embedding_provider=OpenAIEmbeddingProvider(model="text-embedding-3-small"),
        llm_provider=OpenAILLMProvider(model="gpt-4o-mini"),
    )
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await cf.dispose()
    
    app = FastAPI(title="OpenAI-powered Knowledge Base", lifespan=lifespan)
    app.include_router(cf.router, prefix="/api/kb")
    
    return app


# =============================================================================
# Example 4: JWT Authentication
# =============================================================================

def create_jwt_app() -> FastAPI:
    """Integration with JWT authentication."""
    from contextforge import ContextForge, ContextForgeConfig
    from contextforge.providers.embedding import SentenceTransformersProvider
    from contextforge.providers.auth import JWTAuthProvider
    
    database_url = _require_database_url()
    jwt_secret = os.environ.get("JWT_SECRET_KEY")
    if not jwt_secret:
        print("ERROR: JWT_SECRET_KEY environment variable is required for this example.")
        sys.exit(1)
    
    cf = ContextForge(
        config=ContextForgeConfig(database_url=database_url),
        embedding_provider=SentenceTransformersProvider(),
        auth_provider=JWTAuthProvider(secret_key=jwt_secret),
    )
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await cf.dispose()
    
    app = FastAPI(title="Secure Knowledge Base", lifespan=lifespan)
    app.include_router(cf.router, prefix="/api/kb")
    
    return app


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    examples = {
        "basic": create_basic_app,
        "full": create_full_app,
        "openai": create_openai_app,
        "jwt": create_jwt_app,
    }
    
    example = sys.argv[1] if len(sys.argv) > 1 else "basic"
    
    if example not in examples:
        print(f"Unknown example: {example}")
        print(f"Available: {', '.join(examples.keys())}")
        sys.exit(1)
    
    print(f"\nRunning '{example}' example...")
    print("=" * 50)
    
    app = examples[example]()
    uvicorn.run(app, host="0.0.0.0", port=8000)
