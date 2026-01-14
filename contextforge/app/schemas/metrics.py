"""
Metrics and analytics request/response schemas.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.models.enums import NodeType


class MetricsSummaryResponse(BaseModel):
    total_items: int
    published_items: int
    draft_items: int
    archived_items: int
    total_hits: int
    total_sessions: int
    avg_daily_sessions: float
    never_accessed_count: int


class TypeDistribution(BaseModel):
    type: str
    count: int
    percentage: float


class StatusDistribution(BaseModel):
    status: str
    count: int
    percentage: float


class KnowledgeHitStats(BaseModel):
    id: int
    knowledge_type: str
    title: str
    tags: List[str]
    total_hits: int
    unique_sessions: int
    days_with_hits: int
    last_hit_at: Optional[datetime] = None
    avg_similarity: Optional[float] = None
    primary_retrieval_method: Optional[str] = None


class TopItemsResponse(BaseModel):
    """Response for top performing items."""
    
    items: List[KnowledgeHitStats]
    period_days: int


# ==================== Daily Trends ====================

class DailyHitStats(BaseModel):
    """Daily hit statistics."""
    
    date: str  # ISO date
    total_hits: int
    unique_sessions: int
    by_type: Optional[Dict[str, int]] = None


class DailyTrendResponse(BaseModel):
    """Response for daily trend data."""
    
    data: List[DailyHitStats]
    period_days: int


# ==================== Tag Stats ====================

class TagStats(BaseModel):
    """Statistics for a tag."""
    
    tag: str
    count: int
    total_hits: int


class TagStatsResponse(BaseModel):
    """Response for tag statistics."""
    
    tags: List[TagStats]
    total_tags: int


# ==================== Item-Level Stats ====================

class ItemStatsResponse(BaseModel):
    """Detailed stats for a single item."""
    
    item_id: int
    title: str
    total_hits: int
    unique_sessions: int
    days_with_hits: int
    first_hit: Optional[datetime] = None
    last_hit: Optional[datetime] = None
    avg_similarity: Optional[float] = None
    queries: List[str]  # Recent queries that hit this item
    hit_trend: List[DailyHitStats]  # Daily hits for this item
