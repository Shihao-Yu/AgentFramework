"""
Metrics and analytics service.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.nodes import KnowledgeNode
from app.models.enums import KnowledgeStatus, NodeType
from app.utils.schema import sql as schema_sql
from app.schemas.metrics import (
    MetricsSummaryResponse,
    KnowledgeHitStats,
    TopItemsResponse,
    DailyHitStats,
    DailyTrendResponse,
    TagStats,
    TagStatsResponse,
    ItemStatsResponse,
    HeatmapNodeData,
    HeatmapStats,
    HeatmapResponse,
    HeatmapTagData,
    HeatmapTagsResponse,
    HeatmapTypeData,
    HeatmapTypesResponse,
)


@dataclass
class HitRecord:
    """Data for a single hit to record."""
    node_id: int
    similarity_score: Optional[float] = None
    retrieval_method: Optional[str] = None  # 'bm25', 'vector', 'hybrid'


class MetricsService:
    def __init__(self, session: AsyncSession, user_tenant_ids: List[str]):
        self.session = session
        self.user_tenant_ids = user_tenant_ids

    async def get_summary(
        self, days: int = 7, node_types: list[str] | None = None
    ) -> MetricsSummaryResponse:
        base_filters = [
            KnowledgeNode.is_deleted == False,
            KnowledgeNode.tenant_id.in_(self.user_tenant_ids),
        ]
        if node_types:
            enum_types = [NodeType(nt) for nt in node_types]
            base_filters.append(KnowledgeNode.node_type.in_(enum_types))

        total_query = select(func.count(KnowledgeNode.id)).where(*base_filters)
        published_query = select(func.count(KnowledgeNode.id)).where(
            *base_filters,
            KnowledgeNode.status == KnowledgeStatus.PUBLISHED,
        )
        draft_query = select(func.count(KnowledgeNode.id)).where(
            *base_filters,
            KnowledgeNode.status == KnowledgeStatus.DRAFT,
        )
        archived_query = select(func.count(KnowledgeNode.id)).where(
            *base_filters,
            KnowledgeNode.status == KnowledgeStatus.ARCHIVED,
        )

        total = (await self.session.execute(total_query)).scalar() or 0
        published = (await self.session.execute(published_query)).scalar() or 0
        draft = (await self.session.execute(draft_query)).scalar() or 0
        archived = (await self.session.execute(archived_query)).scalar() or 0

        start_date = datetime.utcnow() - timedelta(days=days)

        hits_stmt = text(schema_sql("""
            SELECT COUNT(*) FROM {schema}.knowledge_hits
            WHERE hit_at >= :start_date
        """))
        sessions_stmt = text(schema_sql("""
            SELECT COUNT(DISTINCT session_id) FROM {schema}.knowledge_hits
            WHERE hit_at >= :start_date
        """))

        total_hits = (await self.session.execute(hits_stmt, {"start_date": start_date})).scalar() or 0
        total_sessions = (await self.session.execute(sessions_stmt, {"start_date": start_date})).scalar() or 0

        node_type_filter = ""
        if node_types:
            node_type_list = ", ".join(f"'{nt}'" for nt in node_types)
            node_type_filter = f"AND k.node_type IN ({node_type_list})"

        never_accessed_stmt = text(schema_sql(f"""
            SELECT COUNT(*) FROM {{schema}}.knowledge_nodes k
            WHERE k.is_deleted = FALSE
              AND k.status = 'published'
              AND k.tenant_id = ANY(:tenant_ids)
              {node_type_filter}
              AND NOT EXISTS (
                  SELECT 1 FROM {{schema}}.knowledge_hits h 
                  WHERE h.node_id = k.id
              )
        """))
        never_accessed = (await self.session.execute(
            never_accessed_stmt, {"tenant_ids": self.user_tenant_ids}
        )).scalar() or 0

        return MetricsSummaryResponse(
            total_items=total,
            published_items=published,
            draft_items=draft,
            archived_items=archived,
            total_hits=total_hits,
            total_sessions=total_sessions,
            avg_daily_sessions=total_sessions / days if days > 0 else 0,
            never_accessed_count=never_accessed,
        )
    
    async def get_top_items(
        self,
        limit: int = 10,
        days: int = 7,
    ) -> TopItemsResponse:
        start_date = datetime.utcnow() - timedelta(days=days)

        stmt = text(schema_sql("""
            SELECT 
                k.id,
                k.node_type,
                k.title,
                k.tags,
                COUNT(h.id) AS total_hits,
                COUNT(DISTINCT h.session_id) AS unique_sessions,
                COUNT(DISTINCT DATE(h.hit_at)) AS days_with_hits,
                MAX(h.hit_at) AS last_hit_at,
                ROUND(AVG(h.similarity_score)::numeric, 3) AS avg_similarity,
                MODE() WITHIN GROUP (ORDER BY h.retrieval_method) AS primary_retrieval_method
            FROM {schema}.knowledge_nodes k
            JOIN {schema}.knowledge_hits h ON k.id = h.node_id
            WHERE k.is_deleted = FALSE
              AND k.tenant_id = ANY(:tenant_ids)
              AND h.hit_at >= :start_date
            GROUP BY k.id, k.node_type, k.title, k.tags
            ORDER BY total_hits DESC
            LIMIT :limit
        """))

        result = await self.session.execute(stmt, {
            "start_date": start_date,
            "limit": limit,
            "tenant_ids": self.user_tenant_ids,
        })

        items = []
        for row in result.fetchall():
            items.append(KnowledgeHitStats(
                id=row.id,
                knowledge_type=row.node_type,
                title=row.title,
                tags=row.tags or [],
                total_hits=row.total_hits,
                unique_sessions=row.unique_sessions,
                days_with_hits=row.days_with_hits,
                last_hit_at=row.last_hit_at,
                avg_similarity=float(row.avg_similarity) if row.avg_similarity else None,
                primary_retrieval_method=row.primary_retrieval_method,
            ))

        return TopItemsResponse(items=items, period_days=days)
    
    async def get_daily_trend(self, days: int = 7) -> DailyTrendResponse:
        """Get daily hit trend."""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        stmt = text(schema_sql("""
            SELECT 
                DATE(hit_at) AS date,
                COUNT(*) AS total_hits,
                COUNT(DISTINCT session_id) AS unique_sessions
            FROM {schema}.knowledge_hits
            WHERE hit_at >= :start_date
            GROUP BY DATE(hit_at)
            ORDER BY date
        """))
        
        result = await self.session.execute(stmt, {"start_date": start_date})
        
        data = []
        for row in result.fetchall():
            data.append(DailyHitStats(
                date=row.date.isoformat(),
                total_hits=row.total_hits,
                unique_sessions=row.unique_sessions
            ))
        
        return DailyTrendResponse(data=data, period_days=days)
    
    async def get_tag_stats(self, limit: int = 20) -> TagStatsResponse:
        stmt = text(schema_sql("""
            SELECT 
                unnest(k.tags) AS tag,
                COUNT(*) AS count,
                COALESCE(SUM(stats.total_hits), 0) AS total_hits
            FROM {schema}.knowledge_nodes k
            LEFT JOIN (
                SELECT node_id, COUNT(*) AS total_hits
                FROM {schema}.knowledge_hits
                GROUP BY node_id
            ) stats ON k.id = stats.node_id
            WHERE k.is_deleted = FALSE
              AND k.tenant_id = ANY(:tenant_ids)
            GROUP BY tag
            ORDER BY count DESC
            LIMIT :limit
        """))

        result = await self.session.execute(stmt, {
            "limit": limit,
            "tenant_ids": self.user_tenant_ids,
        })

        tags = []
        for row in result.fetchall():
            tags.append(TagStats(
                tag=row.tag,
                count=row.count,
                total_hits=row.total_hits,
            ))

        total_stmt = text(schema_sql("""
            SELECT COUNT(DISTINCT unnest(tags)) 
            FROM {schema}.knowledge_nodes 
            WHERE is_deleted = FALSE
              AND tenant_id = ANY(:tenant_ids)
        """))
        total = (await self.session.execute(total_stmt, {"tenant_ids": self.user_tenant_ids})).scalar() or 0

        return TagStatsResponse(tags=tags, total_tags=total)

    async def get_node_stats(
        self,
        node_id: int,
        days: int = 30,
    ) -> Optional[ItemStatsResponse]:
        query = select(KnowledgeNode).where(
            KnowledgeNode.id == node_id,
            KnowledgeNode.is_deleted == False,
            KnowledgeNode.tenant_id.in_(self.user_tenant_ids),
        )
        result = await self.session.execute(query)
        node = result.scalar_one_or_none()
        if not node:
            return None

        start_date = datetime.utcnow() - timedelta(days=days)

        stats_stmt = text(schema_sql("""
            SELECT 
                COUNT(*) AS total_hits,
                COUNT(DISTINCT session_id) AS unique_sessions,
                COUNT(DISTINCT DATE(hit_at)) AS days_with_hits,
                MIN(hit_at) AS first_hit,
                MAX(hit_at) AS last_hit,
                ROUND(AVG(similarity_score)::numeric, 3) AS avg_similarity
            FROM {schema}.knowledge_hits
            WHERE node_id = :node_id
        """))

        stats_result = await self.session.execute(stats_stmt, {"node_id": node_id})
        row = stats_result.fetchone()

        queries_stmt = text(schema_sql("""
            SELECT query_text
            FROM {schema}.knowledge_hits
            WHERE node_id = :node_id
              AND query_text IS NOT NULL
            GROUP BY query_text
            ORDER BY MAX(hit_at) DESC
            LIMIT 10
        """))
        queries_result = await self.session.execute(queries_stmt, {"node_id": node_id})
        queries = [r.query_text for r in queries_result.fetchall()]

        trend_stmt = text(schema_sql("""
            SELECT 
                DATE(hit_at) AS date,
                COUNT(*) AS total_hits,
                COUNT(DISTINCT session_id) AS unique_sessions
            FROM {schema}.knowledge_hits
            WHERE node_id = :node_id
              AND hit_at >= :start_date
            GROUP BY DATE(hit_at)
            ORDER BY date
        """))
        trend_result = await self.session.execute(trend_stmt, {
            "node_id": node_id,
            "start_date": start_date,
        })

        hit_trend = []
        for tr in trend_result.fetchall():
            hit_trend.append(DailyHitStats(
                date=tr.date.isoformat(),
                total_hits=tr.total_hits,
                unique_sessions=tr.unique_sessions,
            ))

        return ItemStatsResponse(
            item_id=node_id,
            title=node.title,
            total_hits=row.total_hits or 0,
            unique_sessions=row.unique_sessions or 0,
            days_with_hits=row.days_with_hits or 0,
            first_hit=row.first_hit,
            last_hit=row.last_hit,
            avg_similarity=float(row.avg_similarity) if row.avg_similarity else None,
            queries=queries,
            hit_trend=hit_trend,
        )

    async def record_hits_batch(
        self,
        hits: List[HitRecord],
        query_text: str,
        username: Optional[str] = None,
    ) -> int:
        """
        Record hits for all top-K search results (batch insert).
        
        Args:
            hits: List of HitRecord with node_id, similarity_score, retrieval_method
            query_text: The search query that produced these results
            username: User who performed the search (from auth token)
            
        Returns:
            Number of hits recorded
        """
        if not hits:
            return 0
        
        # TODO: get username from auth token
        username = username or "default"
        
        # Build batch insert values
        values = []
        params = {"query_text": query_text, "username": username}
        
        for i, hit in enumerate(hits):
            values.append(f"""(
                :node_id_{i}, 
                :query_text, 
                :score_{i}, 
                :method_{i}, 
                :username
            )""")
            params[f"node_id_{i}"] = hit.node_id
            params[f"score_{i}"] = hit.similarity_score
            params[f"method_{i}"] = hit.retrieval_method
        
        values_str = ", ".join(values)
        
        stmt = text(schema_sql(f"""
            INSERT INTO {{schema}}.knowledge_hits 
            (node_id, query_text, similarity_score, retrieval_method, user_id)
            VALUES {values_str}
        """))
        
        await self.session.execute(stmt, params)
        await self.session.commit()
        
        return len(hits)

    async def get_heatmap(
        self,
        period: str = "7d",
        metric: str = "hits",
        node_types: Optional[List[str]] = None,
        include_zero: bool = True,
    ) -> HeatmapResponse:
        """
        Get heatmap data for all nodes.
        
        Args:
            period: Time period - '7d', '30d', '90d', 'all'
            metric: Heat metric - 'hits' or 'sessions'
            node_types: Optional filter by node types
            include_zero: Include nodes with 0 hits
            
        Returns:
            HeatmapResponse with per-node heat scores
        """
        # Calculate start date based on period
        days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
        days = days_map.get(period)
        
        date_filter = ""
        if days:
            date_filter = "AND h.hit_at >= NOW() - INTERVAL ':days days'"
        
        node_type_filter = ""
        if node_types:
            node_type_list = ", ".join(f"'{nt}'" for nt in node_types)
            node_type_filter = f"AND n.node_type IN ({node_type_list})"
        
        # Query with PERCENT_RANK for heat score
        stmt = text(schema_sql(f"""
            WITH period_hits AS (
                SELECT 
                    node_id,
                    COUNT(*) as total_hits,
                    COUNT(DISTINCT session_id) as unique_sessions,
                    AVG(similarity_score) as avg_similarity,
                    MAX(hit_at) as last_hit_at
                FROM {{schema}}.knowledge_hits h
                WHERE 1=1 {date_filter.replace(':days', str(days) if days else '0')}
                GROUP BY node_id
            ),
            all_nodes AS (
                SELECT 
                    n.id as node_id,
                    COALESCE(h.total_hits, 0) as total_hits,
                    COALESCE(h.unique_sessions, 0) as unique_sessions,
                    h.avg_similarity,
                    h.last_hit_at
                FROM {{schema}}.knowledge_nodes n
                LEFT JOIN period_hits h ON n.id = h.node_id
                WHERE n.is_deleted = FALSE 
                  AND n.status = 'published'
                  AND n.tenant_id = ANY(:tenant_ids)
                  {node_type_filter}
            )
            SELECT 
                node_id as id,
                total_hits,
                unique_sessions,
                avg_similarity,
                last_hit_at,
                PERCENT_RANK() OVER (ORDER BY {'total_hits' if metric == 'hits' else 'unique_sessions'}) as heat_score
            FROM all_nodes
            {'WHERE total_hits > 0' if not include_zero else ''}
            ORDER BY total_hits DESC
        """))
        
        result = await self.session.execute(stmt, {"tenant_ids": self.user_tenant_ids})
        rows = result.fetchall()
        
        nodes = []
        total_hits = 0
        max_hits = 0
        min_hits = float('inf') if rows else 0
        nodes_with_hits = 0
        
        for row in rows:
            nodes.append(HeatmapNodeData(
                id=row.id,
                total_hits=row.total_hits,
                unique_sessions=row.unique_sessions,
                avg_similarity=float(row.avg_similarity) if row.avg_similarity else None,
                last_hit_at=row.last_hit_at,
                heat_score=float(row.heat_score),
            ))
            total_hits += row.total_hits
            if row.total_hits > max_hits:
                max_hits = row.total_hits
            if row.total_hits < min_hits:
                min_hits = row.total_hits
            if row.total_hits > 0:
                nodes_with_hits += 1
        
        if not rows:
            min_hits = 0
        
        stats = HeatmapStats(
            total_nodes=len(nodes),
            nodes_with_hits=nodes_with_hits,
            total_hits=total_hits,
            max_hits=max_hits,
            min_hits=int(min_hits),
        )
        
        return HeatmapResponse(
            period=period,
            metric=metric,
            generated_at=datetime.utcnow(),
            stats=stats,
            nodes=nodes,
        )

    async def get_heatmap_by_tags(
        self,
        period: str = "7d",
        limit: int = 20,
    ) -> HeatmapTagsResponse:
        """Get heatmap data aggregated by tags."""
        days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
        days = days_map.get(period)
        
        date_filter = ""
        if days:
            date_filter = f"AND h.hit_at >= NOW() - INTERVAL '{days} days'"
        
        stmt = text(schema_sql(f"""
            WITH tag_hits AS (
                SELECT 
                    unnest(n.tags) as tag,
                    COUNT(DISTINCT n.id) as node_count,
                    COALESCE(SUM(stats.total_hits), 0) as total_hits
                FROM {{schema}}.knowledge_nodes n
                LEFT JOIN (
                    SELECT node_id, COUNT(*) as total_hits
                    FROM {{schema}}.knowledge_hits h
                    WHERE 1=1 {date_filter}
                    GROUP BY node_id
                ) stats ON n.id = stats.node_id
                WHERE n.is_deleted = FALSE
                  AND n.status = 'published'
                  AND n.tenant_id = ANY(:tenant_ids)
                GROUP BY tag
            )
            SELECT 
                tag,
                node_count,
                total_hits,
                PERCENT_RANK() OVER (ORDER BY total_hits) as heat_score
            FROM tag_hits
            ORDER BY total_hits DESC
            LIMIT :limit
        """))
        
        result = await self.session.execute(stmt, {
            "tenant_ids": self.user_tenant_ids,
            "limit": limit,
        })
        
        tags = []
        for row in result.fetchall():
            tags.append(HeatmapTagData(
                tag=row.tag,
                node_count=row.node_count,
                total_hits=row.total_hits,
                heat_score=float(row.heat_score),
            ))
        
        return HeatmapTagsResponse(period=period, tags=tags)

    async def get_heatmap_by_types(
        self,
        period: str = "7d",
    ) -> HeatmapTypesResponse:
        """Get heatmap data aggregated by node type."""
        days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
        days = days_map.get(period)
        
        date_filter = ""
        if days:
            date_filter = f"AND h.hit_at >= NOW() - INTERVAL '{days} days'"
        
        stmt = text(schema_sql(f"""
            WITH type_hits AS (
                SELECT 
                    n.node_type,
                    COUNT(DISTINCT n.id) as node_count,
                    COALESCE(SUM(stats.total_hits), 0) as total_hits
                FROM {{schema}}.knowledge_nodes n
                LEFT JOIN (
                    SELECT node_id, COUNT(*) as total_hits
                    FROM {{schema}}.knowledge_hits h
                    WHERE 1=1 {date_filter}
                    GROUP BY node_id
                ) stats ON n.id = stats.node_id
                WHERE n.is_deleted = FALSE
                  AND n.status = 'published'
                  AND n.tenant_id = ANY(:tenant_ids)
                GROUP BY n.node_type
            )
            SELECT 
                node_type,
                node_count,
                total_hits,
                PERCENT_RANK() OVER (ORDER BY total_hits) as heat_score
            FROM type_hits
            ORDER BY total_hits DESC
        """))
        
        result = await self.session.execute(stmt, {"tenant_ids": self.user_tenant_ids})
        
        types = []
        for row in result.fetchall():
            types.append(HeatmapTypeData(
                node_type=row.node_type,
                node_count=row.node_count,
                total_hits=row.total_hits,
                heat_score=float(row.heat_score),
            ))
        
        return HeatmapTypesResponse(period=period, types=types)
