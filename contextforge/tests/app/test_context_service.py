"""Tests for ContextService and ContextRequest schema."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.context import ContextRequest, ContextResponse
from app.models.enums import NodeType


class TestContextRequestSchema:

    def test_default_values(self):
        """ContextRequest should have sensible defaults."""
        request = ContextRequest(query="test", tenant_ids=["tenant1"])
        
        assert request.query == "test"
        assert request.tenant_ids == ["tenant1"]
        assert request.entry_types is None
        assert request.entry_limit == 10
        assert request.tags is None
        assert request.search_method == "hybrid"
        assert request.bm25_weight == 0.4
        assert request.vector_weight == 0.6
        assert request.min_score is None
        assert request.expand is True
        assert request.max_depth == 2
        assert request.context_limit == 50
        assert request.include_entities is True
        assert request.include_schemas is False
        assert request.include_examples is False
        assert request.max_tokens is None
        assert request.token_model == "gpt-4"

    def test_search_method_options(self):
        """search_method should accept hybrid, bm25, or vector."""
        for method in ["hybrid", "bm25", "vector"]:
            request = ContextRequest(
                query="test",
                tenant_ids=["tenant1"],
                search_method=method,
            )
            assert request.search_method == method

    def test_bm25_weight_bounds(self):
        """bm25_weight should be between 0.0 and 1.0."""
        request = ContextRequest(
            query="test",
            tenant_ids=["tenant1"],
            bm25_weight=0.0,
        )
        assert request.bm25_weight == 0.0
        
        request = ContextRequest(
            query="test",
            tenant_ids=["tenant1"],
            bm25_weight=1.0,
        )
        assert request.bm25_weight == 1.0

    def test_vector_weight_bounds(self):
        """vector_weight should be between 0.0 and 1.0."""
        request = ContextRequest(
            query="test",
            tenant_ids=["tenant1"],
            vector_weight=0.0,
        )
        assert request.vector_weight == 0.0
        
        request = ContextRequest(
            query="test",
            tenant_ids=["tenant1"],
            vector_weight=1.0,
        )
        assert request.vector_weight == 1.0

    def test_min_score_optional(self):
        """min_score should be optional and bounded."""
        request = ContextRequest(
            query="test",
            tenant_ids=["tenant1"],
            min_score=0.5,
        )
        assert request.min_score == 0.5

    def test_tags_filter(self):
        """tags should accept list of strings."""
        request = ContextRequest(
            query="test",
            tenant_ids=["tenant1"],
            tags=["procurement", "workflow"],
        )
        assert request.tags == ["procurement", "workflow"]

    def test_entry_types_filter(self):
        """entry_types should accept list of NodeType."""
        request = ContextRequest(
            query="test",
            tenant_ids=["tenant1"],
            entry_types=[NodeType.FAQ, NodeType.PLAYBOOK],
        )
        assert request.entry_types == [NodeType.FAQ, NodeType.PLAYBOOK]

    def test_expansion_types_filter(self):
        """expansion_types should accept list of NodeType."""
        request = ContextRequest(
            query="test",
            tenant_ids=["tenant1"],
            expansion_types=[NodeType.CONCEPT, NodeType.ENTITY],
        )
        assert request.expansion_types == [NodeType.CONCEPT, NodeType.ENTITY]

    def test_max_depth_bounds(self):
        """max_depth should be between 1 and 10."""
        request = ContextRequest(
            query="test",
            tenant_ids=["tenant1"],
            max_depth=1,
        )
        assert request.max_depth == 1
        
        request = ContextRequest(
            query="test",
            tenant_ids=["tenant1"],
            max_depth=10,
        )
        assert request.max_depth == 10

    def test_shallow_planner_config(self):
        """Test typical shallow planner configuration."""
        request = ContextRequest(
            query="how to approve PO?",
            tenant_ids=["acme"],
            entry_types=[NodeType.FAQ, NodeType.PLAYBOOK],
            max_depth=1,
            max_tokens=3000,
            include_schemas=False,
            include_examples=False,
        )
        
        assert request.max_depth == 1
        assert request.max_tokens == 3000
        assert NodeType.FAQ in request.entry_types
        assert NodeType.PLAYBOOK in request.entry_types

    def test_keyword_search_config(self):
        """Test keyword-only search configuration."""
        request = ContextRequest(
            query="error code PO-4501",
            tenant_ids=["acme"],
            search_method="bm25",
        )
        
        assert request.search_method == "bm25"

    def test_semantic_search_config(self):
        """Test semantic-only search configuration."""
        request = ContextRequest(
            query="how do I handle purchase requests",
            tenant_ids=["acme"],
            search_method="vector",
        )
        
        assert request.search_method == "vector"

    def test_custom_weights_config(self):
        """Test custom search weight configuration."""
        request = ContextRequest(
            query="test",
            tenant_ids=["acme"],
            search_method="hybrid",
            bm25_weight=0.3,
            vector_weight=0.7,
        )
        
        assert request.bm25_weight == 0.3
        assert request.vector_weight == 0.7


class TestContextServiceSearchWeights:

    def test_resolve_search_weights_hybrid(self):
        """_resolve_search_weights should return request weights for hybrid."""
        from app.services.context_service import ContextService
        
        request = ContextRequest(
            query="test",
            tenant_ids=["acme"],
            search_method="hybrid",
            bm25_weight=0.3,
            vector_weight=0.7,
        )
        
        mock_session = MagicMock()
        mock_embedding = MagicMock()
        service = ContextService(mock_session, mock_embedding)
        
        bm25, vector = service._resolve_search_weights(request)
        
        assert bm25 == 0.3
        assert vector == 0.7

    def test_resolve_search_weights_bm25_only(self):
        """_resolve_search_weights should return (1.0, 0.0) for bm25."""
        from app.services.context_service import ContextService
        
        request = ContextRequest(
            query="test",
            tenant_ids=["acme"],
            search_method="bm25",
        )
        
        mock_session = MagicMock()
        mock_embedding = MagicMock()
        service = ContextService(mock_session, mock_embedding)
        
        bm25, vector = service._resolve_search_weights(request)
        
        assert bm25 == 1.0
        assert vector == 0.0

    def test_resolve_search_weights_vector_only(self):
        """_resolve_search_weights should return (0.0, 1.0) for vector."""
        from app.services.context_service import ContextService
        
        request = ContextRequest(
            query="test",
            tenant_ids=["acme"],
            search_method="vector",
        )
        
        mock_session = MagicMock()
        mock_embedding = MagicMock()
        service = ContextService(mock_session, mock_embedding)
        
        bm25, vector = service._resolve_search_weights(request)
        
        assert bm25 == 0.0
        assert vector == 1.0
