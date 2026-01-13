"""
Knowledge Verse tenant API routes.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.services.tenant_service import TenantService
from app.schemas.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantListResponse,
    UserTenantAccessCreate,
    UserTenantAccessUpdate,
    UserTenantAccessResponse,
    UserTenantsResponse,
)
from app.schemas.common import SuccessResponse
from app.models.enums import TenantRole


router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("", response_model=TenantListResponse)
async def list_tenants(
    include_inactive: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    service = TenantService(session)
    
    user_tenants = await service.get_user_tenants(current_user)
    if not user_tenants:
        user_tenants = None
    
    tenants = await service.list_tenants(
        user_tenant_ids=user_tenants,
        include_inactive=include_inactive,
    )
    
    return TenantListResponse(tenants=tenants, total=len(tenants))


@router.get("/me", response_model=UserTenantsResponse)
async def get_my_tenants(
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    service = TenantService(session)
    access_list = await service.get_user_tenant_access(current_user)
    
    return UserTenantsResponse(user_id=current_user, tenants=access_list)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    service = TenantService(session)
    
    has_access = await service.check_user_access(current_user, tenant_id)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No access to tenant {tenant_id}"
        )
    
    tenant = await service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )
    
    node_count = await service._get_tenant_node_count(tenant_id)
    user_count = await service._get_tenant_user_count(tenant_id)
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        description=tenant.description,
        settings=tenant.settings or {},
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        node_count=node_count,
        user_count=user_count,
    )


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    service = TenantService(session)
    
    existing = await service.get_tenant(data.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant {data.id} already exists"
        )
    
    tenant = await service.create_tenant(data)
    
    await service.grant_tenant_access(
        UserTenantAccessCreate(
            user_id=current_user,
            tenant_id=tenant.id,
            role=TenantRole.ADMIN,
        ),
        granted_by=current_user,
    )
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        description=tenant.description,
        settings=tenant.settings or {},
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        node_count=0,
        user_count=1,
    )


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    data: TenantUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    service = TenantService(session)
    
    has_access = await service.check_user_access(current_user, tenant_id, TenantRole.ADMIN)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin access required for tenant {tenant_id}"
        )
    
    tenant = await service.update_tenant(tenant_id, data)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )
    
    node_count = await service._get_tenant_node_count(tenant_id)
    user_count = await service._get_tenant_user_count(tenant_id)
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        description=tenant.description,
        settings=tenant.settings or {},
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        node_count=node_count,
        user_count=user_count,
    )


@router.delete("/{tenant_id}", response_model=SuccessResponse)
async def delete_tenant(
    tenant_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    service = TenantService(session)
    
    has_access = await service.check_user_access(current_user, tenant_id, TenantRole.ADMIN)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin access required for tenant {tenant_id}"
        )
    
    success = await service.delete_tenant(tenant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete tenant {tenant_id} (may be protected or not found)"
        )
    
    return SuccessResponse(success=True, message=f"Tenant {tenant_id} deactivated")


@router.post("/{tenant_id}/access", response_model=UserTenantAccessResponse, status_code=status.HTTP_201_CREATED)
async def grant_access(
    tenant_id: str,
    data: UserTenantAccessCreate,
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    if data.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant ID in path and body must match"
        )
    
    service = TenantService(session)
    
    has_access = await service.check_user_access(current_user, tenant_id, TenantRole.ADMIN)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin access required for tenant {tenant_id}"
        )
    
    access = await service.grant_tenant_access(data, granted_by=current_user)
    if not access:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot grant access (tenant not found or user already has access)"
        )
    
    tenant = await service.get_tenant(tenant_id)
    
    return UserTenantAccessResponse(
        user_id=access.user_id,
        tenant_id=access.tenant_id,
        role=access.role,
        granted_at=access.granted_at,
        granted_by=access.granted_by,
        tenant_name=tenant.name if tenant else None,
    )


@router.put("/{tenant_id}/access/{user_id}", response_model=UserTenantAccessResponse)
async def update_access(
    tenant_id: str,
    user_id: str,
    data: UserTenantAccessUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    service = TenantService(session)
    
    has_access = await service.check_user_access(current_user, tenant_id, TenantRole.ADMIN)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin access required for tenant {tenant_id}"
        )
    
    access = await service.update_tenant_access(user_id, tenant_id, data)
    if not access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Access not found for user {user_id} on tenant {tenant_id}"
        )
    
    tenant = await service.get_tenant(tenant_id)
    
    return UserTenantAccessResponse(
        user_id=access.user_id,
        tenant_id=access.tenant_id,
        role=access.role,
        granted_at=access.granted_at,
        granted_by=access.granted_by,
        tenant_name=tenant.name if tenant else None,
    )


@router.delete("/{tenant_id}/access/{user_id}", response_model=SuccessResponse)
async def revoke_access(
    tenant_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
):
    service = TenantService(session)
    
    has_access = await service.check_user_access(current_user, tenant_id, TenantRole.ADMIN)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin access required for tenant {tenant_id}"
        )
    
    success = await service.revoke_tenant_access(user_id, tenant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Access not found for user {user_id} on tenant {tenant_id}"
        )
    
    return SuccessResponse(success=True, message=f"Access revoked for user {user_id}")
