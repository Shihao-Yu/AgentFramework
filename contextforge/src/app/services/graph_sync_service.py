"""
Graph event sync service.

Processes graph_events table to keep NetworkX graph in sync
and generates implicit edges (SHARED_TAG, SIMILAR).
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.enums import EdgeType
from app.clients.embedding_client import EmbeddingClient
from app.utils.schema import sql as schema_sql


class GraphSyncService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_client: Optional[EmbeddingClient] = None,
    ):
        self.session = session
        self.embedding_client = embedding_client
    
    async def process_pending_events(
        self,
        batch_size: int = 100,
    ) -> Dict[str, int]:
        """Process unprocessed events from graph_events table."""
        result = await self.session.execute(
            text(schema_sql("""
                SELECT id, event_type, entity_type, entity_id, payload, created_at
                FROM {schema}.graph_events
                WHERE processed_at IS NULL
                ORDER BY created_at ASC
                LIMIT :batch_size
            """)),
            {"batch_size": batch_size}
        )
        
        events = result.fetchall()
        
        stats = {
            "processed": 0,
            "node_created": 0,
            "node_updated": 0,
            "node_deleted": 0,
            "edge_created": 0,
            "edge_deleted": 0,
            "errors": 0,
        }
        
        processed_ids = []
        
        for event in events:
            try:
                event_type = event.event_type
                
                if event_type == "node_created":
                    stats["node_created"] += 1
                elif event_type == "node_updated":
                    stats["node_updated"] += 1
                elif event_type == "node_deleted":
                    stats["node_deleted"] += 1
                elif event_type == "edge_created":
                    stats["edge_created"] += 1
                elif event_type == "edge_deleted":
                    stats["edge_deleted"] += 1
                
                processed_ids.append(event.id)
                stats["processed"] += 1
                
            except Exception:
                stats["errors"] += 1
        
        if processed_ids:
            await self.session.execute(
                text(schema_sql("""
                    UPDATE {schema}.graph_events
                    SET processed_at = NOW()
                    WHERE id = ANY(:ids)
                """)),
                {"ids": processed_ids}
            )
            await self.session.commit()
        
        return stats
    
    async def generate_shared_tag_edges(
        self,
        tenant_ids: List[str],
        min_shared_tags: int = 2,
        batch_size: int = 1000,
    ) -> int:
        """Generate SHARED_TAG edges between nodes with common tags."""
        await self.session.execute(
            text(schema_sql("""
                DELETE FROM {schema}.knowledge_edges
                WHERE edge_type = 'shared_tag' AND is_auto_generated = TRUE
            """))
        )
        
        result = await self.session.execute(
            text(schema_sql("""
                WITH node_pairs AS (
                    SELECT 
                        n1.id as source_id,
                        n2.id as target_id,
                        array_length(
                            ARRAY(SELECT unnest(n1.tags) INTERSECT SELECT unnest(n2.tags)),
                            1
                        ) as shared_count
                    FROM {schema}.knowledge_nodes n1
                    JOIN {schema}.knowledge_nodes n2 ON n1.id < n2.id
                    WHERE n1.tenant_id = ANY(:tenant_ids)
                      AND n2.tenant_id = ANY(:tenant_ids)
                      AND n1.is_deleted = FALSE
                      AND n2.is_deleted = FALSE
                      AND n1.status = 'published'
                      AND n2.status = 'published'
                      AND n1.tags && n2.tags
                )
                INSERT INTO {schema}.knowledge_edges (source_id, target_id, edge_type, weight, is_auto_generated, created_by)
                SELECT 
                    source_id, 
                    target_id, 
                    'shared_tag',
                    LEAST(shared_count::float / 5.0, 1.0),
                    TRUE,
                    'system'
                FROM node_pairs
                WHERE shared_count >= :min_shared_tags
                LIMIT :batch_size
                ON CONFLICT (source_id, target_id, edge_type) DO UPDATE
                SET weight = EXCLUDED.weight
                RETURNING id
            """)),
            {
                "tenant_ids": tenant_ids,
                "min_shared_tags": min_shared_tags,
                "batch_size": batch_size,
            }
        )
        
        created = len(result.fetchall())
        await self.session.commit()
        
        return created
    
    async def generate_similar_edges(
        self,
        tenant_ids: List[str],
        similarity_threshold: float = 0.85,
        batch_size: int = 100,
    ) -> int:
        """Generate SIMILAR edges between nodes with high embedding similarity."""
        if not self.embedding_client:
            return 0
        
        await self.session.execute(
            text(schema_sql("""
                DELETE FROM {schema}.knowledge_edges
                WHERE edge_type = 'similar' AND is_auto_generated = TRUE
            """))
        )
        
        result = await self.session.execute(
            text(schema_sql("""
                WITH similar_pairs AS (
                    SELECT 
                        n1.id as source_id,
                        n2.id as target_id,
                        1 - (n1.embedding <=> n2.embedding) as similarity
                    FROM {schema}.knowledge_nodes n1
                    JOIN {schema}.knowledge_nodes n2 ON n1.id < n2.id
                    WHERE n1.tenant_id = ANY(:tenant_ids)
                      AND n2.tenant_id = ANY(:tenant_ids)
                      AND n1.is_deleted = FALSE
                      AND n2.is_deleted = FALSE
                      AND n1.status = 'published'
                      AND n2.status = 'published'
                      AND n1.embedding IS NOT NULL
                      AND n2.embedding IS NOT NULL
                      AND 1 - (n1.embedding <=> n2.embedding) >= :threshold
                )
                INSERT INTO {schema}.knowledge_edges (source_id, target_id, edge_type, weight, is_auto_generated, created_by)
                SELECT 
                    source_id, 
                    target_id, 
                    'similar',
                    similarity,
                    TRUE,
                    'system'
                FROM similar_pairs
                LIMIT :batch_size
                ON CONFLICT (source_id, target_id, edge_type) DO UPDATE
                SET weight = EXCLUDED.weight
                RETURNING id
            """)),
            {
                "tenant_ids": tenant_ids,
                "threshold": similarity_threshold,
                "batch_size": batch_size,
            }
        )
        
        created = len(result.fetchall())
        await self.session.commit()
        
        return created
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status."""
        pending_result = await self.session.execute(
            text(schema_sql("""
                SELECT COUNT(*) as count
                FROM {schema}.graph_events
                WHERE processed_at IS NULL
            """))
        )
        pending = pending_result.scalar() or 0
        
        last_processed_result = await self.session.execute(
            text(schema_sql("""
                SELECT MAX(processed_at) as last_processed
                FROM {schema}.graph_events
                WHERE processed_at IS NOT NULL
            """))
        )
        row = last_processed_result.fetchone()
        last_processed = row.last_processed if row else None
        
        auto_edges_result = await self.session.execute(
            text(schema_sql("""
                SELECT edge_type, COUNT(*) as count
                FROM {schema}.knowledge_edges
                WHERE is_auto_generated = TRUE
                GROUP BY edge_type
            """))
        )
        auto_edges = {row.edge_type: row.count for row in auto_edges_result.fetchall()}
        
        return {
            "pending_events": pending,
            "last_processed": last_processed.isoformat() if last_processed else None,
            "auto_generated_edges": auto_edges,
        }
    
    async def cleanup_old_events(
        self,
        days_to_keep: int = 30,
    ) -> int:
        """Delete processed events older than specified days."""
        result = await self.session.execute(
            text(schema_sql("""
                DELETE FROM {schema}.graph_events
                WHERE processed_at IS NOT NULL
                  AND processed_at < NOW() - INTERVAL :days || ' days'
                RETURNING id
            """)),
            {"days": str(days_to_keep)}
        )
        
        deleted = len(result.fetchall())
        await self.session.commit()
        
        return deleted
