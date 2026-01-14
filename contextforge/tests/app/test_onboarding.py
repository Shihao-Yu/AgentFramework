"""
Tests for the onboarding pipelines.

Tests cover:
- Extraction model validation
- Pipeline extraction methods
- OnboardingService orchestration
- API endpoint integration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from app.onboarding.models import (
    FAQExtraction,
    PlaybookExtraction,
    PlaybookStep,
    ConceptExtraction,
    FeaturePermissionExtraction,
    PermissionRule,
    EntityExtraction,
)
from app.onboarding import (
    FAQPipeline,
    PlaybookPipeline,
    ConceptPipeline,
    FeaturePermissionPipeline,
    EntityPipeline,
)
from app.schemas.onboarding import ContentItem, OnboardRequest, OnboardResponse


class TestFAQExtraction:
    """Test FAQExtraction model validation."""

    def test_valid_faq_extraction(self):
        """Should accept valid FAQ extraction data."""
        extraction = FAQExtraction(
            question="How do I reset my password?",
            answer="Go to Settings > Security > Reset Password.",
            tags=["password", "security", "account"],
            confidence=0.95,
        )
        assert extraction.question == "How do I reset my password?"
        assert extraction.confidence == 0.95

    def test_faq_extraction_default_tags(self):
        """Tags should default to empty list."""
        extraction = FAQExtraction(
            question="Test question?",
            answer="Test answer.",
            confidence=0.8,
        )
        assert extraction.tags == []

    def test_faq_extraction_confidence_bounds(self):
        """Confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            FAQExtraction(
                question="Test?",
                answer="Answer.",
                confidence=1.5,  # Invalid: > 1
            )

        with pytest.raises(ValidationError):
            FAQExtraction(
                question="Test?",
                answer="Answer.",
                confidence=-0.1,  # Invalid: < 0
            )


class TestPlaybookExtraction:
    """Test PlaybookExtraction model validation."""

    def test_valid_playbook_extraction(self):
        """Should accept valid playbook extraction data."""
        extraction = PlaybookExtraction(
            title="How to Process a Refund",
            description="Step-by-step guide for processing customer refunds.",
            prerequisites=["Access to billing system", "Manager approval for > $100"],
            steps=[
                PlaybookStep(order=1, action="Open the billing portal"),
                PlaybookStep(order=2, action="Search for the customer"),
                PlaybookStep(order=3, action="Click 'Process Refund'", details="Enter reason code"),
            ],
            tags=["refund", "billing", "customer-service"],
            confidence=0.9,
        )
        assert extraction.title == "How to Process a Refund"
        assert len(extraction.steps) == 3
        assert extraction.steps[0].order == 1

    def test_playbook_step_details_optional(self):
        """PlaybookStep details should be optional."""
        step = PlaybookStep(order=1, action="Do something")
        assert step.details is None

    def test_playbook_prerequisites_optional(self):
        """Prerequisites should default to empty list."""
        extraction = PlaybookExtraction(
            title="Simple Guide",
            description="A simple procedure.",
            steps=[PlaybookStep(order=1, action="Do it")],
            confidence=0.8,
        )
        assert extraction.prerequisites == []


class TestConceptExtraction:
    """Test ConceptExtraction model validation."""

    def test_valid_concept_extraction(self):
        """Should accept valid concept extraction data."""
        extraction = ConceptExtraction(
            term="Purchase Order",
            definition="A formal document issued by a buyer to a seller.",
            aliases=["PO", "P.O."],
            examples=["PO-2024-001", "Standard purchase order for office supplies"],
            tags=["procurement", "purchasing"],
            confidence=0.85,
        )
        assert extraction.term == "Purchase Order"
        assert "PO" in extraction.aliases

    def test_concept_aliases_optional(self):
        """Aliases should default to empty list."""
        extraction = ConceptExtraction(
            term="Widget",
            definition="A generic term for a small component.",
            confidence=0.7,
        )
        assert extraction.aliases == []
        assert extraction.examples == []


