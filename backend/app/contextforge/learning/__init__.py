"""
Learning layer for ContextForge - training, promotion, and feedback.

This module provides:
- TrainingManager: Collect, validate, and store Q&A training examples
- ExamplePromoter: Manage example lifecycle (draft -> validated -> promoted)
- FeedbackCollector: Collect and process user feedback on generated queries
"""

from .trainer import (
    TrainingManager,
    ExampleStatus,
    ValidationResult,
    ValidationReport,
    TrainingStats,
)
from .promotion import (
    ExamplePromoter,
    PromotionCriteria,
    PromotionResult,
)
from .feedback import (
    FeedbackCollector,
    QueryFeedback,
    FeedbackType,
    FeedbackCategory,
    FeedbackStats,
)

__all__ = [
    # Trainer
    "TrainingManager",
    "ExampleStatus",
    "ValidationResult",
    "ValidationReport",
    "TrainingStats",
    # Promotion
    "ExamplePromoter",
    "PromotionCriteria",
    "PromotionResult",
    # Feedback
    "FeedbackCollector",
    "QueryFeedback",
    "FeedbackType",
    "FeedbackCategory",
    "FeedbackStats",
]
