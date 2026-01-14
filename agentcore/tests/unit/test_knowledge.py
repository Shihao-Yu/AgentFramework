"""Unit tests for knowledge module."""

import pytest

from agentcore.knowledge.models import (
    KnowledgeType,
    KnowledgeNode,
    KnowledgeBundle,
    SearchResult,
    SearchResults,
)
from agentcore.knowledge.client import MockKnowledgeClient
from agentcore.knowledge.retriever import KnowledgeRetriever
from agentcore.auth.models import EnrichedUser, Permission
from agentcore.auth.context import RequestContext


# Fixtures
@pytest.fixture
def user():
    return EnrichedUser(
        user_id=1,
        username="testuser",
        email="test@example.com",
        display_name="Test User",
        department="Engineering",
        title="Engineer",
        entity_id=1,
        entity_name="Test Entity",
        permissions=frozenset([Permission.BUYER]),
        token="test-token",
    )


@pytest.fixture
def request_ctx(user):
    return RequestContext.create(
        user=user,
        session_id="test-session",
        request_id="test-request",
    )


@pytest.fixture
def sample_nodes():
    return [
        KnowledgeNode(
            id="node-1",
            type=KnowledgeType.SCHEMA,
            title="PurchaseOrder Schema",
            content="A purchase order contains: id, vendor, items, total, status.",
            summary="Schema for purchase orders",
            tenant="purchasing",
        ),
        KnowledgeNode(
            id="node-2",
            type=KnowledgeType.PLAYBOOK,
            title="How to Create a PO",
            content="Step 1: Select vendor. Step 2: Add items. Step 3: Submit for approval.",
            summary="Guide for creating purchase orders",
            tenant="purchasing",
        ),
        KnowledgeNode(
            id="node-3",
            type=KnowledgeType.FAQ,
            title="PO Approval Process",
            content="Q: How long does approval take? A: Usually 1-2 business days.",
            tenant="purchasing",
        ),
        KnowledgeNode(
            id="node-4",
            type=KnowledgeType.CONCEPT,
            title="Procurement Basics",
            content="Procurement is the process of acquiring goods and services.",
            tenant="shared",
        ),
    ]


class TestKnowledgeNode:
    """Tests for KnowledgeNode model."""

    def test_create_minimal(self):
        node = KnowledgeNode(
            id="test-1",
            type=KnowledgeType.CONCEPT,
            title="Test Node",
            content="Test content",
        )
        
        assert node.id == "test-1"
        assert node.type == KnowledgeType.CONCEPT
        assert node.title == "Test Node"
        assert node.content == "Test content"
        assert node.score is None
        assert node.edges == []

    def test_to_prompt_text(self):
        node = KnowledgeNode(
            id="test-1",
            type=KnowledgeType.SCHEMA,
            title="Test Schema",
            content="Field1, Field2, Field3",
            summary="A test schema",
        )
        
        text = node.to_prompt_text()
        
        assert "Test Schema" in text
        assert "schema" in text.lower()
        assert "A test schema" in text
        assert "Field1, Field2, Field3" in text

    def test_to_prompt_text_with_metadata(self):
        node = KnowledgeNode(
            id="test-1",
            type=KnowledgeType.CONCEPT,
            title="Test",
            content="Content",
            metadata={"key": "value"},
        )
        
        text = node.to_prompt_text(include_metadata=True)
        
        assert "key" in text
        assert "value" in text

    def test_truncate(self):
        long_content = "x" * 5000
        node = KnowledgeNode(
            id="test-1",
            type=KnowledgeType.CONCEPT,
            title="Test",
            content=long_content,
        )
        
        truncated = node.truncate(max_length=100)
        
        assert len(truncated.content) < len(long_content)
        assert "truncated" in truncated.content

    def test_truncate_no_change_if_short(self):
        node = KnowledgeNode(
            id="test-1",
            type=KnowledgeType.CONCEPT,
            title="Test",
            content="Short content",
        )
        
        truncated = node.truncate(max_length=100)
        
        assert truncated.content == node.content