class TestFeaturePermissionExtraction:
    """Test FeaturePermissionExtraction model validation."""

    def test_valid_permission_extraction(self):
        """Should accept valid permission extraction data."""
        extraction = FeaturePermissionExtraction(
            feature="Create Purchase Order",
            rules=[
                PermissionRule(
                    role="Buyer",
                    action="Create",
                    condition="Up to $5,000",
                ),
                PermissionRule(
                    role="Senior Buyer",
                    action="Create",
                    condition="Up to $50,000",
                ),
            ],
            conditions=["Requires valid vendor selection"],
            tags=["procurement", "authorization"],
            confidence=0.92,
        )
        assert extraction.feature == "Create Purchase Order"
        assert len(extraction.rules) == 2

    def test_permission_rule_condition_optional(self):
        """PermissionRule condition should be optional."""
        rule = PermissionRule(role="Admin", action="Delete")
        assert rule.condition is None


class TestEntityExtraction:
    """Test EntityExtraction model validation."""

    def test_valid_entity_extraction(self):
        """Should accept valid entity extraction data."""
        extraction = EntityExtraction(
            name="Acme Corporation",
            entity_type="Vendor",
            attributes={
                "vendor_id": "V-12345",
                "status": "Active",
                "payment_terms": "Net 30",
            },
            tags=["vendor", "supplier"],
            confidence=0.88,
        )
        assert extraction.name == "Acme Corporation"
        assert extraction.entity_type == "Vendor"
        assert extraction.attributes["vendor_id"] == "V-12345"

    def test_entity_attributes_optional(self):
        """Attributes should default to empty dict."""
        extraction = EntityExtraction(
            name="Unknown Entity",
            entity_type="Other",
            confidence=0.5,
        )
        assert extraction.attributes == {}


class TestFAQPipeline:
    """Test FAQPipeline extraction."""

    def test_pipeline_attributes(self):
        """Pipeline should have correct node_type and extraction_model."""
        mock_client = MagicMock()
        pipeline = FAQPipeline(mock_client)
        
        assert pipeline.node_type == "FAQ"
        assert pipeline.extraction_model == FAQExtraction

    def test_prompt_name_attribute(self):
        """Pipeline should have prompt_name for Langfuse lookup."""
        mock_client = MagicMock()
        pipeline = FAQPipeline(mock_client)
        
        assert pipeline.prompt_name == "onboarding_faq_extraction"

    @patch("app.onboarding.base.get_langfuse_client")
    def test_system_prompt_loads_from_langfuse(self, mock_get_langfuse):
        """System prompt should load from Langfuse client."""
        mock_langfuse = MagicMock()
        mock_langfuse.get_prompt_template.return_value = "Test FAQ prompt"
        mock_get_langfuse.return_value = mock_langfuse
        
        mock_client = MagicMock()
        pipeline = FAQPipeline(mock_client)
        
        prompt = pipeline.get_system_prompt()
        assert prompt == "Test FAQ prompt"
        mock_langfuse.get_prompt_template.assert_called_once_with("onboarding_faq_extraction")

    def test_to_node_content(self):
        """Should convert extraction to node content dict."""
        mock_client = MagicMock()
        pipeline = FAQPipeline(mock_client)
        
        extraction = FAQExtraction(
            question="How do I do X?",
            answer="You do Y.",
            tags=["test"],
            confidence=0.9,
        )
        
        content = pipeline.to_node_content(extraction)
        assert content == {
            "question": "How do I do X?",
            "answer": "You do Y.",
        }

    def test_get_title(self):
        """Title should be the question."""
        mock_client = MagicMock()
        pipeline = FAQPipeline(mock_client)
        
        extraction = FAQExtraction(
            question="What is the meaning of life?",
            answer="42",
            confidence=0.9,
        )
        
        assert pipeline.get_title(extraction) == "What is the meaning of life?"

    def test_get_tags(self):
        """Should return tags from extraction."""
        mock_client = MagicMock()
        pipeline = FAQPipeline(mock_client)
        
        extraction = FAQExtraction(
            question="Test?",
            answer="Test.",
            tags=["a", "b", "c"],
            confidence=0.9,
        )
        
        assert pipeline.get_tags(extraction) == ["a", "b", "c"]


