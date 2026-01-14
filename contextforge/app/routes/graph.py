"""
Knowledge Verse graph API routes.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user, get_graph_service
from app.services.graph_service import GraphService
from app.services.tenant_service import TenantService


router = APIRouter(prefix="/graph", tags=["graph"])


class NeighborResponse(BaseModel):
    id: int
    depth: int
    tenant_id: str
    node_type: str
    title: str
    tags: List[str]
    dataset_name: Optional[str] = None
    field_path: Optional[str] = None


class PathResponse(BaseModel):
    paths: List[List[int]]


class GraphStatsResponse(BaseModel):
    node_count: int
    edge_count: int
    density: float
    connected_components: int
    avg_degree: float
    orphan_nodes: int
    node_types: Dict[str, int]
    edge_types: Dict[str, int]
    last_sync: Optional[str] = None


class SuggestionResponse(BaseModel):
    id: int
    score: float
    reason: str
    tenant_id: str
    node_type: str
    title: str
    tags: List[str]
    dataset_name: Optional[str] = None


async def get_user_tenant_ids(
    session: AsyncSession,
    user_id: str,
) -> List[str]:
    tenant_service = TenantService(session)
    tenants = await tenant_service.get_user_tenants(user_id)
    if not tenants:
        all_tenants = await tenant_service.list_tenants()
        tenants = [t.id for t in all_tenants]
    if "shared" not in tenants:
        tenants.append("shared")
    return tenants


@router.get("/stats", response_model=GraphStatsResponse)
async def get_graph_stats(
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
    service: GraphService = Depends(get_graph_service),
):
    user_tenant_ids = await get_user_tenant_ids(session, current_user)
    
    stats = await service.get_graph_stats(user_tenant_ids)
    
    return GraphStatsResponse(**stats)


@router.get("/neighbors/{node_id}", response_model=List[NeighborResponse])
async def get_neighbors(
    node_id: int,
    depth: int = Query(1, ge=1, le=3),
    edge_types: Optional[List[str]] = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
    service: GraphService = Depends(get_graph_service),
):
    user_tenant_ids = await get_user_tenant_ids(session, current_user)
    
    neighbors = await service.get_neighbors(
        node_id, user_tenant_ids, depth, edge_types
    )
    
    return [NeighborResponse(**n) for n in neighbors]


@router.get("/paths", response_model=PathResponse)
async def find_paths(
    source_id: int,
    target_id: int,
    max_depth: int = Query(5, ge=1, le=10),
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
    service: GraphService = Depends(get_graph_service),
):
    user_tenant_ids = await get_user_tenant_ids(session, current_user)
    
    paths = await service.find_paths(
        source_id, target_id, user_tenant_ids, max_depth
    )
    
    return PathResponse(paths=paths)


@router.get("/component/{node_id}", response_model=List[int])
async def get_connected_component(
    node_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
    service: GraphService = Depends(get_graph_service),
):
    user_tenant_ids = await get_user_tenant_ids(session, current_user)
    
    component = await service.get_connected_component(node_id, user_tenant_ids)
    
    return component


@router.get("/orphans", response_model=List[NeighborResponse])
async def find_orphan_nodes(
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
    service: GraphService = Depends(get_graph_service),
):
    user_tenant_ids = await get_user_tenant_ids(session, current_user)
    
    orphans = await service.find_orphan_nodes(user_tenant_ids)
    
    return [NeighborResponse(depth=0, **o) for o in orphans]


@router.get("/suggestions/{node_id}", response_model=List[SuggestionResponse])
async def suggest_connections(
    node_id: int,
    limit: int = Query(5, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
    service: GraphService = Depends(get_graph_service),
):
    user_tenant_ids = await get_user_tenant_ids(session, current_user)
    
    suggestions = await service.suggest_connections(
        node_id, user_tenant_ids, limit
    )
    
    return [SuggestionResponse(**s) for s in suggestions]


@router.post("/reload")
async def reload_graph(
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
    service: GraphService = Depends(get_graph_service),
):
    user_tenant_ids = await get_user_tenant_ids(session, current_user)
    
    service.clear_cache()
    await service.load_graph(user_tenant_ids, force_reload=True)
    stats = await service.get_graph_stats(user_tenant_ids)
    
    return {
        "status": "reloaded",
        "stats": stats,
    }
