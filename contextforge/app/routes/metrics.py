"""
Metrics and analytics API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.metrics_service import MetricsService
from app.schemas.metrics import (
    MetricsSummaryResponse,
    TopItemsResponse,
    DailyTrendResponse,
    TagStatsResponse,
    ItemStatsResponse,
)


router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary", response_model=MetricsSummaryResponse)
async def get_metrics_summary(
    days: int = Query(7, ge=1, le=365, description="Number of days to include in summary"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get overall metrics summary.
    
    Returns:
    - Item counts by status (total, published, draft, archived)
    - Hit statistics for the specified period
    - Session statistics
    - Count of items never accessed
    """
    
    service = MetricsService(session)
    return await service.get_summary(days)


@router.get("/top-items", response_model=TopItemsResponse)
async def get_top_items(
    limit: int = Query(10, ge=1, le=100, description="Number of items to return"),
    days: int = Query(7, ge=1, le=365, description="Number of days to analyze"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get top performing knowledge items by hit count.
    
    Returns items with:
    - Total hits in period
    - Unique sessions
    - Days with hits
    - Average similarity score
    - Primary retrieval method
    """
    
    service = MetricsService(session)
    return await service.get_top_items(limit, days)


@router.get("/daily-trend", response_model=DailyTrendResponse)
async def get_daily_trend(
    days: int = Query(7, ge=1, le=365, description="Number of days to analyze"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get daily hit trend.
    
    Returns daily statistics:
    - Total hits per day
    - Unique sessions per day
    """
    
    service = MetricsService(session)
    return await service.get_daily_trend(days)


@router.get("/tags", response_model=TagStatsResponse)
async def get_tag_stats(
    limit: int = Query(20, ge=1, le=100, description="Number of tags to return"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get tag usage statistics.
    
    Returns for each tag:
    - Count of items with this tag
    - Total hits across items with this tag
    """
    
    service = MetricsService(session)
    return await service.get_tag_stats(limit)


@router.get("/items/{item_id}", response_model=ItemStatsResponse)
async def get_item_stats(
    item_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days for trend data"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get detailed statistics for a single knowledge item.
    
    Returns:
    - Total hits and unique sessions (all time)
    - First and last hit timestamps
    - Average similarity score
    - Recent queries that matched this item
    - Daily hit trend for the specified period
    """
    
    service = MetricsService(session)
    stats = await service.get_item_stats(item_id, days)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge item {item_id} not found"
        )
    
    return stats
