"""
Search service for hybrid and context-aware search.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.analytics import KnowledgeHit
from app.schemas.search import (
    SearchRequest,
    SearchResult,
    SearchResponse,
)
from app.clients.embedding_client import EmbeddingClient
from app.core.config import settings


class SearchService:
    """Service for knowledge search operations."""
    
    def __init__(self, session: AsyncSession, embedding_client: EmbeddingClient):
        self.session = session
        self.embedding_client = embedding_client
    
    async def hybrid_search(
        self,
        request: SearchRequest,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> SearchResponse:
        """
        Perform hybrid search combining BM25 and vector similarity.
        Uses Reciprocal Rank Fusion (RRF) for score combination.
        """
        
        # Generate embedding for query
        query_embedding = await self.embedding_client.embed(request.query)
        
        # Prepare parameters
        knowledge_types = None
        if request.knowledge_types:
            knowledge_types = [kt.value for kt in request.knowledge_types]
        
        # Call hybrid search function
        sql = text("""
            SELECT * FROM agent.search_knowledge_hybrid(
                :query_text,
                :query_embedding::vector,
                :result_limit,
                :bm25_weight,
                :vector_weight,
                :knowledge_types,
                :filter_tags,
                :filter_visibility,
                :filter_status
            )
        """)
        
        result = await self.session.execute(sql, {
            "query_text": request.query,
            "query_embedding": query_embedding,
            "result_limit": request.limit or settings.SEARCH_DEFAULT_LIMIT,
            "bm25_weight": request.bm25_weight or settings.SEARCH_BM25_WEIGHT,
            "vector_weight": request.vector_weight or settings.SEARCH_VECTOR_WEIGHT,
            "knowledge_types": knowledge_types,
            "filter_tags": request.tags,
            "filter_visibility": request.visibility.value if request.visibility else "internal",
            "filter_status": request.status.value if request.status else "published",
        })
        
        rows = result.fetchall()
        
        # Convert to response format
        results = []
        for row in rows:
            results.append(SearchResult(
                id=row.id,
                knowledge_type=row.knowledge_type,
                title=row.title,
                summary=row.summary,
                content=row.content,
                tags=row.tags or [],
                hybrid_score=float(row.hybrid_score),
                match_sources=row.match_sources.split(",") if row.match_sources else []
            ))
        
        # Record hits for analytics
        if session_id and results:
            await self._record_hits(request.query, results, session_id, user_id)
        
        return SearchResponse(
            query=request.query,
            results=results,
            total=len(results)
        )
    
    async def _record_hits(
        self,
        query: str,
        results: List[SearchResult],
        session_id: str,
        user_id: Optional[str]
    ) -> None:
        """Record search hits for analytics."""
        
        for result in results:
            hit = KnowledgeHit(
                knowledge_item_id=result.id,
                query_text=query,
                similarity_score=result.hybrid_score,
                retrieval_method="hybrid",
                match_source=",".join(result.match_sources),
                session_id=session_id,
                user_id=user_id,
            )
            self.session.add(hit)
        
        await self.session.commit()
    
    async def simple_vector_search(
        self,
        query: str,
        limit: int = 10,
        knowledge_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Simple vector-only search for internal use (e.g., pipeline similarity).
        
        Returns raw results without recording hits.
        """
        
        embedding = await self.embedding_client.embed(query)
        
        sql = text("""
            SELECT 
                id, 
                knowledge_type,
                title, 
                content,
                1 - (embedding <=> :embedding::vector) as similarity
            FROM agent.knowledge_items
            WHERE embedding IS NOT NULL
              AND is_deleted = FALSE
              AND status = 'published'
              AND (:types IS NULL OR knowledge_type = ANY(:types))
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """)
        
        result = await self.session.execute(sql, {
            "embedding": embedding,
            "types": knowledge_types,
            "limit": limit
        })
        
        rows = result.fetchall()
        return [
            {
                "id": row.id,
                "knowledge_type": row.knowledge_type,
                "title": row.title,
                "content": row.content,
                "similarity": float(row.similarity)
            }
            for row in rows
        ]
