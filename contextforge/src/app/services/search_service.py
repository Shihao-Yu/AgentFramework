"""
Search service for hybrid and context-aware search.

Note: Primary search is in NodeService.hybrid_search which uses knowledge_nodes.
This service provides utilities and legacy compatibility.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.clients.embedding_client import EmbeddingClient
from app.utils.schema import sql as schema_sql


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_client: EmbeddingClient,
        user_tenant_ids: List[str],
    ):
        self.session = session
        self.embedding_client = embedding_client
        self.user_tenant_ids = user_tenant_ids

    async def simple_vector_search(
        self,
        query_text: str,
        limit: int = 10,
        node_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        embedding = await self.embedding_client.embed(query_text)
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        stmt = text(schema_sql("""
            SELECT 
                id, 
                node_type,
                title, 
                content,
                1 - (embedding <=> :embedding::vector) as similarity
            FROM {schema}.knowledge_nodes
            WHERE embedding IS NOT NULL
              AND is_deleted = FALSE
              AND status = 'published'
              AND tenant_id = ANY(:tenant_ids)
              AND (:types IS NULL OR node_type = ANY(:types))
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """))

        result = await self.session.execute(stmt, {
            "embedding": embedding_str,
            "tenant_ids": self.user_tenant_ids,
            "types": node_types,
            "limit": limit,
        })

        rows = result.fetchall()
        return [
            {
                "id": row.id,
                "node_type": row.node_type,
                "title": row.title,
                "content": row.content,
                "similarity": float(row.similarity),
            }
            for row in rows
        ]

    async def record_hit(
        self,
        node_id: int,
        query_text: str,
        similarity_score: float,
        retrieval_method: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        stmt = text(schema_sql("""
            INSERT INTO {schema}.knowledge_hits (
                node_id, query_text, similarity_score, 
                retrieval_method, session_id, user_id
            ) VALUES (
                :node_id, :query_text, :similarity_score,
                :retrieval_method, :session_id, :user_id
            )
        """))
        await self.session.execute(stmt, {
            "node_id": node_id,
            "query_text": query_text,
            "similarity_score": similarity_score,
            "retrieval_method": retrieval_method,
            "session_id": session_id,
            "user_id": user_id,
        })
        await self.session.commit()