class TestPlaybookPipeline:
    """Test PlaybookPipeline extraction."""

    def test_pipeline_attributes(self):
        """Pipeline should have correct node_type and extraction_model."""
        mock_client = MagicMock()
        pipeline = PlaybookPipeline(mock_client)
        
        assert pipeline.node_type == "PLAYBOOK"
        assert pipeline.extraction_model == PlaybookExtraction

    def test_to_node_content(self):
        """Should convert extraction to node content dict with steps."""
        mock_client = MagicMock()
        pipeline = PlaybookPipeline(mock_client)
        
        extraction = PlaybookExtraction(
            title="Test Procedure",
            description="A test procedure.",
            prerequisites=["Prereq 1"],
            steps=[
                PlaybookStep(order=1, action="Step 1", details="Details 1"),
                PlaybookStep(order=2, action="Step 2"),
            ],
            tags=["test"],
            confidence=0.8,
        )
        
        content = pipeline.to_node_content(extraction)
        assert content["description"] == "A test procedure."
        assert content["prerequisites"] == ["Prereq 1"]
        assert len(content["steps"]) == 2
        assert content["steps"][0]["order"] == 1
        assert content["steps"][0]["action"] == "Step 1"
        assert content["steps"][0]["details"] == "Details 1"

    def test_get_title(self):
        """Title should be the playbook title."""
        mock_client = MagicMock()
        pipeline = PlaybookPipeline(mock_client)
        
        extraction = PlaybookExtraction(
            title="My Procedure",
            description="Desc",
            steps=[PlaybookStep(order=1, action="Do it")],
            confidence=0.9,
        )
        
        assert pipeline.get_title(extraction) == "My Procedure"


class TestConceptPipeline:
    """Test ConceptPipeline extraction."""

    def test_pipeline_attributes(self):
        """Pipeline should have correct node_type and extraction_model."""
        mock_client = MagicMock()
        pipeline = ConceptPipeline(mock_client)
        
        assert pipeline.node_type == "CONCEPT"
        assert pipeline.extraction_model == ConceptExtraction

    def test_to_node_content(self):
        """Should convert extraction to node content dict."""
        mock_client = MagicMock()
        pipeline = ConceptPipeline(mock_client)
        
        extraction = ConceptExtraction(
            term="Test Term",
            definition="A definition.",
            aliases=["TT", "T.T."],
            examples=["Example 1"],
            tags=["glossary"],
            confidence=0.85,
        )
        
        content = pipeline.to_node_content(extraction)
        assert content["term"] == "Test Term"
        assert content["definition"] == "A definition."
        assert content["aliases"] == ["TT", "T.T."]
        assert content["examples"] == ["Example 1"]

    def test_get_title(self):
        """Title should be the term."""
        mock_client = MagicMock()
        pipeline = ConceptPipeline(mock_client)
        
        extraction = ConceptExtraction(
            term="Important Concept",
            definition="Very important.",
            confidence=0.9,
        )
        
        assert pipeline.get_title(extraction) == "Important Concept"


class TestFeaturePermissionPipeline:
    """Test FeaturePermissionPipeline extraction."""

    def test_pipeline_attributes(self):
        """Pipeline should have correct node_type and extraction_model."""
        mock_client = MagicMock()
        pipeline = FeaturePermissionPipeline(mock_client)
        
        assert pipeline.node_type == "FEATURE_PERMISSION"
        assert pipeline.extraction_model == FeaturePermissionExtraction

    def test_to_node_content(self):
        """Should convert extraction to node content dict with rules."""
        mock_client = MagicMock()
        pipeline = FeaturePermissionPipeline(mock_client)
        
        extraction = FeaturePermissionExtraction(
            feature="Approve Invoice",
            rules=[
                PermissionRule(role="Manager", action="Approve", condition="< $10,000"),
            ],
            conditions=["Must be in same department"],
            tags=["approval"],
            confidence=0.9,
        )
        
        content = pipeline.to_node_content(extraction)
        assert content["feature"] == "Approve Invoice"
        assert len(content["rules"]) == 1
        assert content["rules"][0]["role"] == "Manager"
        assert content["conditions"] == ["Must be in same department"]

    def test_get_title(self):
        """Title should be the feature name with Permissions suffix."""
        mock_client = MagicMock()
        pipeline = FeaturePermissionPipeline(mock_client)
        
        extraction = FeaturePermissionExtraction(
            feature="Delete Records",
            rules=[PermissionRule(role="Admin", action="Delete")],
            confidence=0.9,
        )
        
        assert pipeline.get_title(extraction) == "Delete Records Permissions"


