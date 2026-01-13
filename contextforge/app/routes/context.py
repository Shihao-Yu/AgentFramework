"""
Agent context API routes.

Primary API for AI agents to retrieve structured context from Knowledge Verse.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_embedding_client, get_current_user
from app.clients.embedding_client import EmbeddingClient
from app.services.context_service import ContextService
from app.services.tenant_service import TenantService
from app.schemas.context import ContextRequest, ContextResponse


router = APIRouter(prefix="/context", tags=["context"])


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


@router.post("", response_model=ContextResponse)
async def get_context(
    request: ContextRequest,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: str = Depends(get_current_user),
):
    """
    Get structured context for AI agent.
    
    This is the primary API for agents to retrieve relevant knowledge.
    
    The response includes:
    - **entry_points**: Direct search matches (FAQs, playbooks, etc.)
    - **context**: Related nodes found via graph expansion
    - **entities**: Business entities related to the query
    - **stats**: Search and expansion statistics
    """
    user_tenant_ids = await get_user_tenant_ids(session, current_user)
    
    allowed_tenants = [t for t in request.tenant_ids if t in user_tenant_ids]
    if not allowed_tenants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to requested tenants"
        )
    
    request.tenant_ids = allowed_tenants
    
    service = ContextService(session, embedding_client)
    return await service.get_context(request)
