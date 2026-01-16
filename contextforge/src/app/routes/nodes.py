"""
Knowledge Verse node API routes.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_embedding_client, get_optional_embedding_client, get_current_user
from app.clients.embedding_client import EmbeddingClient
from app.services.node_service import NodeService
from app.services.edge_service import EdgeService
from app.services.tenant_service import TenantService
from app.services.metrics_service import MetricsService, HitRecord
from app.schemas.nodes import (
    NodeListParams,
    NodeCreate,
    NodeUpdate,
    NodeResponse,
    NodeDetailResponse,
    NodeSearchResponse,
    NodeSearchResult,
    NodeVersionResponse,
)
from app.schemas.edges import EdgeListParams
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.models.enums import NodeType, KnowledgeStatus, Visibility


router = APIRouter(prefix="/nodes", tags=["nodes"])


async def get_user_tenant_ids(
    session: AsyncSession,
    user_id: str,
) -> List[str]:
    # TODO: Re-enable tenant permission check once auth is properly integrated
    return ["shared", "purchasing", "payables", "asset"]


@router.get("", response_model=PaginatedResponse[NodeResponse])
async def list_nodes(
    tenant_ids: Optional[List[str]] = Query(None),
    node_types: Optional[List[NodeType]] = Query(None),
    status_filter: Optional[KnowledgeStatus] = Query(None, alias="status"),
    visibility: Optional[Visibility] = None,
    tags: Optional[List[str]] = Query(None),
    dataset_name: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    embedding_client: Optional[EmbeddingClient] = Depends(get_optional_embedding_client),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    params = NodeListParams(
        tenant_ids=tenant_ids,
        node_types=node_types,
        status=status_filter,
        visibility=visibility,
        tags=tags,
        dataset_name=dataset_name,
        search=search,
        page=page,
        limit=limit,
    )
    
    service = NodeService(session, embedding_client)
    return await service.list_nodes(params, user_tenant_ids)


@router.get("/search", response_model=NodeSearchResponse)
async def search_nodes(
    q: str = Query(..., min_length=1),
    node_types: Optional[List[NodeType]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    bm25_weight: float = Query(0.4, ge=0, le=1),
    vector_weight: float = Query(0.6, ge=0, le=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    service = NodeService(session, embedding_client)
    results = await service.hybrid_search(
        query_text=q,
        user_tenant_ids=user_tenant_ids,
        node_types=node_types,
        tags=tags,
        bm25_weight=bm25_weight,
        vector_weight=vector_weight,
        limit=limit,
    )
    
    if results:
        hits = [
            HitRecord(
                node_id=r.node.id,
                similarity_score=r.rrf_score,
                retrieval_method="hybrid",
            )
            for r in results
        ]
        metrics_service = MetricsService(session, user_tenant_ids)
        await metrics_service.record_hits_batch(hits, query_text=q, username=email)
    
    return NodeSearchResponse(
        results=results,
        total=len(results),
        page=1,
        limit=limit,
    )


@router.get("/{node_id}", response_model=NodeDetailResponse)
async def get_node(
    node_id: int,
    include_edges: bool = Query(True),
    session: AsyncSession = Depends(get_session),
    embedding_client: Optional[EmbeddingClient] = Depends(get_optional_embedding_client),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    service = NodeService(session, embedding_client)
    node = await service.get_node(node_id, user_tenant_ids)
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found"
        )
    
    response = NodeDetailResponse.model_validate(node)
    
    if include_edges:
        edge_service = EdgeService(session)
        incoming, outgoing = await edge_service.get_node_edges(
            node_id, user_tenant_ids
        )
        response.incoming_edges = incoming
        response.outgoing_edges = outgoing
        response.edges_count = len(incoming) + len(outgoing)
    
    return response


@router.post("", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node(
    data: NodeCreate,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    service = NodeService(session, embedding_client)
    node = await service.create_node(data, user_tenant_ids, created_by=email)
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No access to tenant {data.tenant_id}"
        )
    
    return NodeResponse.model_validate(node)


@router.put("/{node_id}", response_model=NodeResponse)
async def update_node(
    node_id: int,
    data: NodeUpdate,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    service = NodeService(session, embedding_client)
    node = await service.update_node(node_id, data, user_tenant_ids, updated_by=email)
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found or no access"
        )
    
    return NodeResponse.model_validate(node)


@router.delete("/{node_id}", response_model=SuccessResponse)
async def delete_node(
    node_id: int,
    session: AsyncSession = Depends(get_session),
    embedding_client: Optional[EmbeddingClient] = Depends(get_optional_embedding_client),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    service = NodeService(session, embedding_client)
    success = await service.delete_node(node_id, user_tenant_ids, deleted_by=email)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found or no access"
        )
    
    return SuccessResponse(success=True, message=f"Node {node_id} deleted")


@router.get("/{node_id}/versions", response_model=List[NodeVersionResponse])
async def list_node_versions(
    node_id: int,
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    embedding_client: Optional[EmbeddingClient] = Depends(get_optional_embedding_client),
    current_user: dict = Depends(get_current_user),
):
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)
    
    service = NodeService(session, embedding_client)
    versions = await service.get_node_versions(node_id, user_tenant_ids, limit)
    
    return [NodeVersionResponse(**v) for v in versions]
