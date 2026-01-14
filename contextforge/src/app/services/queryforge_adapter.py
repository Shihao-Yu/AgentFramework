"""
Knowledge Verse Adapter for AgenticSearch QueryForge.

This adapter implements the MultiTenantVectorStore interface by querying
Knowledge Verse's PostgreSQL storage instead of ChromaDB. This enables
QueryForge's QueryGenerationPipeline to use Knowledge Verse as its backend.

Key Conversions:
- schema_field KnowledgeNode → FieldSpec (LangfuseFieldMetadata)
- example KnowledgeNode → ExampleSpec (LangfuseQAExample)
- schema_index KnowledgeNode → DocumentMasterConfig

Usage:
    adapter = KnowledgeVerseAdapter(session, embedding_client)
    
    # Use with QueryGenerationPipeline
    pipeline = QueryGenerationPipeline(
        vector_store=adapter,
        llm_client=llm_client,
    )
    
    result = await pipeline.generate_query(
        tenant_id="acme",
        document_name="orders",
        user_question="Show pending orders",
    )
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.enums import NodeType, KnowledgeStatus
from app.models.nodes import KnowledgeNode
from app.clients.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)


# =============================================================================
# AgenticSearch Types Import with Graceful Fallback
# =============================================================================

_QUERYFORGE_AVAILABLE = False

try:
    from agentic_search.queryforge.common.schema.field_schema import (
        FieldSpec,
        FieldType,
        SourceType,
    )
    from agentic_search.queryforge.common.schema.example_schema import (
        ExampleSpec,
        ExampleContent,
    )
    from agentic_search.queryforge.core.models import (
        DocumentMasterConfig,
        QueryType,
        Complexity,
        SearchRules,
    )
    _QUERYFORGE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AgenticSearch not available: {e}")
    # Define minimal stub types for type hints
    FieldSpec = Any
    ExampleSpec = Any
    DocumentMasterConfig = Any


# =============================================================================
# Source Type Mapping
# =============================================================================

# Map our schema source_type to QueryForge SourceType
QUERYFORGE_SOURCE_MAP = {
    "postgres": "postgres",
    "elasticsearch": "opensearch",
    "api": "rest_api",
}

# Map our query_type to QueryForge QueryType
QUERYFORGE_QUERY_TYPE_MAP = {
    "sql": "POSTGRES",
    "elasticsearch": "OPENSEARCH",
    "api": "REST_API",
}


# =============================================================================
# Knowledge Verse Adapter
# =============================================================================

class KnowledgeVerseAdapter:
    """
    Adapter that makes Knowledge Verse PostgreSQL storage compatible with
    AgenticSearch's MultiTenantVectorStore interface.
    
    This enables QueryForge's QueryGenerationPipeline to use our PostgreSQL
    knowledge_nodes table instead of ChromaDB for:
    - Schema field retrieval (get_similar_fields)
    - Q&A example retrieval (get_similar_qa_examples)
    - Master config loading (load_master_config)
    
    The adapter performs hybrid search using our PostgreSQL hybrid_search_nodes()
    function and converts results to QueryForge's expected types.
    """
    
    def __init__(
        self,
        session: AsyncSession,
        embedding_client: EmbeddingClient,
    ):
        """
        Initialize the adapter.
        
        Args:
            session: AsyncIO database session for querying knowledge_nodes
            embedding_client: Client for generating query embeddings
        """
        self.session = session
        self.embedding_client = embedding_client
    
    @staticmethod
    def is_available() -> bool:
        """Check if AgenticSearch QueryForge types are available."""
        return _QUERYFORGE_AVAILABLE
    
    # -------------------------------------------------------------------------
    # Schema Field Retrieval
    # -------------------------------------------------------------------------
    
    async def get_similar_fields(
        self,
        tenant_id: str,
        document_name: str,
        question: str,
        top_k: int = 10,
        similarity_threshold: float = 0.7,
    ) -> List["FieldSpec"]:
        """
        Retrieve similar schema fields using hybrid search.
        
        Queries schema_field nodes from knowledge_nodes table and converts
        them to FieldSpec objects for QueryForge compatibility.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Dataset/document name (maps to dataset_name)
            question: User question for similarity search
            top_k: Maximum fields to return
            similarity_threshold: Minimum similarity score (not strictly enforced)
        
        Returns:
            List of FieldSpec objects
        """
        if not _QUERYFORGE_AVAILABLE:
            logger.warning("QueryForge not available, returning empty list")
            return []
        
        try:
            # Generate query embedding
            query_embedding = await self.embedding_client.embed(question)
            
            # Call hybrid_search_nodes for schema_field nodes
            result = await self.session.execute(
                text("""
                    SELECT * FROM hybrid_search_nodes(
                        :query_text,
                        :query_embedding::vector,
                        :tenant_ids,
                        :node_types,
                        :top_k,
                        :bm25_weight,
                        :vector_weight
                    )
                """),
                {
                    "query_text": question,
                    "query_embedding": query_embedding,
                    "tenant_ids": [tenant_id],
                    "node_types": [NodeType.SCHEMA_FIELD.value],
                    "top_k": top_k,
                    "bm25_weight": 0.4,
                    "vector_weight": 0.6,
                }
            )
            
            rows = result.fetchall()
            
            # Filter by dataset_name if specified
            fields = []
            for row in rows:
                node_id = row[0]
                
                # Fetch full node details
                node = await self._get_node_by_id(node_id)
                if node is None:
                    continue
                
                # Filter by dataset_name
                if document_name and node.dataset_name != document_name:
                    continue
                
                # Convert to FieldSpec
                field_spec = self._node_to_field_spec(node)
                if field_spec:
                    fields.append(field_spec)
            
            logger.debug(
                f"Retrieved {len(fields)} schema fields for "
                f"{tenant_id}/{document_name}: {question[:50]}..."
            )
            return fields
            
        except Exception as e:
            logger.exception(f"Failed to retrieve schema fields: {e}")
            return []
    
    def _node_to_field_spec(self, node: KnowledgeNode) -> Optional["FieldSpec"]:
        """
        Convert a schema_field KnowledgeNode to FieldSpec.
        
        Mapping:
        - node.title → name, qualified_name
        - node.content.description → description
        - node.content.business_meaning → business_meaning
        - node.content.allowed_values → allowed_values
        - node.content.search_patterns → common_filters
        - node.content.value_synonyms → value_synonyms
        - node.data_type → type
        - node.content.nullable → nullable
        - node.content.indexed → is_indexed
        """
        if node.node_type != NodeType.SCHEMA_FIELD:
            return None
        
        content = node.content or {}
        
        # Determine field type
        field_type = self._map_data_type(node.data_type or "string")
        
        # Determine source type from dataset
        source_type = SourceType.UNKNOWN
        if node.dataset_name:
            # Try to infer from parent schema_index
            source_type = SourceType.POSTGRES  # Default
        
        return FieldSpec(
            name=node.title,
            qualified_name=node.field_path or node.title,
            type=field_type,
            nullable=content.get("nullable", True),
            description=content.get("description"),
            business_meaning=content.get("business_meaning"),
            maps_to=[],  # Could be populated from tags
            aliases=[],
            related_fields=[],
            allowed_values=content.get("allowed_values", []),
            value_synonyms=content.get("value_synonyms", {}),
            value_examples=[],
            value_patterns=None,
            value_encoding=None,
            searchable=True,
            filterable=True,
            sortable=True,
            aggregatable=False,
            search_guidance=None,
            common_filters=content.get("search_patterns", []),
            aggregation_hints=None,
            source_type=source_type,
            index_name=node.dataset_name,
            parent_entity=None,
            nested_fields=None,
            is_required=not content.get("nullable", True),
            is_indexed=content.get("indexed", False),
            is_sensitive=False,
            is_primary_key=False,
            human_edited=False,
            last_modified=node.updated_at,
            modified_by=node.updated_by,
            embedding=[],  # Not needed for retrieval
        )
    
    def _map_data_type(self, data_type: str) -> "FieldType":
        """Map our data_type string to QueryForge FieldType."""
        if not _QUERYFORGE_AVAILABLE:
            return data_type
        
        type_map = {
            "string": FieldType.STRING,
            "text": FieldType.TEXT,
            "keyword": FieldType.KEYWORD,
            "integer": FieldType.INTEGER,
            "int": FieldType.INTEGER,
            "bigint": FieldType.INTEGER,
            "float": FieldType.FLOAT,
            "double": FieldType.FLOAT,
            "decimal": FieldType.DECIMAL,
            "boolean": FieldType.BOOLEAN,
            "bool": FieldType.BOOLEAN,
            "date": FieldType.DATE,
            "datetime": FieldType.DATETIME,
            "timestamp": FieldType.TIMESTAMP,
            "json": FieldType.JSON,
            "jsonb": FieldType.JSON,
            "array": FieldType.ARRAY,
            "object": FieldType.OBJECT,
            "nested": FieldType.NESTED,
            "uuid": FieldType.UUID,
        }
        
        return type_map.get(data_type.lower(), FieldType.STRING)
    
    # -------------------------------------------------------------------------
    # Q&A Example Retrieval
    # -------------------------------------------------------------------------
    
    async def get_similar_qa_examples(
        self,
        tenant_id: str,
        document_name: str,
        question: str,
        top_n: int = 5,
        only_reviewed: bool = True,
        min_confidence: float = 0.8,
    ) -> List["ExampleSpec"]:
        """
        Retrieve similar Q&A examples using hybrid search.
        
        Queries example nodes from knowledge_nodes table and converts
        them to ExampleSpec objects for QueryForge compatibility.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Dataset/document name
            question: User question for similarity search
            top_n: Maximum examples to return
            only_reviewed: If True, only return verified examples
            min_confidence: Minimum confidence (not used in our schema)
        
        Returns:
            List of ExampleSpec objects
        """
        if not _QUERYFORGE_AVAILABLE:
            logger.warning("QueryForge not available, returning empty list")
            return []
        
        try:
            # Generate query embedding
            query_embedding = await self.embedding_client.embed(question)
            
            # Call hybrid_search_nodes for example nodes
            result = await self.session.execute(
                text("""
                    SELECT * FROM hybrid_search_nodes(
                        :query_text,
                        :query_embedding::vector,
                        :tenant_ids,
                        :node_types,
                        :top_k,
                        :bm25_weight,
                        :vector_weight
                    )
                """),
                {
                    "query_text": question,
                    "query_embedding": query_embedding,
                    "tenant_ids": [tenant_id],
                    "node_types": [NodeType.EXAMPLE.value],
                    "top_k": top_n * 2,  # Fetch more to filter
                    "bm25_weight": 0.4,
                    "vector_weight": 0.6,
                }
            )
            
            rows = result.fetchall()
            
            examples = []
            for row in rows:
                if len(examples) >= top_n:
                    break
                
                node_id = row[0]
                
                # Fetch full node details
                node = await self._get_node_by_id(node_id)
                if node is None:
                    continue
                
                # Filter by dataset_name
                if document_name and node.dataset_name != document_name:
                    continue
                
                # Filter by verification status
                if only_reviewed:
                    verified = node.content.get("verified", False) if node.content else False
                    if not verified:
                        continue
                
                # Convert to ExampleSpec
                example_spec = self._node_to_example_spec(node)
                if example_spec:
                    examples.append(example_spec)
            
            logger.debug(
                f"Retrieved {len(examples)} Q&A examples for "
                f"{tenant_id}/{document_name}: {question[:50]}..."
            )
            return examples
            
        except Exception as e:
            logger.exception(f"Failed to retrieve Q&A examples: {e}")
            return []
    
    def _node_to_example_spec(self, node: KnowledgeNode) -> Optional["ExampleSpec"]:
        """
        Convert an example KnowledgeNode to ExampleSpec.
        
        Mapping:
        - node.content.question → title (primary question)
        - node.content.query → content.query
        - node.content.query_type → content.query_type
        - node.content.explanation → content.explanation
        - node.content.verified → verified
        - node.created_at → created_at
        """
        if node.node_type != NodeType.EXAMPLE:
            return None
        
        content = node.content or {}
        
        question = content.get("question", node.title)
        query = content.get("query", "")
        query_type = content.get("query_type", "sql")
        explanation = content.get("explanation")
        verified = content.get("verified", False)
        
        return ExampleSpec(
            id=str(node.id),
            title=question,
            description=node.summary,
            variants=[],  # Could be extracted from tags or other sources
            content=ExampleContent(
                query=query,
                query_type=query_type,
                explanation=explanation,
            ),
            linked_concepts=[],
            linked_fields=[],
            linked_values={},
            additional_context=None,
            verified=verified,
            source="knowledge_verse",
            tags=node.tags or [],
            created_at=node.created_at or datetime.utcnow(),
            updated_at=node.updated_at,
            usage_count=0,
            embedding=[],  # Not needed for retrieval
        )
    
    # -------------------------------------------------------------------------
    # Master Config Loading
    # -------------------------------------------------------------------------
    
    async def load_master_config(
        self,
        tenant_id: str,
        document_name: str,
        version: Optional[str] = None,
    ) -> Optional[Union["DocumentMasterConfig", Dict[str, Any]]]:
        """
        Load master configuration from schema_index node.
        
        Converts schema_index node content to DocumentMasterConfig format.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Dataset/document name
            version: Optional version (not currently used)
        
        Returns:
            DocumentMasterConfig or dict with config data, or None
        """
        try:
            # Find schema_index node
            query = select(KnowledgeNode).where(
                KnowledgeNode.tenant_id == tenant_id,
                KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
                KnowledgeNode.dataset_name == document_name,
                KnowledgeNode.is_deleted == False,
            ).limit(1)
            
            result = await self.session.execute(query)
            node = result.scalar_one_or_none()
            
            if not node:
                logger.warning(
                    f"No schema_index found for {tenant_id}/{document_name}"
                )
                return None
            
            # Convert to config dict (or DocumentMasterConfig if available)
            config = self._node_to_config(node)
            
            logger.debug(
                f"Loaded master config for {tenant_id}/{document_name}"
            )
            return config
            
        except Exception as e:
            logger.exception(f"Failed to load master config: {e}")
            return None
    
    def _node_to_config(
        self, node: KnowledgeNode
    ) -> Union["DocumentMasterConfig", Dict[str, Any]]:
        """
        Convert schema_index node to DocumentMasterConfig or dict.
        
        Mapping:
        - node.content.source_type → query_type
        - node.content.description → description
        - node.content.query_patterns → formatting_rules
        """
        content = node.content or {}
        source_type = content.get("source_type", "postgres")
        
        # Map source_type to QueryType
        query_type_str = QUERYFORGE_QUERY_TYPE_MAP.get(source_type, "POSTGRES")
        
        # If QueryForge available, create proper DocumentMasterConfig
        if _QUERYFORGE_AVAILABLE:
            try:
                return DocumentMasterConfig(
                    tenant_id=node.tenant_id,
                    document_name=node.dataset_name or "",
                    query_type=QueryType[query_type_str],
                    schema_complexity=Complexity.MEDIUM,  # Default
                    version="1.0",
                    description=content.get("description", ""),
                    formatting_rules=content.get("query_patterns", []),
                    validation_rules=[],
                    search_rules=SearchRules(),
                    entities=[],
                )
            except Exception as e:
                logger.warning(f"Failed to create DocumentMasterConfig: {e}")
        
        # Fallback to dict
        return {
            "tenant_id": node.tenant_id,
            "document_name": node.dataset_name,
            "query_type": query_type_str,
            "schema_complexity": "MEDIUM",
            "version": "1.0",
            "description": content.get("description", ""),
            "formatting_rules": content.get("query_patterns", []),
            "validation_rules": [],
            "search_rules": {},
        }
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    async def _get_node_by_id(self, node_id: int) -> Optional[KnowledgeNode]:
        """Fetch a KnowledgeNode by ID."""
        query = select(KnowledgeNode).where(
            KnowledgeNode.id == node_id,
            KnowledgeNode.is_deleted == False,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def list_tenant_documents(self, tenant_id: str) -> List[str]:
        """
        List all documents (datasets) for a tenant.
        
        Returns unique dataset_name values from schema_index nodes.
        """
        query = select(KnowledgeNode.dataset_name).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
            KnowledgeNode.is_deleted == False,
            KnowledgeNode.dataset_name.isnot(None),
        ).distinct()
        
        result = await self.session.execute(query)
        rows = result.scalars().all()
        
        return [r for r in rows if r]
    
    async def get_all_fields(
        self,
        tenant_id: str,
        document_name: str,
    ) -> List["FieldSpec"]:
        """
        Get all schema fields for a document (for graph loading).
        
        Returns all schema_field nodes without similarity filtering.
        """
        if not _QUERYFORGE_AVAILABLE:
            return []
        
        query = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.node_type == NodeType.SCHEMA_FIELD,
            KnowledgeNode.dataset_name == document_name,
            KnowledgeNode.is_deleted == False,
        )
        
        result = await self.session.execute(query)
        nodes = result.scalars().all()
        
        fields = []
        for node in nodes:
            field = self._node_to_field_spec(node)
            if field:
                fields.append(field)
        
        return fields
    
    # -------------------------------------------------------------------------
    # Write Operations (for completeness)
    # -------------------------------------------------------------------------
    
    async def add_field(
        self,
        tenant_id: str,
        document_name: str,
        field: "FieldSpec",
    ) -> Optional[int]:
        """
        Add a schema field (creates schema_field node).
        
        Note: This is primarily for QueryForge compatibility.
        The main onboarding flow uses QueryForgeService directly.
        """
        logger.warning(
            "add_field called on adapter - use QueryForgeService.onboard_dataset instead"
        )
        return None
    
    async def add_qa_example(
        self,
        tenant_id: str,
        document_name: str,
        qa: "ExampleSpec",
    ) -> Optional[int]:
        """
        Add a Q&A example (creates example node).
        
        Note: This is primarily for QueryForge compatibility.
        The main flow uses QueryForgeService.add_example directly.
        """
        logger.warning(
            "add_qa_example called on adapter - use QueryForgeService.add_example instead"
        )
        return None
    
    async def get_related_documentation(
        self,
        tenant_id: str,
        document_name: str,
        question: str,
        top_k: int = 5,
    ) -> List[str]:
        """
        Get related documentation for a question.
        
        Currently returns empty list - documentation support can be added
        by creating a documentation node type or using existing FAQs.
        """
        # Could query FAQ nodes as documentation
        return []
