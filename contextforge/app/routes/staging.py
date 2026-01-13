"""
Staging queue API routes.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_embedding_client, get_current_user
from app.clients.embedding_client import EmbeddingClient
from app.services.staging_service import StagingService
from app.schemas.staging import (
    StagingListParams,
    StagingItemResponse,
    StagingListResponse,
    StagingCountsResponse,
    StagingReviewRequest,
    StagingReviewResponse,
    StagingEditRequest,
)
from app.schemas.knowledge import KnowledgeItemResponse
from app.models.enums import StagingStatus, StagingAction


router = APIRouter(prefix="/staging", tags=["staging"])


@router.get("", response_model=StagingListResponse)
async def list_staging_items(
    status: Optional[StagingStatus] = StagingStatus.PENDING,
    action: Optional[StagingAction] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """List staging items with filtering."""
    
    params = StagingListParams(
        status=status,
        action=action,
        page=page,
        limit=limit,
    )
    
    service = StagingService(session, embedding_client)
    return await service.list_items(params)


@router.get("/counts", response_model=StagingCountsResponse)
async def get_staging_counts(
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """Get counts of pending items by action type."""
    
    service = StagingService(session, embedding_client)
    return await service.get_counts()


@router.get("/{staging_id}", response_model=StagingItemResponse)
async def get_staging_item(
    staging_id: int,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """Get a single staging item."""
    
    service = StagingService(session, embedding_client)
    item = await service.get_item(staging_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staging item {staging_id} not found"
        )
    
    return StagingItemResponse.model_validate(item)


@router.get("/{staging_id}/merge-target", response_model=Optional[KnowledgeItemResponse])
async def get_merge_target(
    staging_id: int,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """
    Get the knowledge item that would be merged with this staging item.
    
    Returns null if staging item is action=NEW or if target doesn't exist.
    """
    
    service = StagingService(session, embedding_client)
    
    # Verify staging item exists
    staging = await service.get_item(staging_id)
    if not staging:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staging item {staging_id} not found"
        )
    
    target = await service.get_merge_target(staging_id)
    if not target:
        return None
    
    return KnowledgeItemResponse.model_validate(target)


@router.patch("/{staging_id}", response_model=StagingItemResponse)
async def edit_staging_item(
    staging_id: int,
    data: StagingEditRequest,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """
    Edit a staging item before review.
    
    Only pending items can be edited.
    """
    
    service = StagingService(session, embedding_client)
    item = await service.get_item(staging_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staging item {staging_id} not found"
        )
    
    if item.status != StagingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending items can be edited"
        )
    
    # Apply edits
    if data.title is not None:
        item.title = data.title
    if data.content is not None:
        item.content = {**item.content, **data.content}
    if data.tags is not None:
        item.tags = data.tags
    
    await session.commit()
    await session.refresh(item)
    
    return StagingItemResponse.model_validate(item)


@router.post("/{staging_id}/approve", response_model=StagingReviewResponse)
async def approve_staging_item(
    staging_id: int,
    data: Optional[StagingReviewRequest] = None,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: str = Depends(get_current_user),
):
    """
    Approve a staging item.
    
    - NEW: Creates a new knowledge item
    - MERGE: Merges into existing knowledge item
    - ADD_VARIANT: Adds variant to existing item
    
    Optionally include edits to apply before approval.
    """
    
    service = StagingService(session, embedding_client)
    
    try:
        edits = data.edits if data else None
        result = await service.approve(staging_id, current_user, edits)
        return StagingReviewResponse(
            success=True,
            staging_id=staging_id,
            created_item_id=result.get("created_item_id"),
            message="Staging item approved successfully"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{staging_id}/reject", response_model=StagingReviewResponse)
async def reject_staging_item(
    staging_id: int,
    data: Optional[StagingReviewRequest] = None,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: str = Depends(get_current_user),
):
    """
    Reject a staging item.
    
    Optionally include a reason for rejection.
    """
    
    service = StagingService(session, embedding_client)
    
    try:
        reason = data.reason if data else None
        await service.reject(staging_id, current_user, reason)
        return StagingReviewResponse(
            success=True,
            staging_id=staging_id,
            message="Staging item rejected"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
