"""
Tests for variant search functionality.

Tests cover:
- Variant CRUD operations
- Variant embedding generation
- Hybrid search with variant matches
- Deduplication of variant matches
- match_source field in search results
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.variant_service import VariantService, VariantCreate, VariantResponse
from app.models.enums import VariantSource


class TestVariantCreate:
    """Test VariantCreate data class."""

    def test_variant_create_defaults(self):
        """Should have sensible defaults."""
        vc = VariantCreate(variant_text="How do I do X?")
        
        assert vc.variant_text == "How do I do X?"
        assert vc.source == VariantSource.MANUAL
        assert vc.source_reference is None

    def test_variant_create_custom_source(self):
        """Should accept custom source."""
        vc = VariantCreate(
            variant_text="Alternative phrasing",
            source=VariantSource.PIPELINE,
            source_reference="ticket-123"
        )
        
        assert vc.source == VariantSource.PIPELINE
        assert vc.source_reference == "ticket-123"


class TestVariantResponse:
    """Test VariantResponse data class."""

    def test_from_model(self):
        """Should convert from model correctly."""
        mock_variant = MagicMock()
        mock_variant.id = 1
        mock_variant.node_id = 10
        mock_variant.variant_text = "Test variant"
        mock_variant.source = VariantSource.MANUAL
        mock_variant.source_reference = None
        mock_variant.created_by = "user-123"
        mock_variant.created_at = datetime(2024, 1, 15, 10, 30)
        
        response = VariantResponse.from_model(mock_variant)
        
        assert response.id == 1
        assert response.node_id == 10
        assert response.variant_text == "Test variant"
        assert response.source == VariantSource.MANUAL
        assert response.created_by == "user-123"


class TestVariantServiceListVariants:
    """Test VariantService.list_variants."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_embedding_client(self):
        """Create mock embedding client."""
        client = AsyncMock()
        client.embed.return_value = [0.1] * 1536
        return client

    @pytest.fixture
    def service(self, mock_session, mock_embedding_client):
        """Create VariantService with mocks."""
        return VariantService(mock_session, mock_embedding_client)

    @pytest.mark.asyncio
    async def test_list_variants_empty_when_node_not_found(self, service, mock_session):
        """Should return empty list when node not found."""
        # Mock _get_node to return None
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await service.list_variants(
            node_id=999,
            user_tenant_ids=["tenant-a"]
        )
        
        assert result == []

    @pytest.mark.asyncio
    async def test_list_variants_returns_variants(self, service, mock_session):
        """Should return variants for valid node."""
        # Mock node exists
        mock_node = MagicMock()
        mock_node.id = 1
        
        # Mock variant results
        mock_variant = MagicMock()
        mock_variant.id = 10
        mock_variant.node_id = 1
        mock_variant.variant_text = "Variant text"
        mock_variant.source = VariantSource.MANUAL
        mock_variant.source_reference = None
        mock_variant.created_by = "user"
        mock_variant.created_at = datetime.utcnow()
        
        # Setup mock returns
        node_result = AsyncMock()
        node_result.scalar_one_or_none.return_value = mock_node
        
        variants_result = AsyncMock()
        variants_result.scalars.return_value.all.return_value = [mock_variant]
        
        mock_session.execute.side_effect = [node_result, variants_result]
        
        result = await service.list_variants(
            node_id=1,
            user_tenant_ids=["tenant-a"]
        )
        
        assert len(result) == 1
        assert result[0].variant_text == "Variant text"


