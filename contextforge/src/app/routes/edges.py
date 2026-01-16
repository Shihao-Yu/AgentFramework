"""
Knowledge Verse edge API routes.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.services.edge_service import EdgeService
from app.services.tenant_service import TenantService
from app.schemas.edges import (
    EdgeCreate,
    EdgeBulkCreate,
    EdgeUpdate,
    EdgeResponse,
    EdgeListParams,
    EdgeListResponse,
)
from app.schemas.common import SuccessResponse
from app.models.enums import EdgeType


router = APIRouter(prefix="/edges", tags=["edges"])


async def get_user_tenant_ids(
    session: AsyncSession,
    user_id: str,
) -> List[str]:
    # TODO: Re-enable tenant permission check once auth is properly integrated
    return ["shared", "purchasing", "payables", "asset"]


@router.get("", response_model=EdgeListResponse)
async def list_edges(
    node_id: Optional[int] = None,
    edge_types: Optional[List[EdgeType]] = Query(None),
    include_auto_generated: bool = Query(True),
    direction: Optional[str] = Query(None, pattern="^(incoming|outgoing|both)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    params = EdgeListParams(
        node_id=node_id,
        edge_types=edge_types,
        include_auto_generated=include_auto_generated,
        direction=direction,
        page=page,
        limit=limit,
    )
    
    service = EdgeService(session)
    edges, total = await service.list_edges(params, user_tenant_ids)
    
    return EdgeListResponse(
        edges=edges,
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{edge_id}", response_model=EdgeResponse)
async def get_edge(
    edge_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    service = EdgeService(session)
    edge = await service.get_edge(edge_id, user_tenant_ids)
    
    if not edge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Edge {edge_id} not found"
        )
    
    return edge


@router.post("", response_model=EdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_edge(
    data: EdgeCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    service = EdgeService(session)
    try:
        edge = await service.create_edge(data, user_tenant_ids, created_by=email)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    
    if not edge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create edge: nodes not found or no access"
        )
    
    return await service.get_edge(edge.id, user_tenant_ids)


@router.post("/bulk", response_model=List[EdgeResponse], status_code=status.HTTP_201_CREATED)
async def create_edges_bulk(
    data: EdgeBulkCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    service = EdgeService(session)
    edges = await service.create_edges_bulk(data.edges, user_tenant_ids, created_by=email)
    
    responses = []
    for edge in edges:
        edge_response = await service.get_edge(edge.id, user_tenant_ids)
        if edge_response:
            responses.append(edge_response)
    
    return responses


@router.put("/{edge_id}", response_model=EdgeResponse)
async def update_edge(
    edge_id: int,
    data: EdgeUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    service = EdgeService(session)
    edge = await service.update_edge(edge_id, data, user_tenant_ids)
    
    if not edge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Edge {edge_id} not found or no access"
        )
    
    return await service.get_edge(edge.id, user_tenant_ids)


@router.delete("/{edge_id}", response_model=SuccessResponse)
async def delete_edge(
    edge_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    service = EdgeService(session)
    success = await service.delete_edge(edge_id, user_tenant_ids)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Edge {edge_id} not found or no access"
        )
    
    return SuccessResponse(success=True, message=f"Edge {edge_id} deleted")
