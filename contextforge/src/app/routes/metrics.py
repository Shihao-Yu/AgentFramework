from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.services.metrics_service import MetricsService
from app.services.tenant_service import TenantService
from app.schemas.metrics import (
    MetricsSummaryResponse,
    TopItemsResponse,
    DailyTrendResponse,
    TagStatsResponse,
    ItemStatsResponse,
)


router = APIRouter(prefix="/metrics", tags=["metrics"])


async def get_user_tenant_ids(session: AsyncSession, user_id: str) -> List[str]:
    # TODO: Re-enable tenant permission check once auth is properly integrated
    return ["shared", "purchasing", "payables", "asset"]


@router.get("/summary", response_model=MetricsSummaryResponse)
async def get_metrics_summary(
    days: int = Query(7, ge=1, le=365, description="Number of days to include in summary"),
    node_types: list[str] = Query(None, description="Filter by node types (e.g., faq, playbook)"),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id", "anonymous")
    user_tenant_ids = await get_user_tenant_ids(session, user_id)
    service = MetricsService(session, user_tenant_ids)
    return await service.get_summary(days, node_types=node_types)


@router.get("/top-items", response_model=TopItemsResponse)
async def get_top_items(
    limit: int = Query(10, ge=1, le=100, description="Number of items to return"),
    days: int = Query(7, ge=1, le=365, description="Number of days to analyze"),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id", "anonymous")
    user_tenant_ids = await get_user_tenant_ids(session, user_id)
    service = MetricsService(session, user_tenant_ids)
    return await service.get_top_items(limit, days)


@router.get("/daily-trend", response_model=DailyTrendResponse)
async def get_daily_trend(
    days: int = Query(7, ge=1, le=365, description="Number of days to analyze"),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id", "anonymous")
    user_tenant_ids = await get_user_tenant_ids(session, user_id)
    service = MetricsService(session, user_tenant_ids)
    return await service.get_daily_trend(days)


@router.get("/tags", response_model=TagStatsResponse)
async def get_tag_stats(
    limit: int = Query(20, ge=1, le=100, description="Number of tags to return"),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id", "anonymous")
    user_tenant_ids = await get_user_tenant_ids(session, user_id)
    service = MetricsService(session, user_tenant_ids)
    return await service.get_tag_stats(limit)


@router.get("/items/{item_id}", response_model=ItemStatsResponse)
async def get_item_stats(
    item_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days for trend data"),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id", "anonymous")
    user_tenant_ids = await get_user_tenant_ids(session, user_id)
    service = MetricsService(session, user_tenant_ids)
    stats = await service.get_node_stats(item_id, days)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge item {item_id} not found"
        )
    
    return stats