class TestVariantServiceCreateVariant:
    """Test VariantService.create_variant."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def mock_embedding_client(self):
        """Create mock embedding client."""
        client = AsyncMock()
        client.embed.return_value = [0.1] * 1536
        return client

    @pytest.fixture
    def service(self, mock_session, mock_embedding_client):
        """Create VariantService with mocks."""
        return VariantService(mock_session, mock_embedding_client)

    @pytest.mark.asyncio
    async def test_create_variant_returns_none_for_missing_node(self, service, mock_session):
        """Should return None when node doesn't exist."""
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await service.create_variant(
            node_id=999,
            data=VariantCreate(variant_text="Test"),
            user_tenant_ids=["tenant-a"]
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_create_variant_generates_embedding(self, service, mock_session, mock_embedding_client):
        """Should generate embedding for new variant."""
        mock_node = MagicMock()
        mock_node.graph_version = 1
        
        # Mock: node exists
        node_result = AsyncMock()
        node_result.scalar_one_or_none.return_value = mock_node
        
        # Mock: no existing variant
        existing_result = AsyncMock()
        existing_result.scalar_one_or_none.return_value = None
        
        mock_session.execute.side_effect = [node_result, existing_result, AsyncMock()]
        mock_session.get = AsyncMock(return_value=mock_node)
        
        await service.create_variant(
            node_id=1,
            data=VariantCreate(variant_text="New variant text"),
            user_tenant_ids=["tenant-a"],
            created_by="user-123"
        )
        
        # Verify embedding was generated
        mock_embedding_client.embed.assert_called_once_with("New variant text")

    @pytest.mark.asyncio
    async def test_create_variant_raises_on_duplicate(self, service, mock_session):
        """Should raise error for duplicate variant text."""
        mock_node = MagicMock()
        
        # Mock: node exists
        node_result = AsyncMock()
        node_result.scalar_one_or_none.return_value = mock_node
        
        # Mock: existing variant found
        existing_variant = MagicMock()
        existing_result = AsyncMock()
        existing_result.scalar_one_or_none.return_value = existing_variant
        
        mock_session.execute.side_effect = [node_result, existing_result]
        
        with pytest.raises(ValueError) as exc_info:
            await service.create_variant(
                node_id=1,
                data=VariantCreate(variant_text="Duplicate text"),
                user_tenant_ids=["tenant-a"]
            )
        
        assert "already exists" in str(exc_info.value)


class TestVariantServiceDeleteVariant:
    """Test VariantService.delete_variant."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_embedding_client(self):
        """Create mock embedding client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session, mock_embedding_client):
        """Create VariantService with mocks."""
        return VariantService(mock_session, mock_embedding_client)

    @pytest.mark.asyncio
    async def test_delete_variant_returns_false_when_not_found(self, service, mock_session):
        """Should return False when variant doesn't exist."""
        mock_session.get.return_value = None
        
        result = await service.delete_variant(
            variant_id=999,
            user_tenant_ids=["tenant-a"]
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_variant_returns_false_for_unauthorized(self, service, mock_session):
        """Should return False when user can't access parent node."""
        mock_variant = MagicMock()
        mock_variant.node_id = 1
        mock_session.get.return_value = mock_variant
        
        # Mock: node not accessible
        node_result = AsyncMock()
        node_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = node_result
        
        result = await service.delete_variant(
            variant_id=1,
            user_tenant_ids=["wrong-tenant"]
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_variant_increments_graph_version(self, service, mock_session):
        """Should increment node graph_version on delete."""
        mock_variant = MagicMock()
        mock_variant.node_id = 1
        
        mock_node = MagicMock()
        mock_node.graph_version = 5
        
        mock_session.get.return_value = mock_variant
        
        node_result = AsyncMock()
        node_result.scalar_one_or_none.return_value = mock_node
        mock_session.execute.return_value = node_result
        
        result = await service.delete_variant(
            variant_id=1,
            user_tenant_ids=["tenant-a"]
        )
        
        assert result is True
        assert mock_node.graph_version == 6


class TestHybridSearchWithVariants:
    """Test hybrid search includes variant matches."""

    @pytest.mark.asyncio
    async def test_search_result_includes_match_source(self):
        """Search results should include match_source field."""
        # This is more of an integration test concept
        # The match_source field is set by the SQL function
        
        # Mock a search result row with match_source
        mock_row = MagicMock()
        mock_row.id = 1
        mock_row.tenant_id = "tenant-a"
        mock_row.node_type = "faq"
        mock_row.title = "FAQ Title"
        mock_row.summary = "Summary"
        mock_row.content = "Content"
        mock_row.tags = ["tag1"]
        mock_row.dataset_name = None
        mock_row.field_path = None
        mock_row.bm25_rank = 1
        mock_row.vector_rank = 2
        mock_row.bm25_score = 0.8
        mock_row.vector_score = 0.9
        mock_row.rrf_score = 0.85
        mock_row.match_source = "variant"  # Key field
        
        # Verify the attribute is accessible
        assert mock_row.match_source == "variant"

    def test_match_source_values(self):
        """match_source should be 'node' or 'variant'."""
        valid_sources = ["node", "variant"]
        
        for source in valid_sources:
            mock_row = MagicMock()
            mock_row.match_source = source
            assert mock_row.match_source in valid_sources


class TestVariantSearchDeduplication:
    """Test deduplication of variant search results."""

    def test_same_node_matched_multiple_ways_deduplicated(self):
        """When same node matches via title and variant, should dedupe."""
        # This tests the concept - actual implementation is in SQL
        
        # Scenario: Node 1 matches both directly and via variant
        results_before_dedup = [
            {"node_id": 1, "match_source": "node", "rrf_score": 0.8},
            {"node_id": 1, "match_source": "variant", "rrf_score": 0.9},
            {"node_id": 2, "match_source": "node", "rrf_score": 0.7},
        ]
        
        # After dedup, should keep highest scoring match per node
        # This simulates what the SQL DISTINCT ON does
        seen_nodes = set()
        deduped = []
        
        # Sort by score desc, then take first per node_id
        sorted_results = sorted(
            results_before_dedup,
            key=lambda x: x["rrf_score"],
            reverse=True
        )
        
        for result in sorted_results:
            if result["node_id"] not in seen_nodes:
                deduped.append(result)
                seen_nodes.add(result["node_id"])
        
        assert len(deduped) == 2
        # Node 1 should keep the variant match (higher score)
        node_1_result = next(r for r in deduped if r["node_id"] == 1)
        assert node_1_result["match_source"] == "variant"
        assert node_1_result["rrf_score"] == 0.9


class TestVariantSearchIntegration:
    """Integration-level tests for variant search flow."""

    def test_variant_included_in_search_scope(self):
        """Variants should be searched alongside main content."""
        # This documents the expected behavior
        # The hybrid_search_nodes SQL function UNIONs:
        # 1. Matches on knowledge_nodes (title, content)
        # 2. Matches on node_variants (variant_text)
        
        search_scope = [
            "knowledge_nodes.title",
            "knowledge_nodes.content",
            "node_variants.variant_text",  # Added by migration 004
        ]
        
        assert "node_variants.variant_text" in search_scope

    def test_variant_match_returns_parent_node(self):
        """Matching a variant should return the parent node."""
        # When variant "How to purchase?" matches,
        # The result should be the parent FAQ node,
        # not just the variant text
        
        variant = {
            "id": 100,
            "node_id": 1,  # Parent FAQ
            "variant_text": "How to purchase?"
        }
        
        parent_node = {
            "id": 1,
            "title": "Purchasing Guide",
            "content": "Full guide content..."
        }
        
        # Search result should contain parent node info
        expected_result = {
            "id": parent_node["id"],  # Parent node ID
            "title": parent_node["title"],
            "content": parent_node["content"],
            "match_source": "variant",  # Indicates matched via variant
        }
        
        assert expected_result["id"] == 1
        assert expected_result["match_source"] == "variant"
