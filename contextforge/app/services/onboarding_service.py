"""
Onboarding service for extracting and staging knowledge from raw text.

Orchestrates type-specific pipelines and creates staging nodes for review.
"""

import json
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.inference_client import InferenceClient
from app.onboarding import (
    FAQPipeline,
    PlaybookPipeline,
    ConceptPipeline,
    FeaturePermissionPipeline,
    EntityPipeline,
)
from app.schemas.onboarding import ContentItem, OnboardResponse
from app.utils.schema import sql

logger = logging.getLogger(__name__)


# Map node type strings to pipeline classes
PIPELINE_MAP = {
    "FAQ": FAQPipeline,
    "PLAYBOOK": PlaybookPipeline,
    "CONCEPT": ConceptPipeline,
    "FEATURE_PERMISSION": FeaturePermissionPipeline,
    "ENTITY": EntityPipeline,
}


class OnboardingService:
    """
    Service for onboarding raw text content into the knowledge base.

    Extracts structured knowledge using LLM pipelines and creates
    staging nodes for human review.
    """

    def __init__(
        self,
        session: AsyncSession,
        inference_client: InferenceClient,
    ):
        """
        Initialize the onboarding service.

        Args:
            session: Database session for staging node creation.
            inference_client: Client for LLM inference with structured output.
        """
        self.session = session
        self.inference = inference_client

    async def onboard(
        self,
        items: list[ContentItem],
        tenant_id: str,
        source_tag: str = "",
        created_by: Optional[str] = None,
    ) -> OnboardResponse:
        """
        Process content items and create staging nodes.

        For each content item, runs extraction pipelines for each requested
        node type and creates staging nodes for review.

        Args:
            items: List of content items with text and target node types.
            tenant_id: Tenant to create staging nodes under.
            source_tag: Free-form source tag for tracking (e.g., 'confluence-import').
            created_by: User ID creating the staging nodes.

        Returns:
            OnboardResponse with count and IDs of created staging nodes.
        """
        staging_ids: list[int] = []

        for item in items:
            for node_type in item.node_types:
                try:
                    staging_id = await self._extract_and_stage(
                        text=item.text,
                        node_type=node_type,
                        tenant_id=tenant_id,
                        source_tag=source_tag,
                        created_by=created_by,
                    )
                    if staging_id:
                        staging_ids.append(staging_id)
                except Exception as e:
                    # Log but continue processing other items
                    logger.error(
                        f"Failed to extract {node_type} from text: {e}",
                        exc_info=True,
                    )

        return OnboardResponse(
            created=len(staging_ids),
            staging_ids=staging_ids,
        )

    async def _extract_and_stage(
        self,
        text: str,
        node_type: str,
        tenant_id: str,
        source_tag: str,
        created_by: Optional[str],
    ) -> Optional[int]:
        """
        Extract content and create a staging node.

        Args:
            text: Raw text to extract from.
            node_type: Type of node to extract (FAQ, PLAYBOOK, etc.).
            tenant_id: Tenant ID for the staging node.
            source_tag: Source tag for tracking.
            created_by: User ID creating the node.

        Returns:
            Staging node ID if successful, None otherwise.
        """
        pipeline_cls = PIPELINE_MAP.get(node_type)
        if not pipeline_cls:
            logger.warning(f"Unknown node type: {node_type}")
            return None

        # Create pipeline and extract
        pipeline = pipeline_cls(self.inference)
        title, content, tags, confidence = await pipeline.extract(text)

        # Create staging node
        result = await self.session.execute(
            text(sql("""
                INSERT INTO {schema}.staging_nodes (
                    tenant_id, node_type, title, content, tags,
                    status, action, source, confidence, created_by
                ) VALUES (
                    :tenant_id, :node_type, :title, :content::jsonb, :tags,
                    'pending', 'new', :source, :confidence, :created_by
                ) RETURNING id
            """)),
            {
                "tenant_id": tenant_id,
                "node_type": node_type,
                "title": title,
                "content": json.dumps(content),
                "tags": tags,
                "source": source_tag or "onboarding",
                "confidence": confidence,
                "created_by": created_by or "onboarding",
            },
        )

        staging_id = result.scalar_one()
        await self.session.commit()

        logger.info(
            f"Created staging node {staging_id} for {node_type}: {title[:50]}..."
        )

        return staging_id
