"""
Knowledge Verse tenant and access control service.
"""

from datetime import datetime
from typing import List, Optional
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.tenant import Tenant, UserTenantAccess
from app.models.enums import TenantRole
from app.schemas.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    UserTenantAccessCreate,
    UserTenantAccessUpdate,
    UserTenantAccessResponse,
)
from app.utils.schema import sql as schema_sql


class TenantService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def list_tenants(
        self,
        user_tenant_ids: Optional[List[str]] = None,
        include_inactive: bool = False,
    ) -> List[TenantResponse]:
        query = select(Tenant)
        
        if user_tenant_ids:
            query = query.where(Tenant.id.in_(user_tenant_ids))
        
        if not include_inactive:
            query = query.where(Tenant.is_active == True)
        
        query = query.order_by(Tenant.name)
        
        result = await self.session.execute(query)
        tenants = result.scalars().all()
        
        responses = []
        for tenant in tenants:
            node_count = await self._get_tenant_node_count(tenant.id)
            user_count = await self._get_tenant_user_count(tenant.id)
            
            responses.append(TenantResponse(
                id=tenant.id,
                name=tenant.name,
                description=tenant.description,
                settings=tenant.settings or {},
                is_active=tenant.is_active,
                created_at=tenant.created_at,
                updated_at=tenant.updated_at,
                node_count=node_count,
                user_count=user_count,
            ))
        
        return responses
    
    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        query = select(Tenant).where(Tenant.id == tenant_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def create_tenant(self, data: TenantCreate) -> Tenant:
        tenant = Tenant(
            id=data.id,
            name=data.name,
            description=data.description,
            settings=data.settings,
        )
        
        self.session.add(tenant)
        await self.session.commit()
        await self.session.refresh(tenant)
        
        return tenant
    
    async def update_tenant(
        self,
        tenant_id: str,
        data: TenantUpdate,
    ) -> Optional[Tenant]:
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(tenant, field, value)
        
        tenant.updated_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(tenant)
        
        return tenant
    
    async def delete_tenant(self, tenant_id: str) -> bool:
        if tenant_id in ("default", "shared"):
            return False
        
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        tenant.is_active = False
        tenant.updated_at = datetime.utcnow()
        
        await self.session.commit()
        return True
    
    async def get_user_tenants(self, user_id: str) -> List[str]:
        result = await self.session.execute(
            text(schema_sql("""
                SELECT uta.tenant_id 
                FROM {schema}.user_tenant_access uta
                JOIN {schema}.tenants t ON uta.tenant_id = t.id
                WHERE uta.user_id = :user_id AND t.is_active = TRUE
            """)),
            {"user_id": user_id}
        )
        return [row.tenant_id for row in result.fetchall()]
    
    async def get_user_tenant_access(
        self,
        user_id: str,
    ) -> List[UserTenantAccessResponse]:
        result = await self.session.execute(
            text(schema_sql("""
                SELECT uta.user_id, uta.tenant_id, uta.role, uta.granted_at, 
                       uta.granted_by, t.name as tenant_name
                FROM {schema}.user_tenant_access uta
                JOIN {schema}.tenants t ON uta.tenant_id = t.id
                WHERE uta.user_id = :user_id AND t.is_active = TRUE
                ORDER BY t.name
            """)),
            {"user_id": user_id}
        )
        
        return [
            UserTenantAccessResponse(
                user_id=row.user_id,
                tenant_id=row.tenant_id,
                role=TenantRole(row.role),
                granted_at=row.granted_at,
                granted_by=row.granted_by,
                tenant_name=row.tenant_name,
            )
            for row in result.fetchall()
        ]
    
    async def grant_tenant_access(
        self,
        data: UserTenantAccessCreate,
        granted_by: Optional[str] = None,
    ) -> Optional[UserTenantAccess]:
        tenant = await self.get_tenant(data.tenant_id)
        if not tenant or not tenant.is_active:
            return None
        
        existing = await self.session.execute(
            select(UserTenantAccess).where(
                UserTenantAccess.user_id == data.user_id,
                UserTenantAccess.tenant_id == data.tenant_id,
            )
        )
        if existing.scalar_one_or_none():
            return None
        
        access = UserTenantAccess(
            user_id=data.user_id,
            tenant_id=data.tenant_id,
            role=data.role,
            granted_by=granted_by,
        )
        
        self.session.add(access)
        await self.session.commit()
        await self.session.refresh(access)
        
        return access
    
    async def update_tenant_access(
        self,
        user_id: str,
        tenant_id: str,
        data: UserTenantAccessUpdate,
    ) -> Optional[UserTenantAccess]:
        query = select(UserTenantAccess).where(
            UserTenantAccess.user_id == user_id,
            UserTenantAccess.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        access = result.scalar_one_or_none()
        
        if not access:
            return None
        
        access.role = data.role
        
        await self.session.commit()
        await self.session.refresh(access)
        
        return access
    
    async def revoke_tenant_access(
        self,
        user_id: str,
        tenant_id: str,
    ) -> bool:
        query = select(UserTenantAccess).where(
            UserTenantAccess.user_id == user_id,
            UserTenantAccess.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        access = result.scalar_one_or_none()
        
        if not access:
            return False
        
        await self.session.delete(access)
        await self.session.commit()
        
        return True
    
    async def check_user_access(
        self,
        user_id: str,
        tenant_id: str,
        required_role: Optional[TenantRole] = None,
    ) -> bool:
        query = select(UserTenantAccess).where(
            UserTenantAccess.user_id == user_id,
            UserTenantAccess.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        access = result.scalar_one_or_none()
        
        if not access:
            return False
        
        if required_role:
            role_hierarchy = {
                TenantRole.VIEWER: 0,
                TenantRole.EDITOR: 1,
                TenantRole.ADMIN: 2,
            }
            return role_hierarchy.get(access.role, 0) >= role_hierarchy.get(required_role, 0)
        
        return True
    
    async def _get_tenant_node_count(self, tenant_id: str) -> int:
        result = await self.session.execute(
            text(schema_sql("""
                SELECT COUNT(*) FROM {schema}.knowledge_nodes 
                WHERE tenant_id = :tenant_id AND is_deleted = FALSE
            """)),
            {"tenant_id": tenant_id}
        )
        return result.scalar() or 0
    
    async def _get_tenant_user_count(self, tenant_id: str) -> int:
        result = await self.session.execute(
            text(schema_sql("""
                SELECT COUNT(DISTINCT user_id) FROM {schema}.user_tenant_access 
                WHERE tenant_id = :tenant_id
            """)),
            {"tenant_id": tenant_id}
        )
        return result.scalar() or 0
