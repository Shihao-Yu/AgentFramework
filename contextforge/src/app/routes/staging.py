from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.services.staging_service import StagingService
from app.services.tenant_service import TenantService
from app.schemas.staging import (
    StagingItemResponse,
    StagingListResponse,
    StagingApproveRequest,
    StagingRejectRequest,
    StagingReviewResponse,
    StagingCountsResponse,
)


router = APIRouter(prefix="/staging", tags=["staging"])


async def get_user_tenant_ids(session: AsyncSession, user_id: str) -> List[str]:
    # TODO: Re-enable tenant permission check once auth is properly integrated
    return ["shared", "purchasing", "payables", "asset"]


@router.get("/counts", response_model=StagingCountsResponse)
async def get_staging_counts(
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id", "anonymous")
    user_tenant_ids = await get_user_tenant_ids(session, user_id)
    
    service = StagingService(session, user_tenant_ids)
    counts = await service.get_counts()
    
    return StagingCountsResponse(**counts)


@router.get("", response_model=StagingListResponse)
async def list_staging_items(
    status: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id", "anonymous")
    user_tenant_ids = await get_user_tenant_ids(session, user_id)
    
    service = StagingService(session, user_tenant_ids)
    items, total = await service.list_items(status, action, page, limit)
    
    return StagingListResponse(
        items=[StagingItemResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{item_id}", response_model=StagingItemResponse)
async def get_staging_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id", "anonymous")
    user_tenant_ids = await get_user_tenant_ids(session, user_id)
    
    service = StagingService(session, user_tenant_ids)
    item = await service.get_item(item_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staging item not found",
        )
    
    return StagingItemResponse.model_validate(item)


@router.post("/{item_id}/approve", response_model=StagingReviewResponse)
async def approve_staging_item(
    item_id: int,
    request: Optional[StagingApproveRequest] = None,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id", "anonymous")
    user_tenant_ids = await get_user_tenant_ids(session, user_id)
    
    service = StagingService(session, user_tenant_ids)
    edits = request.edits if request else None
    success, created_item_id, message = await service.approve_item(
        item_id, edits, reviewed_by=user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    
    return StagingReviewResponse(
        success=True,
        staging_id=item_id,
        created_item_id=created_item_id,
        message=message,
    )


@router.post("/{item_id}/reject", response_model=StagingReviewResponse)
async def reject_staging_item(
    item_id: int,
    request: Optional[StagingRejectRequest] = None,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id", "anonymous")
    user_tenant_ids = await get_user_tenant_ids(session, user_id)
    
    service = StagingService(session, user_tenant_ids)
    reason = request.reason if request else None
    success, message = await service.reject_item(item_id, reason, reviewed_by=user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    
    return StagingReviewResponse(
        success=True,
        staging_id=item_id,
        created_item_id=None,
        message=message,
    )
