"""
Search API routes.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_embedding_client, get_current_user
from app.core.rate_limit import rate_limit_dependency
from app.core.config import settings
from app.clients.embedding_client import EmbeddingClient
from app.services.search_service import SearchService
from app.schemas.search import SearchRequest, SearchResponse


router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: dict = Depends(get_current_user),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    _rate_limit: None = Depends(rate_limit_dependency(
        limit=settings.RATE_LIMIT_SEARCH_LIMIT,
        window=settings.RATE_LIMIT_DEFAULT_WINDOW,
    )),
):
    """
    Search knowledge base using hybrid search (BM25 + Vector).
    
    The search combines:
    - BM25 full-text search (default 40% weight)
    - Vector similarity search (default 60% weight)
    
    Results are ranked using Reciprocal Rank Fusion (RRF).
    
    Headers:
    - X-Session-ID: Optional session ID for analytics tracking
    """
    email = current_user["email"]
    
    service = SearchService(session, embedding_client)
    return await service.hybrid_search(
        request,
        session_id=x_session_id,
        user_id=user_id if user_id != "anonymous" else None
    )
