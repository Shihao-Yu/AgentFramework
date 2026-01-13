"""
Example Promotion Logic for ContextForge.

Handles the promotion of validated examples to production status
and manages example quality thresholds.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .trainer import ExampleStatus, TrainingManager

logger = logging.getLogger(__name__)


@dataclass
class PromotionCriteria:
    """Criteria for promoting examples to production."""
    min_quality_score: float = 80.0
    min_validations: int = 1
    require_manual_review: bool = False
    max_auto_promotions_per_day: int = 100


@dataclass
class PromotionResult:
    """Result of a promotion attempt."""
    success: bool
    example_id: str
    old_status: str
    new_status: str
    reason: Optional[str] = None


class ExamplePromoter:
    """
    Manages the promotion of examples from validated to production.
    
    Promotion flow:
    1. Example created (draft)
    2. Example validated (validated)
    3. Example promoted to production (promoted)
    """
    
    def __init__(
        self,
        tenant_id: str = "default",
        criteria: Optional[PromotionCriteria] = None,
    ):
        self.tenant_id = tenant_id
        self.criteria = criteria or PromotionCriteria()
        self._trainer = TrainingManager(tenant_id=tenant_id)
    
    async def promote_example(
        self,
        session: AsyncSession,
        example_id: str,
        force: bool = False,
    ) -> PromotionResult:
        """
        Promote a single example to production status.
        
        Args:
            session: Database session
            example_id: Example to promote
            force: Skip quality checks
            
        Returns:
            PromotionResult with outcome
        """
        from sqlalchemy import select
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == self.tenant_id,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
            KnowledgeNode.source_reference == example_id,
        )
        
        result = await session.execute(stmt)
        node = result.scalar_one_or_none()
        
        if not node:
            return PromotionResult(
                success=False,
                example_id=example_id,
                old_status="unknown",
                new_status="unknown",
                reason="Example not found",
            )
        
        content = node.content
        old_status = content.get("status", ExampleStatus.DRAFT.value)
        
        if old_status == ExampleStatus.PROMOTED.value:
            return PromotionResult(
                success=False,
                example_id=example_id,
                old_status=old_status,
                new_status=old_status,
                reason="Already promoted",
            )
        
        if not force:
            quality_score = content.get("quality_score", 0.0)
            if quality_score < self.criteria.min_quality_score:
                return PromotionResult(
                    success=False,
                    example_id=example_id,
                    old_status=old_status,
                    new_status=old_status,
                    reason=f"Quality score {quality_score} below threshold {self.criteria.min_quality_score}",
                )
            
            if old_status not in [ExampleStatus.VALIDATED.value, ExampleStatus.PENDING_REVIEW.value]:
                return PromotionResult(
                    success=False,
                    example_id=example_id,
                    old_status=old_status,
                    new_status=old_status,
                    reason=f"Cannot promote from status {old_status}",
                )
        
        content["status"] = ExampleStatus.PROMOTED.value
        content["promoted_at"] = datetime.utcnow().isoformat()
        node.content = content
        node.updated_at = datetime.utcnow()
        
        await session.flush()
        
        logger.info(f"Promoted example {example_id}")
        
        return PromotionResult(
            success=True,
            example_id=example_id,
            old_status=old_status,
            new_status=ExampleStatus.PROMOTED.value,
        )
    
    async def demote_example(
        self,
        session: AsyncSession,
        example_id: str,
        reason: str = "Manual demotion",
    ) -> PromotionResult:
        """
        Demote an example back to validated status.
        
        Args:
            session: Database session
            example_id: Example to demote
            reason: Reason for demotion
            
        Returns:
            PromotionResult with outcome
        """
        from sqlalchemy import select
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == self.tenant_id,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
            KnowledgeNode.source_reference == example_id,
        )
        
        result = await session.execute(stmt)
        node = result.scalar_one_or_none()
        
        if not node:
            return PromotionResult(
                success=False,
                example_id=example_id,
                old_status="unknown",
                new_status="unknown",
                reason="Example not found",
            )
        
        content = node.content
        old_status = content.get("status", ExampleStatus.DRAFT.value)
        
        content["status"] = ExampleStatus.VALIDATED.value
        content["demoted_at"] = datetime.utcnow().isoformat()
        content["demotion_reason"] = reason
        node.content = content
        node.updated_at = datetime.utcnow()
        
        await session.flush()
        
        logger.info(f"Demoted example {example_id}: {reason}")
        
        return PromotionResult(
            success=True,
            example_id=example_id,
            old_status=old_status,
            new_status=ExampleStatus.VALIDATED.value,
            reason=reason,
        )
    
    async def auto_promote_batch(
        self,
        session: AsyncSession,
        dataset_name: str,
        limit: Optional[int] = None,
    ) -> List[PromotionResult]:
        """
        Automatically promote examples that meet criteria.
        
        Args:
            session: Database session
            dataset_name: Dataset to process
            limit: Max examples to promote
            
        Returns:
            List of PromotionResult for each attempt
        """
        from sqlalchemy import select
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        
        max_promotions = limit or self.criteria.max_auto_promotions_per_day
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == self.tenant_id,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
            KnowledgeNode.dataset_name == dataset_name,
        ).limit(max_promotions * 2)
        
        result = await session.execute(stmt)
        nodes = result.scalars().all()
        
        results = []
        promoted_count = 0
        
        for node in nodes:
            if promoted_count >= max_promotions:
                break
            
            content = node.content
            status = content.get("status", ExampleStatus.DRAFT.value)
            
            if status != ExampleStatus.VALIDATED.value:
                continue
            
            quality_score = content.get("quality_score", 0.0)
            if quality_score < self.criteria.min_quality_score:
                continue
            
            example_id = node.source_reference
            promotion_result = await self.promote_example(session, example_id)
            results.append(promotion_result)
            
            if promotion_result.success:
                promoted_count += 1
        
        return results
    
    async def get_promotion_candidates(
        self,
        session: AsyncSession,
        dataset_name: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get examples that are candidates for promotion.
        
        Returns validated examples above the quality threshold.
        """
        from sqlalchemy import select
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == self.tenant_id,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
            KnowledgeNode.dataset_name == dataset_name,
        ).limit(limit * 2)
        
        result = await session.execute(stmt)
        nodes = result.scalars().all()
        
        candidates = []
        for node in nodes:
            content = node.content
            status = content.get("status", ExampleStatus.DRAFT.value)
            
            if status != ExampleStatus.VALIDATED.value:
                continue
            
            quality_score = content.get("quality_score", 0.0)
            if quality_score < self.criteria.min_quality_score:
                continue
            
            candidates.append({
                "id": node.source_reference,
                "question": content.get("question", "")[:50],
                "quality_score": quality_score,
                "status": status,
            })
            
            if len(candidates) >= limit:
                break
        
        return candidates
