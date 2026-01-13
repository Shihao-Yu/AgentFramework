"""
Knowledge item API routes.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_embedding_client, get_current_user
from app.clients.embedding_client import EmbeddingClient
from app.services.knowledge_service import KnowledgeService
from app.services.variant_service import VariantService
from app.services.relationship_service import RelationshipService
from app.services.version_service import VersionService
from app.schemas.knowledge import (
    KnowledgeListParams,
    KnowledgeItemCreate,
    KnowledgeItemUpdate,
    KnowledgeItemResponse,
    KnowledgeItemDetailResponse,
    VariantCreate,
    VariantResponse,
    RelationshipCreate,
    RelationshipResponse,
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryTreeResponse,
    VersionResponse,
)
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.models.enums import KnowledgeType, KnowledgeStatus, Visibility


router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ==================== Knowledge Items CRUD ====================

@router.get("", response_model=PaginatedResponse[KnowledgeItemResponse])
async def list_knowledge_items(
    knowledge_type: Optional[KnowledgeType] = None,
    status: Optional[KnowledgeStatus] = None,
    visibility: Optional[Visibility] = None,
    tags: Optional[List[str]] = Query(None),
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """List knowledge items with filtering and pagination."""
    
    params = KnowledgeListParams(
        knowledge_type=knowledge_type,
        status=status,
        visibility=visibility,
        tags=tags,
        category_id=category_id,
        search=search,
        page=page,
        limit=limit,
    )
    
    service = KnowledgeService(session, embedding_client)
    return await service.list_items(params)


@router.get("/{item_id}", response_model=KnowledgeItemDetailResponse)
async def get_knowledge_item(
    item_id: int,
    include_variants: bool = Query(True),
    include_relationships: bool = Query(True),
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """Get a single knowledge item with optional variants and relationships."""
    
    service = KnowledgeService(session, embedding_client)
    item = await service.get_item(item_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge item {item_id} not found"
        )
    
    response = KnowledgeItemDetailResponse.model_validate(item)
    
    # Include variants if requested
    if include_variants:
        variant_service = VariantService(session, embedding_client)
        variants = await variant_service.list_variants(item_id)
        response.variants = [VariantResponse.model_validate(v) for v in variants]
        response.variants_count = len(variants)
    
    # Include relationships if requested
    if include_relationships:
        rel_service = RelationshipService(session)
        relationships = await rel_service.list_relationships(item_id)
        response.related_items = relationships
        response.relationships_count = len(relationships)
    
    return response


@router.post("", response_model=KnowledgeItemResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_item(
    data: KnowledgeItemCreate,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: str = Depends(get_current_user),
):
    """Create a new knowledge item."""
    
    service = KnowledgeService(session, embedding_client)
    item = await service.create_item(data, created_by=current_user)
    return KnowledgeItemResponse.model_validate(item)


@router.put("/{item_id}", response_model=KnowledgeItemResponse)
async def update_knowledge_item(
    item_id: int,
    data: KnowledgeItemUpdate,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: str = Depends(get_current_user),
):
    """Update an existing knowledge item."""
    
    service = KnowledgeService(session, embedding_client)
    item = await service.update_item(item_id, data, updated_by=current_user)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge item {item_id} not found"
        )
    
    return KnowledgeItemResponse.model_validate(item)


@router.delete("/{item_id}", response_model=SuccessResponse)
async def delete_knowledge_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: str = Depends(get_current_user),
):
    """Soft delete a knowledge item."""
    
    service = KnowledgeService(session, embedding_client)
    success = await service.delete_item(item_id, deleted_by=current_user)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge item {item_id} not found"
        )
    
    return SuccessResponse(success=True, message=f"Knowledge item {item_id} deleted")


# ==================== Variants ====================

@router.get("/{item_id}/variants", response_model=List[VariantResponse])
async def list_variants(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """List all variants for a knowledge item."""
    
    # Verify item exists
    knowledge_service = KnowledgeService(session, embedding_client)
    item = await knowledge_service.get_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge item {item_id} not found"
        )
    
    service = VariantService(session, embedding_client)
    variants = await service.list_variants(item_id)
    return [VariantResponse.model_validate(v) for v in variants]


@router.post("/{item_id}/variants", response_model=VariantResponse, status_code=status.HTTP_201_CREATED)
async def create_variant(
    item_id: int,
    data: VariantCreate,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: str = Depends(get_current_user),
):
    """Add a new variant to a knowledge item."""
    
    # Verify item exists
    knowledge_service = KnowledgeService(session, embedding_client)
    item = await knowledge_service.get_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge item {item_id} not found"
        )
    
    service = VariantService(session, embedding_client)
    variant = await service.create_variant(item_id, data, created_by=current_user)
    return VariantResponse.model_validate(variant)


@router.delete("/{item_id}/variants/{variant_id}", response_model=SuccessResponse)
async def delete_variant(
    item_id: int,
    variant_id: int,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """Delete a variant."""
    
    service = VariantService(session, embedding_client)
    success = await service.delete_variant(variant_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant {variant_id} not found"
        )
    
    return SuccessResponse(success=True, message=f"Variant {variant_id} deleted")


# ==================== Relationships ====================

@router.get("/{item_id}/relationships", response_model=List[RelationshipResponse])
async def list_relationships(
    item_id: int,
    include_reverse: bool = Query(True),
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """List all relationships for a knowledge item."""
    
    # Verify item exists
    knowledge_service = KnowledgeService(session, embedding_client)
    item = await knowledge_service.get_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge item {item_id} not found"
        )
    
    service = RelationshipService(session)
    relationships = await service.get_related_items(item_id)
    return relationships


@router.post("/{item_id}/relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    item_id: int,
    data: RelationshipCreate,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: str = Depends(get_current_user),
):
    """Create a relationship from this item to another."""
    
    # Verify source item exists
    knowledge_service = KnowledgeService(session, embedding_client)
    item = await knowledge_service.get_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge item {item_id} not found"
        )
    
    # Verify target item exists
    target = await knowledge_service.get_item(data.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target knowledge item {data.target_id} not found"
        )
    
    service = RelationshipService(session)
    relationship = await service.create_relationship(
        source_id=item_id,
        data=data,
        created_by=current_user
    )
    return RelationshipResponse.model_validate(relationship)


@router.delete("/{item_id}/relationships/{relationship_id}", response_model=SuccessResponse)
async def delete_relationship(
    item_id: int,
    relationship_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a relationship."""
    
    service = RelationshipService(session)
    success = await service.delete_relationship(relationship_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Relationship {relationship_id} not found"
        )
    
    return SuccessResponse(success=True, message=f"Relationship {relationship_id} deleted")


# ==================== Versions ====================

@router.get("/{item_id}/versions", response_model=List[VersionResponse])
async def list_versions(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """List all versions (history) for a knowledge item."""
    
    # Verify item exists
    knowledge_service = KnowledgeService(session, embedding_client)
    item = await knowledge_service.get_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge item {item_id} not found"
        )
    
    service = VersionService(session)
    versions = await service.list_versions(item_id)
    return versions


@router.post("/{item_id}/versions/{version_number}/rollback", response_model=KnowledgeItemResponse)
async def rollback_to_version(
    item_id: int,
    version_number: int,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: str = Depends(get_current_user),
):
    """Rollback a knowledge item to a previous version."""
    
    service = VersionService(session)
    
    try:
        item = await service.rollback_to_version(item_id, version_number, rolled_back_by=current_user)
        return KnowledgeItemResponse.model_validate(item)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
