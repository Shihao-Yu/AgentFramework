from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_embedding_client, get_current_user
from app.clients.embedding_client import EmbeddingClient
from app.services.llm_context_service import LLMContextService
from app.services.metrics_service import MetricsService, HitRecord
from app.schemas.llm_context import LLMContextRequest, LLMContextResponse


router = APIRouter(prefix="/llm-context", tags=["llm-context"])


async def get_user_tenant_ids(
    session: AsyncSession,
    user_id: str,
) -> List[str]:
    return ["shared", "purchasing", "payables", "asset"]


@router.post("", response_model=LLMContextResponse)
async def get_llm_context(
    request: LLMContextRequest,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Get LLM-optimized hierarchical context for AI agents.
    
    Returns pre-formatted context ready for prompt injection, with structured
    JSON for programmatic access if needed.
    
    **Use cases:**
    - `include_knowledge=true`: Get FAQ, playbook, permissions, concepts
    - `include_schema=true`: Get schema fields and examples for query generation
    - Both can be combined in a single request
    
    **Response structure:**
    - `context`: Pre-formatted string ready to inject into LLM prompt
    - `knowledge`: Hierarchical knowledge grouped by topic (if requested)
    - `schema_context`: Hierarchical schema grouped by concept (if requested)
    - `stats`: Retrieval statistics
    """
    email = current_user["email"]
    user_tenant_ids = await get_user_tenant_ids(session, email)

    if not request.tenant_ids:
        request.tenant_ids = user_tenant_ids
    else:
        allowed_tenants = [t for t in request.tenant_ids if t in user_tenant_ids]
        if not allowed_tenants:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to requested tenants"
            )
        request.tenant_ids = allowed_tenants

    service = LLMContextService(session, embedding_client)
    response = await service.get_llm_context(request)

    all_hits: List[HitRecord] = []
    
    if response.knowledge:
        for group in response.knowledge.groups:
            for faq in group.faqs:
                all_hits.append(HitRecord(
                    node_id=faq.id,
                    similarity_score=faq.score,
                    retrieval_method="hybrid",
                ))
            for pb in group.playbooks:
                all_hits.append(HitRecord(
                    node_id=pb.id,
                    similarity_score=pb.score,
                    retrieval_method="hybrid",
                ))
            for perm in group.permissions:
                all_hits.append(HitRecord(
                    node_id=perm.id,
                    similarity_score=perm.score,
                    retrieval_method="hybrid",
                ))
            for concept in group.concepts:
                all_hits.append(HitRecord(
                    node_id=concept.id,
                    similarity_score=concept.score,
                    retrieval_method="hybrid",
                ))

    if all_hits:
        username = "default"
        metrics_service = MetricsService(session, user_tenant_ids)
        await metrics_service.record_hits_batch(all_hits, query_text=request.query, username=username)

    return response
