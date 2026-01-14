"""
User Feedback Collection for ContextForge.

Collects and processes user feedback on generated queries.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of user feedback."""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    CORRECTION = "correction"
    COMMENT = "comment"
    BUG_REPORT = "bug_report"


class FeedbackCategory(str, Enum):
    """Categories for feedback classification."""
    CORRECT = "correct"
    INCORRECT_QUERY = "incorrect_query"
    MISSING_FIELDS = "missing_fields"
    WRONG_FIELDS = "wrong_fields"
    SYNTAX_ERROR = "syntax_error"
    PERFORMANCE = "performance"
    OTHER = "other"


@dataclass
class QueryFeedback:
    """Feedback on a generated query."""
    id: str
    dataset_name: str
    question: str
    generated_query: str
    
    feedback_type: FeedbackType
    category: Optional[FeedbackCategory] = None
    
    corrected_query: Optional[str] = None
    comment: Optional[str] = None
    
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackStats:
    """Statistics about collected feedback."""
    total_feedback: int = 0
    positive_count: int = 0
    negative_count: int = 0
    corrections_count: int = 0
    positive_rate: float = 0.0


class FeedbackCollector:
    """
    Collects and manages user feedback on generated queries.
    
    Uses feedback to:
    - Identify queries that need improvement
    - Create new training examples from corrections
    - Track quality metrics over time
    """
    
    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id
    
    async def submit_feedback(
        self,
        session: AsyncSession,
        feedback: QueryFeedback,
        auto_create_example: bool = True,
    ) -> str:
        """
        Submit user feedback on a generated query.
        
        Args:
            session: Database session
            feedback: Feedback to submit
            auto_create_example: Auto-create training example from corrections
            
        Returns:
            Feedback ID
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType, KnowledgeStatus, Visibility
        
        if not feedback.id:
            feedback.id = f"fb_{self.tenant_id}_{int(datetime.utcnow().timestamp())}"
        
        content = {
            "_type": "query_feedback",
            "dataset_name": feedback.dataset_name,
            "question": feedback.question,
            "generated_query": feedback.generated_query,
            "feedback_type": feedback.feedback_type.value,
            "category": feedback.category.value if feedback.category else None,
            "corrected_query": feedback.corrected_query,
            "comment": feedback.comment,
            "user_id": feedback.user_id,
            "session_id": feedback.session_id,
            "metadata": feedback.metadata,
        }
        
        node = KnowledgeNode(
            tenant_id=self.tenant_id,
            node_type=NodeType.EXAMPLE,
            title=f"Feedback: {feedback.question[:50]}...",
            summary=feedback.comment,
            content=content,
            tags=["feedback", feedback.feedback_type.value],
            dataset_name=feedback.dataset_name,
            source_reference=feedback.id,
            visibility=Visibility.INTERNAL,
            status=KnowledgeStatus.DRAFT,
            source="feedback",
        )
        
        session.add(node)
        await session.flush()
        
        if auto_create_example and feedback.corrected_query:
            await self._create_example_from_correction(session, feedback)
        
        logger.info(f"Collected feedback {feedback.id} ({feedback.feedback_type.value})")
        return feedback.id
    
    async def _create_example_from_correction(
        self,
        session: AsyncSession,
        feedback: QueryFeedback,
    ) -> None:
        """Create a training example from a user correction."""
        from .trainer import TrainingManager
        
        trainer = TrainingManager(tenant_id=self.tenant_id)
        
        await trainer.add_example(
            session,
            dataset_name=feedback.dataset_name,
            question=feedback.question,
            query=feedback.corrected_query,
            explanation=f"User correction: {feedback.comment or 'No comment provided'}",
            source="feedback_correction",
            auto_validate=True,
        )
    
    async def get_feedback(
        self,
        session: AsyncSession,
        dataset_name: Optional[str] = None,
        feedback_type: Optional[FeedbackType] = None,
        limit: int = 50,
    ) -> List[QueryFeedback]:
        """
        Get collected feedback with optional filtering.
        
        Args:
            session: Database session
            dataset_name: Filter by dataset
            feedback_type: Filter by type
            limit: Max results
            
        Returns:
            List of QueryFeedback objects
        """
        from sqlalchemy import select
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == self.tenant_id,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
            KnowledgeNode.source == "feedback",
        ).limit(limit)
        
        if dataset_name:
            stmt = stmt.where(KnowledgeNode.dataset_name == dataset_name)
        
        if feedback_type:
            stmt = stmt.where(KnowledgeNode.tags.contains([feedback_type.value]))
        
        result = await session.execute(stmt)
        nodes = result.scalars().all()
        
        feedbacks = []
        for node in nodes:
            content = node.content
            if content.get("_type") != "query_feedback":
                continue
            
            feedbacks.append(QueryFeedback(
                id=node.source_reference or str(node.id),
                dataset_name=content.get("dataset_name", ""),
                question=content.get("question", ""),
                generated_query=content.get("generated_query", ""),
                feedback_type=FeedbackType(content.get("feedback_type", "thumbs_up")),
                category=FeedbackCategory(content["category"]) if content.get("category") else None,
                corrected_query=content.get("corrected_query"),
                comment=content.get("comment"),
                user_id=content.get("user_id"),
                session_id=content.get("session_id"),
                created_at=node.created_at or datetime.utcnow(),
                metadata=content.get("metadata", {}),
            ))
        
        return feedbacks
    
    async def get_stats(
        self,
        session: AsyncSession,
        dataset_name: Optional[str] = None,
    ) -> FeedbackStats:
        """
        Get feedback statistics.
        
        Args:
            session: Database session
            dataset_name: Optional dataset filter
            
        Returns:
            FeedbackStats with counts and rates
        """
        feedbacks = await self.get_feedback(session, dataset_name=dataset_name, limit=1000)
        
        total = len(feedbacks)
        positive = sum(1 for f in feedbacks if f.feedback_type == FeedbackType.THUMBS_UP)
        negative = sum(1 for f in feedbacks if f.feedback_type == FeedbackType.THUMBS_DOWN)
        corrections = sum(1 for f in feedbacks if f.feedback_type == FeedbackType.CORRECTION)
        
        positive_rate = positive / total if total > 0 else 0.0
        
        return FeedbackStats(
            total_feedback=total,
            positive_count=positive,
            negative_count=negative,
            corrections_count=corrections,
            positive_rate=positive_rate,
        )
    
    async def get_negative_feedback(
        self,
        session: AsyncSession,
        dataset_name: str,
        limit: int = 20,
    ) -> List[QueryFeedback]:
        """
        Get negative feedback for analysis.
        
        Returns thumbs down and correction feedback for improvement.
        """
        all_feedback = await self.get_feedback(session, dataset_name=dataset_name, limit=limit * 2)
        
        negative = [
            f for f in all_feedback
            if f.feedback_type in [FeedbackType.THUMBS_DOWN, FeedbackType.CORRECTION, FeedbackType.BUG_REPORT]
        ]
        
        return negative[:limit]
