"""
Onboarding API routes.

Endpoints for extracting structured knowledge from raw text
and creating staging nodes for review.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_inference_client, get_current_user
from app.clients.inference_client import InferenceClient
from app.services.onboarding_service import OnboardingService
from app.schemas.onboarding import OnboardRequest, OnboardResponse


router = APIRouter(prefix="/onboard", tags=["onboarding"])


@router.post("", response_model=OnboardResponse)
async def onboard_content(
    request: OnboardRequest,
    session: AsyncSession = Depends(get_session),
    inference_client: InferenceClient = Depends(get_inference_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Extract knowledge from raw text and create staging nodes.

    Accepts one or more content items, each with text and target node types.
    For each content item and node type combination, runs an LLM extraction
    pipeline and creates a staging node for human review.

    All extracted content goes to the staging queue with status='pending'
    and action='new'. Reviewers can then approve or reject items.

    Returns the count and IDs of created staging nodes.
    """
    email = current_user["email"]
    user_tenants = current_user.get("tenant_ids", [])

    if request.tenant_id not in user_tenants and user_tenants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized for tenant: {request.tenant_id}",
        )

    service = OnboardingService(session, inference_client)
    return await service.onboard(
        items=request.items,
        tenant_id=request.tenant_id,
        source_tag=request.source_tag,
        created_by=email,
    )
