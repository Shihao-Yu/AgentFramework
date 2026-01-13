"""Tests for ContextForge learning module."""
import pytest
from datetime import datetime

from app.contextforge.learning import (
    TrainingManager,
    ExampleStatus,
    ValidationResult,
    ValidationReport,
    TrainingStats,
    ExamplePromoter,
    PromotionCriteria,
    PromotionResult,
    FeedbackCollector,
    QueryFeedback,
    FeedbackType,
    FeedbackCategory,
    FeedbackStats,
)
from app.contextforge.schema import ExampleSpec


class TestExampleStatus:
    def test_status_values(self):
        assert ExampleStatus.DRAFT.value == "draft"
        assert ExampleStatus.PENDING_REVIEW.value == "pending_review"
        assert ExampleStatus.VALIDATED.value == "validated"
        assert ExampleStatus.REJECTED.value == "rejected"
        assert ExampleStatus.PROMOTED.value == "promoted"


class TestValidationResult:
    def test_result_values(self):
        assert ValidationResult.VALID.value == "valid"
        assert ValidationResult.INVALID_QUERY.value == "invalid_query"
        assert ValidationResult.DUPLICATE.value == "duplicate"


class TestValidationReport:
    def test_is_valid_true(self):
        report = ValidationReport(result=ValidationResult.VALID, score=95.0)
        assert report.is_valid is True
    
    def test_is_valid_false(self):
        report = ValidationReport(
            result=ValidationResult.INVALID_QUERY,
            issues=["Query too short"],
            score=50.0,
        )
        assert report.is_valid is False
    
    def test_default_values(self):
        report = ValidationReport(result=ValidationResult.VALID)
        assert report.issues == []
        assert report.suggestions == []
        assert report.score == 0.0


class TestTrainingStats:
    def test_default_values(self):
        stats = TrainingStats()
        assert stats.total_examples == 0
        assert stats.validated_count == 0
        assert stats.avg_quality_score == 0.0


class TestPromotionCriteria:
    def test_default_values(self):
        criteria = PromotionCriteria()
        assert criteria.min_quality_score == 80.0
        assert criteria.min_validations == 1
        assert criteria.require_manual_review is False
        assert criteria.max_auto_promotions_per_day == 100
    
    def test_custom_values(self):
        criteria = PromotionCriteria(
            min_quality_score=90.0,
            require_manual_review=True,
        )
        assert criteria.min_quality_score == 90.0
        assert criteria.require_manual_review is True


class TestPromotionResult:
    def test_successful_promotion(self):
        result = PromotionResult(
            success=True,
            example_id="ex_123",
            old_status="validated",
            new_status="promoted",
        )
        assert result.success is True
        assert result.reason is None
    
    def test_failed_promotion(self):
        result = PromotionResult(
            success=False,
            example_id="ex_123",
            old_status="draft",
            new_status="draft",
            reason="Quality score below threshold",
        )
        assert result.success is False
        assert "Quality score" in result.reason


class TestFeedbackType:
    def test_feedback_types(self):
        assert FeedbackType.THUMBS_UP.value == "thumbs_up"
        assert FeedbackType.THUMBS_DOWN.value == "thumbs_down"
        assert FeedbackType.CORRECTION.value == "correction"


class TestFeedbackCategory:
    def test_categories(self):
        assert FeedbackCategory.CORRECT.value == "correct"
        assert FeedbackCategory.INCORRECT_QUERY.value == "incorrect_query"
        assert FeedbackCategory.SYNTAX_ERROR.value == "syntax_error"


class TestQueryFeedback:
    def test_create_feedback(self):
        feedback = QueryFeedback(
            id="fb_123",
            dataset_name="orders",
            question="Show me pending orders",
            generated_query="SELECT * FROM orders WHERE status = 'pending'",
            feedback_type=FeedbackType.THUMBS_UP,
        )
        assert feedback.id == "fb_123"
        assert feedback.feedback_type == FeedbackType.THUMBS_UP
        assert feedback.corrected_query is None
    
    def test_correction_feedback(self):
        feedback = QueryFeedback(
            id="fb_456",
            dataset_name="orders",
            question="Show me pending orders",
            generated_query="SELECT * FROM orders",
            feedback_type=FeedbackType.CORRECTION,
            category=FeedbackCategory.MISSING_FIELDS,
            corrected_query="SELECT * FROM orders WHERE status = 'pending'",
            comment="Missing status filter",
        )
        assert feedback.feedback_type == FeedbackType.CORRECTION
        assert feedback.category == FeedbackCategory.MISSING_FIELDS
        assert feedback.corrected_query is not None


class TestFeedbackStats:
    def test_default_values(self):
        stats = FeedbackStats()
        assert stats.total_feedback == 0
        assert stats.positive_rate == 0.0
    
    def test_with_values(self):
        stats = FeedbackStats(
            total_feedback=100,
            positive_count=75,
            negative_count=20,
            corrections_count=5,
            positive_rate=0.75,
        )
        assert stats.positive_rate == 0.75


class TestTrainingManager:
    def test_init(self):
        manager = TrainingManager(tenant_id="test_tenant")
        assert manager.tenant_id == "test_tenant"
    
    def test_default_tenant(self):
        manager = TrainingManager()
        assert manager.tenant_id == "default"


class TestExamplePromoter:
    def test_init_default_criteria(self):
        promoter = ExamplePromoter(tenant_id="test")
        assert promoter.tenant_id == "test"
        assert promoter.criteria.min_quality_score == 80.0
    
    def test_init_custom_criteria(self):
        criteria = PromotionCriteria(min_quality_score=95.0)
        promoter = ExamplePromoter(tenant_id="test", criteria=criteria)
        assert promoter.criteria.min_quality_score == 95.0


class TestFeedbackCollector:
    def test_init(self):
        collector = FeedbackCollector(tenant_id="test")
        assert collector.tenant_id == "test"
