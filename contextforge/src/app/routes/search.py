"""
Search API routes.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_embedding_client, get_user_tenant_ids
from app.clients.embedding_client import EmbeddingClient
from app.services.node_service import NodeService
from app.schemas.search import SearchRequest, SearchResponse, SearchResult


router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    user_tenant_ids: List[str] = Depends(get_user_tenant_ids),
):
    """
    Search knowledge base using hybrid search (BM25 + Vector).
    
    The search combines:
    - BM25 full-text search (default 40% weight)
    - Vector similarity search (default 60% weight)
    
    Results are ranked using Reciprocal Rank Fusion (RRF).
    """
    service = NodeService(session, embedding_client)
    
    results = await service.hybrid_search(
        query_text=request.query,
        user_tenant_ids=user_tenant_ids,
        node_types=request.node_types,
        tags=request.tags,
        bm25_weight=request.bm25_weight or 0.4,
        vector_weight=request.vector_weight or 0.6,
        limit=request.limit or 10,
    )
    
    return SearchResponse(
        query=request.query,
        results=[
            SearchResult(
                id=r.node.id,
                node_type=r.node.node_type.value,
                title=r.node.title,
                summary=r.node.summary,
                content=r.node.content,
                tags=r.node.tags or [],
                hybrid_score=r.rrf_score,
                match_sources=r.match_sources,
            )
            for r in results
        ],
        total=len(results),
    )