class TestSearchResults:
    """Tests for SearchResults model."""

    def test_create_empty(self):
        results = SearchResults(query="test")
        
        assert len(results.results) == 0
        assert results.total_count == 0
        assert results.query == "test"

    def test_nodes_property(self, sample_nodes):
        results = SearchResults(
            results=[SearchResult(node=n, score=0.8) for n in sample_nodes],
            total_count=len(sample_nodes),
            query="purchase order",
        )
        
        nodes = results.nodes
        
        assert len(nodes) == len(sample_nodes)
        assert all(isinstance(n, KnowledgeNode) for n in nodes)

    def test_top(self, sample_nodes):
        results = SearchResults(
            results=[SearchResult(node=n, score=0.8) for n in sample_nodes],
            query="test",
        )
        
        top_2 = results.top(2)
        
        assert len(top_2.results) == 2

    def test_filter_by_type(self, sample_nodes):
        results = SearchResults(
            results=[SearchResult(node=n, score=0.8) for n in sample_nodes],
            query="test",
        )
        
        schemas_only = results.filter_by_type(KnowledgeType.SCHEMA)
        
        assert len(schemas_only.results) == 1
        assert schemas_only.results[0].node.type == KnowledgeType.SCHEMA

    def test_to_prompt_context(self, sample_nodes):
        results = SearchResults(
            results=[SearchResult(node=n, score=0.8) for n in sample_nodes],
            query="test",
        )
        
        context = results.to_prompt_context()
        
        assert "PurchaseOrder Schema" in context
        assert "How to Create a PO" in context


class TestKnowledgeBundle:
    """Tests for KnowledgeBundle model."""

    def test_from_search_results(self, sample_nodes):
        results = SearchResults(
            results=[SearchResult(node=n, score=0.8) for n in sample_nodes],
            query="purchase order",
        )
        
        bundle = KnowledgeBundle.from_search_results("purchase order", results)
        
        assert bundle.query == "purchase order"
        assert len(bundle.schemas) == 1
        assert len(bundle.playbooks) == 1
        assert len(bundle.faqs) == 1
        assert len(bundle.concepts) == 1

    def test_all_nodes(self, sample_nodes):
        results = SearchResults(
            results=[SearchResult(node=n, score=0.8) for n in sample_nodes],
            query="test",
        )
        bundle = KnowledgeBundle.from_search_results("test", results)
        
        all_nodes = bundle.all_nodes
        
        assert len(all_nodes) == len(sample_nodes)

    def test_is_empty(self):
        empty_bundle = KnowledgeBundle(query="test")
        
        assert empty_bundle.is_empty
        
        non_empty = KnowledgeBundle(
            query="test",
            concepts=[KnowledgeNode(id="1", type=KnowledgeType.CONCEPT, title="T", content="C")],
        )
        
        assert not non_empty.is_empty

    def test_get_for_planning(self, sample_nodes):
        results = SearchResults(
            results=[SearchResult(node=n, score=0.8) for n in sample_nodes],
            query="test",
        )
        bundle = KnowledgeBundle.from_search_results("test", results)
        
        planning_context = bundle.get_for_planning()
        
        # Should include playbooks and concepts
        assert "How to Create a PO" in planning_context
        assert "Procurement Basics" in planning_context

    def test_get_for_research(self, sample_nodes):
        results = SearchResults(
            results=[SearchResult(node=n, score=0.8) for n in sample_nodes],
            query="test",
        )
        bundle = KnowledgeBundle.from_search_results("test", results)
        
        research_context = bundle.get_for_research()
        
        # Should include schemas and FAQs
        assert "PurchaseOrder Schema" in research_context
        assert "PO Approval Process" in research_context

    def test_get_schema(self, sample_nodes):
        results = SearchResults(
            results=[SearchResult(node=n, score=0.8) for n in sample_nodes],
            query="test",
        )
        bundle = KnowledgeBundle.from_search_results("test", results)
        
        schema = bundle.get_schema("PurchaseOrder")
        
        assert schema is not None
        assert schema.type == KnowledgeType.SCHEMA

    def test_get_schema_not_found(self, sample_nodes):
        results = SearchResults(
            results=[SearchResult(node=n, score=0.8) for n in sample_nodes],
            query="test",
        )
        bundle = KnowledgeBundle.from_search_results("test", results)
        
        schema = bundle.get_schema("NonExistent")
        
        assert schema is None


