"""
Metrics and analytics service.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.knowledge import KnowledgeItem
from app.models.analytics import KnowledgeHit
from app.models.enums import KnowledgeStatus
from app.schemas.metrics import (
    MetricsSummaryResponse,
    KnowledgeHitStats,
    TopItemsResponse,
    DailyHitStats,
    DailyTrendResponse,
    TagStats,
    TagStatsResponse,
    ItemStatsResponse,
)


class MetricsService:
    """Service for analytics and metrics."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_summary(self, days: int = 7) -> MetricsSummaryResponse:
        """Get overall metrics summary."""
        
        # Count items by status
        total_query = select(func.count(KnowledgeItem.id)).where(
            KnowledgeItem.is_deleted == False
        )
        published_query = select(func.count(KnowledgeItem.id)).where(
            KnowledgeItem.is_deleted == False,
            KnowledgeItem.status == KnowledgeStatus.PUBLISHED
        )
        draft_query = select(func.count(KnowledgeItem.id)).where(
            KnowledgeItem.is_deleted == False,
            KnowledgeItem.status == KnowledgeStatus.DRAFT
        )
        archived_query = select(func.count(KnowledgeItem.id)).where(
            KnowledgeItem.is_deleted == False,
            KnowledgeItem.status == KnowledgeStatus.ARCHIVED
        )
        
        total = (await self.session.execute(total_query)).scalar() or 0
        published = (await self.session.execute(published_query)).scalar() or 0
        draft = (await self.session.execute(draft_query)).scalar() or 0
        archived = (await self.session.execute(archived_query)).scalar() or 0
        
        # Hit stats for period
        start_date = datetime.utcnow() - timedelta(days=days)
        
        hits_query = select(func.count(KnowledgeHit.id)).where(
            KnowledgeHit.hit_at >= start_date
        )
        sessions_query = select(func.count(func.distinct(KnowledgeHit.session_id))).where(
            KnowledgeHit.hit_at >= start_date
        )
        
        total_hits = (await self.session.execute(hits_query)).scalar() or 0
        total_sessions = (await self.session.execute(sessions_query)).scalar() or 0
        
        # Items never accessed
        never_accessed_sql = text("""
            SELECT COUNT(*) FROM agent.knowledge_items k
            WHERE k.is_deleted = FALSE
              AND k.status = 'published'
              AND NOT EXISTS (
                  SELECT 1 FROM agent.knowledge_hits h 
                  WHERE h.knowledge_item_id = k.id
              )
        """)
        never_accessed = (await self.session.execute(never_accessed_sql)).scalar() or 0
        
        return MetricsSummaryResponse(
            total_items=total,
            published_items=published,
            draft_items=draft,
            archived_items=archived,
            total_hits=total_hits,
            total_sessions=total_sessions,
            avg_daily_sessions=total_sessions / days if days > 0 else 0,
            never_accessed_count=never_accessed
        )
    
    async def get_top_items(
        self,
        limit: int = 10,
        days: int = 7
    ) -> TopItemsResponse:
        """Get top performing items by hits."""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        sql = text("""
            SELECT 
                k.id,
                k.knowledge_type,
                k.title,
                k.tags,
                COUNT(h.id) AS total_hits,
                COUNT(DISTINCT h.session_id) AS unique_sessions,
                COUNT(DISTINCT DATE(h.hit_at)) AS days_with_hits,
                MAX(h.hit_at) AS last_hit_at,
                ROUND(AVG(h.similarity_score)::numeric, 3) AS avg_similarity,
                MODE() WITHIN GROUP (ORDER BY h.retrieval_method) AS primary_retrieval_method
            FROM agent.knowledge_items k
            JOIN agent.knowledge_hits h ON k.id = h.knowledge_item_id
            WHERE k.is_deleted = FALSE
              AND h.hit_at >= :start_date
            GROUP BY k.id, k.knowledge_type, k.title, k.tags
            ORDER BY total_hits DESC
            LIMIT :limit
        """)
        
        result = await self.session.execute(sql, {
            "start_date": start_date,
            "limit": limit
        })
        
        items = []
        for row in result.fetchall():
            items.append(KnowledgeHitStats(
                id=row.id,
                knowledge_type=row.knowledge_type,
                title=row.title,
                tags=row.tags or [],
                total_hits=row.total_hits,
                unique_sessions=row.unique_sessions,
                days_with_hits=row.days_with_hits,
                last_hit_at=row.last_hit_at,
                avg_similarity=float(row.avg_similarity) if row.avg_similarity else None,
                primary_retrieval_method=row.primary_retrieval_method
            ))
        
        return TopItemsResponse(items=items, period_days=days)
    
    async def get_daily_trend(self, days: int = 7) -> DailyTrendResponse:
        """Get daily hit trend."""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        sql = text("""
            SELECT 
                DATE(hit_at) AS date,
                COUNT(*) AS total_hits,
                COUNT(DISTINCT session_id) AS unique_sessions
            FROM agent.knowledge_hits
            WHERE hit_at >= :start_date
            GROUP BY DATE(hit_at)
            ORDER BY date
        """)
        
        result = await self.session.execute(sql, {"start_date": start_date})
        
        data = []
        for row in result.fetchall():
            data.append(DailyHitStats(
                date=row.date.isoformat(),
                total_hits=row.total_hits,
                unique_sessions=row.unique_sessions
            ))
        
        return DailyTrendResponse(data=data, period_days=days)
    
    async def get_tag_stats(self, limit: int = 20) -> TagStatsResponse:
        """Get tag usage statistics."""
        
        sql = text("""
            SELECT 
                unnest(k.tags) AS tag,
                COUNT(*) AS count,
                COALESCE(SUM(stats.total_hits), 0) AS total_hits
            FROM agent.knowledge_items k
            LEFT JOIN (
                SELECT knowledge_item_id, COUNT(*) AS total_hits
                FROM agent.knowledge_hits
                GROUP BY knowledge_item_id
            ) stats ON k.id = stats.knowledge_item_id
            WHERE k.is_deleted = FALSE
            GROUP BY tag
            ORDER BY count DESC
            LIMIT :limit
        """)
        
        result = await self.session.execute(sql, {"limit": limit})
        
        tags = []
        for row in result.fetchall():
            tags.append(TagStats(
                tag=row.tag,
                count=row.count,
                total_hits=row.total_hits
            ))
        
        # Get total unique tags
        total_sql = text("""
            SELECT COUNT(DISTINCT unnest(tags)) 
            FROM agent.knowledge_items 
            WHERE is_deleted = FALSE
        """)
        total = (await self.session.execute(total_sql)).scalar() or 0
        
        return TagStatsResponse(tags=tags, total_tags=total)
    
    async def get_item_stats(
        self,
        item_id: int,
        days: int = 30
    ) -> Optional[ItemStatsResponse]:
        """Get detailed stats for a single item."""
        
        # Get item
        item = await self.session.get(KnowledgeItem, item_id)
        if not item or item.is_deleted:
            return None
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Aggregate stats
        stats_sql = text("""
            SELECT 
                COUNT(*) AS total_hits,
                COUNT(DISTINCT session_id) AS unique_sessions,
                COUNT(DISTINCT DATE(hit_at)) AS days_with_hits,
                MIN(hit_at) AS first_hit,
                MAX(hit_at) AS last_hit,
                ROUND(AVG(similarity_score)::numeric, 3) AS avg_similarity
            FROM agent.knowledge_hits
            WHERE knowledge_item_id = :item_id
        """)
        
        result = await self.session.execute(stats_sql, {"item_id": item_id})
        row = result.fetchone()
        
        # Recent queries
        queries_sql = text("""
            SELECT DISTINCT query_text
            FROM agent.knowledge_hits
            WHERE knowledge_item_id = :item_id
              AND query_text IS NOT NULL
            ORDER BY MAX(hit_at) DESC
            LIMIT 10
        """)
        queries_result = await self.session.execute(queries_sql, {"item_id": item_id})
        queries = [r.query_text for r in queries_result.fetchall()]
        
        # Daily trend for this item
        trend_sql = text("""
            SELECT 
                DATE(hit_at) AS date,
                COUNT(*) AS total_hits,
                COUNT(DISTINCT session_id) AS unique_sessions
            FROM agent.knowledge_hits
            WHERE knowledge_item_id = :item_id
              AND hit_at >= :start_date
            GROUP BY DATE(hit_at)
            ORDER BY date
        """)
        trend_result = await self.session.execute(trend_sql, {
            "item_id": item_id,
            "start_date": start_date
        })
        
        hit_trend = []
        for tr in trend_result.fetchall():
            hit_trend.append(DailyHitStats(
                date=tr.date.isoformat(),
                total_hits=tr.total_hits,
                unique_sessions=tr.unique_sessions
            ))
        
        return ItemStatsResponse(
            item_id=item_id,
            title=item.title,
            total_hits=row.total_hits or 0,
            unique_sessions=row.unique_sessions or 0,
            days_with_hits=row.days_with_hits or 0,
            first_hit=row.first_hit,
            last_hit=row.last_hit,
            avg_similarity=float(row.avg_similarity) if row.avg_similarity else None,
            queries=queries,
            hit_trend=hit_trend
        )