class TestEntityPipeline:
    """Test EntityPipeline extraction."""

    def test_pipeline_attributes(self):
        """Pipeline should have correct node_type and extraction_model."""
        mock_client = MagicMock()
        pipeline = EntityPipeline(mock_client)
        
        assert pipeline.node_type == "ENTITY"
        assert pipeline.extraction_model == EntityExtraction

    def test_to_node_content(self):
        """Should convert extraction to node content dict."""
        mock_client = MagicMock()
        pipeline = EntityPipeline(mock_client)
        
        extraction = EntityExtraction(
            name="Test Entity",
            entity_type="Customer",
            attributes={"id": "C-001", "tier": "Gold"},
            tags=["customer"],
            confidence=0.88,
        )
        
        content = pipeline.to_node_content(extraction)
        assert content["name"] == "Test Entity"
        assert content["entity_type"] == "Customer"
        assert content["attributes"]["id"] == "C-001"

    def test_get_title(self):
        """Title should be the entity name."""
        mock_client = MagicMock()
        pipeline = EntityPipeline(mock_client)
        
        extraction = EntityExtraction(
            name="Acme Corp",
            entity_type="Vendor",
            confidence=0.9,
        )
        
        assert pipeline.get_title(extraction) == "Acme Corp"

    def test_get_tags_adds_entity_type(self):
        mock_client = MagicMock()
        pipeline = EntityPipeline(mock_client)
        
        extraction = EntityExtraction(
            name="Test",
            entity_type="Product Category",
            tags=["existing-tag"],
            confidence=0.9,
        )
        
        tags = pipeline.get_tags(extraction)
        assert "existing-tag" in tags
        assert "product-category" in tags


class TestOnboardingSchemas:
    """Test API request/response schemas."""

    def test_content_item_validation(self):
        """ContentItem should validate text and node_types."""
        item = ContentItem(
            text="This is a test content with enough characters.",
            node_types=["FAQ", "PLAYBOOK"],
        )
        assert len(item.node_types) == 2

    def test_content_item_requires_min_text_length(self):
        """ContentItem should require minimum text length."""
        with pytest.raises(ValidationError):
            ContentItem(
                text="short",  # Less than 10 chars
                node_types=["FAQ"],
            )

    def test_content_item_requires_at_least_one_node_type(self):
        """ContentItem should require at least one node type."""
        with pytest.raises(ValidationError):
            ContentItem(
                text="This is valid text content.",
                node_types=[],  # Empty list
            )

    def test_onboard_request_validation(self):
        """OnboardRequest should validate items and tenant_id."""
        request = OnboardRequest(
            items=[
                ContentItem(
                    text="Test content here.",
                    node_types=["FAQ"],
                ),
            ],
            tenant_id="test-tenant",
            source_tag="manual-import",
        )
        assert request.tenant_id == "test-tenant"
        assert request.source_tag == "manual-import"

    def test_onboard_request_source_tag_optional(self):
        """source_tag should default to empty string."""
        request = OnboardRequest(
            items=[
                ContentItem(
                    text="Test content here.",
                    node_types=["FAQ"],
                ),
            ],
            tenant_id="test-tenant",
        )
        assert request.source_tag == ""

    def test_onboard_response(self):
        """OnboardResponse should contain created count and staging_ids."""
        response = OnboardResponse(
            created=3,
            staging_ids=[101, 102, 103],
        )
        assert response.created == 3
        assert len(response.staging_ids) == 3
