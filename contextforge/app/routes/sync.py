"""
Graph sync API routes.

Admin endpoints for managing graph synchronization and implicit edge generation.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_embedding_client, get_current_user
from app.clients.embedding_client import EmbeddingClient
from app.services.graph_sync_service import GraphSyncService
from app.services.tenant_service import TenantService


router = APIRouter(prefix="/sync", tags=["sync"])


class SyncStatusResponse(BaseModel):
    pending_events: int
    last_processed: Optional[str]
    auto_generated_edges: dict


class ProcessEventsResponse(BaseModel):
    processed: int
    node_created: int
    node_updated: int
    node_deleted: int
    edge_created: int
    edge_deleted: int
    errors: int


class GenerateEdgesResponse(BaseModel):
    edges_created: int
    edge_type: str


async def get_user_tenant_ids(
    session: AsyncSession,
    user_id: str,
) -> List[str]:
    tenant_service = TenantService(session)
    tenants = await tenant_service.get_user_tenants(user_id)
    if not tenants:
        tenants = ["default", "shared"]
    else:
        if "shared" not in tenants:
            tenants.append("shared")
    return tenants


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    """Get current graph sync status."""
    service = GraphSyncService(session)
    status = await service.get_sync_status()
    return SyncStatusResponse(**status)


@router.post("/process", response_model=ProcessEventsResponse)
async def process_events(
    batch_size: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    """Process pending graph events."""
    service = GraphSyncService(session)
    stats = await service.process_pending_events(batch_size)
    return ProcessEventsResponse(**stats)


@router.post("/generate/shared-tags", response_model=GenerateEdgesResponse)
async def generate_shared_tag_edges(
    min_shared_tags: int = Query(2, ge=1, le=10),
    batch_size: int = Query(1000, ge=1, le=10000),
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    """Generate SHARED_TAG edges between nodes with common tags."""
    user_tenant_ids = await get_user_tenant_ids(session, current_user)
    
    service = GraphSyncService(session)
    created = await service.generate_shared_tag_edges(
        tenant_ids=user_tenant_ids,
        min_shared_tags=min_shared_tags,
        batch_size=batch_size,
    )
    
    return GenerateEdgesResponse(edges_created=created, edge_type="shared_tag")


@router.post("/generate/similar", response_model=GenerateEdgesResponse)
async def generate_similar_edges(
    similarity_threshold: float = Query(0.85, ge=0.5, le=0.99),
    batch_size: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: str = Depends(get_current_user),
):
    """Generate SIMILAR edges between nodes with high embedding similarity."""
    user_tenant_ids = await get_user_tenant_ids(session, current_user)
    
    service = GraphSyncService(session, embedding_client)
    created = await service.generate_similar_edges(
        tenant_ids=user_tenant_ids,
        similarity_threshold=similarity_threshold,
        batch_size=batch_size,
    )
    
    return GenerateEdgesResponse(edges_created=created, edge_type="similar")


@router.post("/generate/all", response_model=dict)
async def generate_all_implicit_edges(
    min_shared_tags: int = Query(2, ge=1, le=10),
    similarity_threshold: float = Query(0.85, ge=0.5, le=0.99),
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: str = Depends(get_current_user),
):
    """Generate all implicit edges (SHARED_TAG and SIMILAR)."""
    user_tenant_ids = await get_user_tenant_ids(session, current_user)
    
    service = GraphSyncService(session, embedding_client)
    
    shared_tag_count = await service.generate_shared_tag_edges(
        tenant_ids=user_tenant_ids,
        min_shared_tags=min_shared_tags,
    )
    
    similar_count = await service.generate_similar_edges(
        tenant_ids=user_tenant_ids,
        similarity_threshold=similarity_threshold,
    )
    
    return {
        "shared_tag_edges_created": shared_tag_count,
        "similar_edges_created": similar_count,
        "total_edges_created": shared_tag_count + similar_count,
    }


@router.delete("/events/cleanup")
async def cleanup_old_events(
    days_to_keep: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    """Delete processed events older than specified days."""
    service = GraphSyncService(session)
    deleted = await service.cleanup_old_events(days_to_keep)
    
    return {
        "events_deleted": deleted,
        "days_kept": days_to_keep,
    }