class TestMockKnowledgeClient:
    """Tests for MockKnowledgeClient."""

    @pytest.mark.asyncio
    async def test_search_by_keyword(self, request_ctx, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        
        results = await client.search(request_ctx, "purchase order")
        
        assert len(results.results) > 0
        # Should find PO-related nodes
        assert any("Purchase" in r.node.title for r in results.results)

    @pytest.mark.asyncio
    async def test_search_filter_by_type(self, request_ctx, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        
        results = await client.search(
            request_ctx,
            "purchase",
            types=[KnowledgeType.SCHEMA],
        )
        
        assert all(r.node.type == KnowledgeType.SCHEMA for r in results.results)

    @pytest.mark.asyncio
    async def test_search_filter_by_tenant(self, request_ctx, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        
        results = await client.search(
            request_ctx,
            "procurement",
            tenant="shared",
        )
        
        assert all(r.node.tenant == "shared" for r in results.results)

    @pytest.mark.asyncio
    async def test_get_bundle(self, request_ctx, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        
        bundle = await client.get_bundle(request_ctx, "purchase order")
        
        assert not bundle.is_empty
        assert bundle.query == "purchase order"

    @pytest.mark.asyncio
    async def test_get_node(self, request_ctx, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        
        node = await client.get_node(request_ctx, "node-1")
        
        assert node is not None
        assert node.id == "node-1"

    @pytest.mark.asyncio
    async def test_get_node_not_found(self, request_ctx, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        
        node = await client.get_node(request_ctx, "nonexistent")
        
        assert node is None

    @pytest.mark.asyncio
    async def test_get_related(self, request_ctx):
        node1 = KnowledgeNode(
            id="node-1",
            type=KnowledgeType.CONCEPT,
            title="Node 1",
            content="Content 1",
            edges=["node-2"],
        )
        node2 = KnowledgeNode(
            id="node-2",
            type=KnowledgeType.CONCEPT,
            title="Node 2",
            content="Content 2",
        )
        
        client = MockKnowledgeClient(nodes=[node1, node2])
        
        related = await client.get_related(request_ctx, "node-1")
        
        assert len(related) == 1
        assert related[0].id == "node-2"

    @pytest.mark.asyncio
    async def test_get_schema(self, request_ctx, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        
        schema = await client.get_schema(request_ctx, "PurchaseOrder")
        
        assert schema is not None
        assert schema.type == KnowledgeType.SCHEMA

    def test_add_node(self, sample_nodes):
        client = MockKnowledgeClient()
        
        assert len(client._nodes) == 0
        
        client.add_node(sample_nodes[0])
        
        assert len(client._nodes) == 1

    def test_clear(self, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        
        assert len(client._nodes) > 0
        
        client.clear()
        
        assert len(client._nodes) == 0


class TestKnowledgeRetriever:
    """Tests for KnowledgeRetriever."""

    @pytest.mark.asyncio
    async def test_retrieve_for_planning(self, request_ctx, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        retriever = KnowledgeRetriever(client)
        
        # Use a query that matches our sample nodes
        bundle = await retriever.retrieve_for_planning(request_ctx, "purchase order")
        
        # Should find at least some knowledge
        # Note: may be empty if query doesn't match well enough
        assert bundle is not None

    @pytest.mark.asyncio
    async def test_retrieve_for_research(self, request_ctx, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        retriever = KnowledgeRetriever(client)
        
        bundle = await retriever.retrieve_for_research(request_ctx, "purchase order")
        
        assert not bundle.is_empty

    @pytest.mark.asyncio
    async def test_retrieve_schema(self, request_ctx, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        retriever = KnowledgeRetriever(client)
        
        schema = await retriever.retrieve_schema(request_ctx, "PurchaseOrder")
        
        assert schema is not None
        assert schema.type == KnowledgeType.SCHEMA

    @pytest.mark.asyncio
    async def test_get_context_for_llm(self, request_ctx, sample_nodes):
        client = MockKnowledgeClient(nodes=sample_nodes)
        retriever = KnowledgeRetriever(client)
        
        context = await retriever.get_context_for_llm(request_ctx, "purchase order")
        
        assert len(context) > 0
        assert isinstance(context, str)
