"""
ContextForge service for Knowledge Verse.

Provides:
- Schema onboarding (parse, enrich, store as KnowledgeNodes)
- Query generation (NL → SQL/DSL/API)

Uses ContextForge modules (migrated from AgenticSearch QueryForge) with:
- PostgreSQL storage via KnowledgeNode/KnowledgeEdge tables
- Async/await with SQLAlchemy 2.0
- InferenceClient for LLM calls

Usage:
    service = QueryForgeService(session, embedding_client)
    result = await service.onboard_dataset(...)
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import logging
import re

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, desc as sql_desc

from app.models.enums import NodeType, EdgeType, KnowledgeStatus, Visibility
from app.models.nodes import KnowledgeNode
from app.models.edges import KnowledgeEdge
from app.clients.embedding_client import EmbeddingClient
from app.services.queryforge_adapter import KnowledgeVerseAdapter

logger = logging.getLogger(__name__)

# =============================================================================
# ContextForge Imports
# =============================================================================

from app.contextforge.generation import QueryGenerationPipeline
from app.contextforge.sources import (
    get_source,
    list_sources,
    is_source_registered,
)
from app.contextforge.schema import FieldSpec as UnifiedField
from app.contextforge.core import QueryType


SOURCE_TYPE_MAP = {
    "postgres": "postgres",
    "opensearch": "elasticsearch",
    "elasticsearch": "elasticsearch",
    "clickhouse": "postgres",
    "rest_api": "api",
    "mysql": "postgres",
}


# =============================================================================
# QueryForge Service
# =============================================================================

class QueryForgeService:
    """
    Service wrapping AgenticSearch QueryForge for Knowledge Verse integration.
    
    Provides:
    - Dataset onboarding: Parse schema → Create KnowledgeNodes (schema_index, schema_field)
    - Query generation: NL → SQL/DSL/API query
    - Example management: Store Q&A pairs as example nodes
    
    Gracefully handles case where AgenticSearch is not installed.
    """
    
    def __init__(
        self,
        session: AsyncSession,
        embedding_client: EmbeddingClient,
        vector_store: Optional[Any] = None,
        llm_client: Optional[Any] = None,
    ):
        """
        Initialize QueryForge service.
        
        Args:
            session: Database session for node/edge operations
            embedding_client: Client for generating embeddings
            vector_store: Optional ChromaDB vector store for AgenticSearch
            llm_client: Optional LLM client for enrichment and generation
        """
        self.session = session
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.llm_client = llm_client
    
    @staticmethod
    def is_available() -> bool:
        """Check if QueryForge or ContextForge is available."""
        return _QUERYFORGE_AVAILABLE or _CONTEXTFORGE_AVAILABLE
    
    @staticmethod
    def is_queryforge_available() -> bool:
        """Check if AgenticSearch QueryForge (external) is available."""
        return _QUERYFORGE_AVAILABLE
    
    @staticmethod
    def is_contextforge_available() -> bool:
        """Check if ContextForge (local fallback) is available."""
        return _CONTEXTFORGE_AVAILABLE
    
    @staticmethod
    def get_import_error() -> Optional[str]:
        """Get import error if neither backend is available."""
        if _QUERYFORGE_AVAILABLE or _CONTEXTFORGE_AVAILABLE:
            return None
        return _IMPORT_ERROR
    
    @staticmethod
    def list_available_sources() -> List[str]:
        """List available data source types."""
        if _QUERYFORGE_AVAILABLE or _CONTEXTFORGE_AVAILABLE:
            return list_sources()
        return []
    
    # -------------------------------------------------------------------------
    # Schema Onboarding
    # -------------------------------------------------------------------------
    
    async def onboard_dataset(
        self,
        tenant_id: str,
        dataset_name: str,
        source_type: str,
        raw_schema: Union[str, Dict[str, Any]],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        enable_enrichment: bool = False,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Onboard a dataset by parsing its schema and creating KnowledgeNodes.
        
        This is the main entry point for dataset onboarding. It:
        1. Parses the raw schema using AgenticSearch source plugins
        2. Creates a schema_index node for the dataset
        3. Creates schema_field nodes for each field
        4. Creates PARENT edges from fields to index
        
        Args:
            tenant_id: Tenant identifier
            dataset_name: Name of the dataset/table/index
            source_type: Source type (postgres, opensearch, rest_api, etc.)
            raw_schema: Raw schema (DDL, JSON mapping, OpenAPI spec)
            description: Optional description for the dataset
            tags: Optional tags for categorization
            enable_enrichment: Whether to use LLM for metadata enrichment
            created_by: User ID for audit
        
        Returns:
            Dict with:
                - status: "success" or "error"
                - dataset_name: Name of onboarded dataset
                - schema_index_id: ID of created schema_index node
                - field_count: Number of fields created
                - fields: List of created field node IDs
                - errors: List of any errors encountered
        """
        if not (_QUERYFORGE_AVAILABLE or _CONTEXTFORGE_AVAILABLE):
            return {
                "status": "error",
                "error": "Neither AgenticSearch nor ContextForge available",
                "install_hint": "pip install -e ../agentic_search or check ContextForge setup",
            }
        
        errors: List[str] = []
        
        if not is_source_registered(source_type):
            available = list_sources()
            return {
                "status": "error",
                "error": f"Unknown source type: {source_type}",
                "available_sources": available,
            }
        
        try:
            # Get source plugin
            source = get_source(source_type)
            
            # Parse schema
            parsed_schema = source.parse_schema(raw_schema)
            
            # Convert to unified fields
            unified_fields = source.to_unified_fields(parsed_schema)
            
            # Optionally enrich with LLM
            if enable_enrichment and self.llm_client:
                # TODO: Implement LLM enrichment via source.onboard() 
                pass
            
            # Create schema_index node
            schema_index_node = await self._create_schema_index_node(
                tenant_id=tenant_id,
                dataset_name=dataset_name,
                source_type=source_type,
                description=description or f"Schema for {dataset_name}",
                tags=tags or [],
                field_count=len(unified_fields),
                created_by=created_by,
            )
            
            # Create schema_field nodes
            if schema_index_node.id is None:
                return {
                    "status": "error",
                    "error": "Failed to create schema_index node",
                    "dataset_name": dataset_name,
                }
            
            field_nodes = await self._create_schema_field_nodes(
                tenant_id=tenant_id,
                dataset_name=dataset_name,
                schema_index_id=schema_index_node.id,
                unified_fields=unified_fields,
                tags=tags or [],
                created_by=created_by,
            )
            
            return {
                "status": "success",
                "dataset_name": dataset_name,
                "source_type": source_type,
                "schema_index_id": schema_index_node.id,
                "field_count": len(field_nodes),
                "fields": [f.id for f in field_nodes],
                "errors": errors if errors else None,
            }
            
        except Exception as e:
            logger.exception(f"Failed to onboard dataset {dataset_name}")
            return {
                "status": "error",
                "error": str(e),
                "dataset_name": dataset_name,
            }
    
    async def _create_schema_index_node(
        self,
        tenant_id: str,
        dataset_name: str,
        source_type: str,
        description: str,
        tags: List[str],
        field_count: int,
        created_by: Optional[str],
    ) -> KnowledgeNode:
        """Create a schema_index node for a dataset."""
        # Map source type to our content schema format
        mapped_source_type = SOURCE_TYPE_MAP.get(source_type, source_type)
        
        content: Dict[str, Any] = {
            "source_type": mapped_source_type,
            "description": description,
            "query_patterns": [],
        }
        
        # Add source-specific fields
        if mapped_source_type == "postgres":
            content["table_name"] = dataset_name
        elif mapped_source_type == "elasticsearch":
            content["index_name"] = dataset_name
        elif mapped_source_type == "api":
            content["endpoint"] = dataset_name
        
        # Build embedding text
        embed_text = f"{dataset_name}\n{description}"
        embedding = await self.embedding_client.embed(embed_text)
        
        node = KnowledgeNode(
            tenant_id=tenant_id,
            node_type=NodeType.SCHEMA_INDEX,
            title=f"Schema: {dataset_name}",
            summary=f"{source_type} schema with {field_count} fields",
            content=content,
            tags=tags + [f"source:{source_type}"],
            dataset_name=dataset_name,
            status=KnowledgeStatus.PUBLISHED,
            visibility=Visibility.INTERNAL,
            source="queryforge",
            created_by=created_by,
        )
        
        self.session.add(node)
        await self.session.flush()
        
        # Update embedding
        await self.session.execute(
            text("""
                UPDATE agent.knowledge_nodes 
                SET embedding = :embedding::vector 
                WHERE id = :id
            """),
            {"id": node.id, "embedding": embedding}
        )
        
        await self.session.commit()
        await self.session.refresh(node)
        
        return node
    
    async def _create_schema_field_nodes(
        self,
        tenant_id: str,
        dataset_name: str,
        schema_index_id: int,
        unified_fields: List[Any],  # List[UnifiedField] when available
        tags: List[str],
        created_by: Optional[str],
    ) -> List[KnowledgeNode]:
        """Create schema_field nodes and link to schema_index."""
        nodes: List[KnowledgeNode] = []
        
        for field in unified_fields:
            # Build content from UnifiedField
            field_desc = getattr(field, 'description', None) or f"Field {field.path}"
            content: Dict[str, Any] = {
                "description": field_desc,
                "business_meaning": getattr(field, 'business_meaning', None),
                "allowed_values": getattr(field, 'allowed_values', None) or [],
                "nullable": not getattr(field, 'is_required', False),
                "indexed": getattr(field, 'is_indexed', True),
                "search_patterns": [],
                "business_rules": [],
            }
            
            # Add value synonyms if present
            value_synonyms = getattr(field, 'value_synonyms', None)
            if value_synonyms:
                content["value_synonyms"] = value_synonyms
            
            # Build embedding text
            embed_text = f"{field.path}\n{field_desc}"
            business_meaning = getattr(field, 'business_meaning', None)
            if business_meaning:
                embed_text += f"\n{business_meaning}"
            embedding = await self.embedding_client.embed(embed_text)
            
            # Create node
            node = KnowledgeNode(
                tenant_id=tenant_id,
                node_type=NodeType.SCHEMA_FIELD,
                title=field.path,
                summary=field_desc,
                content=content,
                tags=tags,
                dataset_name=dataset_name,
                field_path=field.path,
                data_type=field.field_type,
                status=KnowledgeStatus.PUBLISHED,
                visibility=Visibility.INTERNAL,
                source="queryforge",
                created_by=created_by,
            )
            
            self.session.add(node)
            await self.session.flush()
            
            # Update embedding
            await self.session.execute(
                text("""
                    UPDATE agent.knowledge_nodes 
                    SET embedding = :embedding::vector 
                    WHERE id = :id
                """),
                {"id": node.id, "embedding": embedding}
            )
            
            nodes.append(node)
            
            # Create PARENT edge: schema_index → field
            edge = KnowledgeEdge(
                source_id=schema_index_id,
                target_id=node.id,
                edge_type=EdgeType.PARENT,
                is_auto_generated=True,
                metadata_={"auto_generated": True},
                created_by=created_by,
            )
            self.session.add(edge)
        
        await self.session.commit()
        
        # Refresh all nodes
        for node in nodes:
            await self.session.refresh(node)
        
        return nodes
    
    # -------------------------------------------------------------------------
    # Query Generation
    # -------------------------------------------------------------------------
    
    async def generate_query(
        self,
        tenant_id: str,
        dataset_name: str,
        question: str,
        include_explanation: bool = False,
        use_pipeline: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a query from natural language.
        
        Uses the schema_index and schema_field nodes for context,
        then delegates to AgenticSearch for query generation.
        
        When use_pipeline=True and AgenticSearch is available, this method
        creates a KnowledgeVerseAdapter to bridge our PostgreSQL storage
        with QueryForge's QueryGenerationPipeline.
        
        Args:
            tenant_id: Tenant identifier
            dataset_name: Dataset to query against
            question: Natural language question
            include_explanation: Whether to include query explanation
            use_pipeline: Whether to use QueryGenerationPipeline (default True)
        
        Returns:
            Dict with:
                - status: "success" or "error"
                - query: Generated query string
                - query_type: Type of query (sql, elasticsearch, api)
                - explanation: Optional explanation
                - confidence: Confidence score (if using pipeline)
        """
        if not self.llm_client:
            return {
                "status": "error",
                "error": "LLM client not configured",
            }
        
        try:
            # Get schema context from our nodes
            context = await self._build_query_context(tenant_id, dataset_name)
            
            if not context:
                return {
                    "status": "error",
                    "error": f"Dataset {dataset_name} not found for tenant {tenant_id}",
                }
            
            if use_pipeline and (_QUERYFORGE_AVAILABLE or _CONTEXTFORGE_AVAILABLE):
                vector_store = self.vector_store
                if vector_store is None:
                    vector_store = KnowledgeVerseAdapter(
                        session=self.session,
                        embedding_client=self.embedding_client,
                    )
                
                pipeline = QueryGenerationPipeline(
                    vector_store=vector_store,
                    llm_client=self.llm_client,
                )
                
                result = await pipeline.generate_query(
                    tenant_id=tenant_id,
                    document_name=dataset_name,
                    user_question=question,
                )
                
                return {
                    "status": "success",
                    "query": result.query,
                    "query_type": context.get("source_type", "sql"),
                    "explanation": getattr(result, "explanation", None) if include_explanation else None,
                    "confidence": getattr(result, "confidence", None),
                }
            
            # Direct LLM call fallback
            return await self._generate_query_direct(
                context=context,
                question=question,
                include_explanation=include_explanation,
            )
            
        except Exception as e:
            logger.exception(f"Failed to generate query for {dataset_name}")
            return {
                "status": "error",
                "error": str(e),
            }
    
    async def _build_query_context(
        self,
        tenant_id: str,
        dataset_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Build query context from our KnowledgeNodes."""
        # Find schema_index node
        query = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.is_deleted == False,
        ).limit(1)
        result = await self.session.execute(query)
        index_node = result.scalar_one_or_none()
        
        if not index_node:
            return None
        
        # Find schema_field nodes
        field_query = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.node_type == NodeType.SCHEMA_FIELD,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.is_deleted == False,
        ).limit(500)
        field_result = await self.session.execute(field_query)
        field_nodes = field_result.scalars().all()
        
        # Find example nodes
        example_query = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.is_deleted == False,
        ).limit(10)
        example_result = await self.session.execute(example_query)
        example_nodes = example_result.scalars().all()
        
        return {
            "source_type": index_node.content.get("source_type", "postgres"),
            "dataset_name": dataset_name,
            "description": index_node.content.get("description", ""),
            "fields": [
                {
                    "path": f.field_path,
                    "type": f.data_type,
                    "description": f.content.get("description", ""),
                    "allowed_values": f.content.get("allowed_values", []),
                }
                for f in field_nodes
            ],
            "examples": [
                {
                    "question": e.content.get("question", ""),
                    "query": e.content.get("query", ""),
                }
                for e in example_nodes
                if e.content.get("verified", False)
            ],
        }
    
    async def _generate_query_direct(
        self,
        context: Dict[str, Any],
        question: str,
        include_explanation: bool,
    ) -> Dict[str, Any]:
        """Generate query using direct LLM call with node context."""
        # Build prompt from context
        source_type = context.get("source_type", "postgres")
        
        prompt = self._build_generation_prompt(
            source_type=source_type,
            schema_context=context,
            question=question,
            include_explanation=include_explanation,
        )
        
        # Call LLM
        response = await self.llm_client.submit_prompt(prompt)
        
        # Extract query from response
        query = self._extract_query(response, source_type)
        
        return {
            "status": "success",
            "query": query,
            "query_type": source_type,
            "explanation": response if include_explanation else None,
        }
    
    def _build_generation_prompt(
        self,
        source_type: str,
        schema_context: Dict[str, Any],
        question: str,
        include_explanation: bool,
    ) -> str:
        """Build LLM prompt for query generation."""
        # Format fields
        fields_text = "\n".join([
            f"- {f['path']} ({f['type']}): {f['description']}"
            + (f" [values: {', '.join(f['allowed_values'][:5])}]" if f.get('allowed_values') else "")
            for f in schema_context.get("fields", [])[:50]  # Limit fields
        ])
        
        # Format examples
        examples_text = ""
        examples = schema_context.get("examples", [])
        if examples:
            examples_text = "Examples:\n" + "\n".join([
                f"Q: {e['question']}\nA: {e['query']}"
                for e in examples[:5]
            ])
        
        # Build prompt based on source type
        if source_type in ("postgres", "mysql", "clickhouse"):
            query_format = "SQL"
        elif source_type == "elasticsearch":
            query_format = "OpenSearch DSL (JSON)"
        elif source_type == "api":
            query_format = "REST API request"
        else:
            query_format = "query"
        
        prompt = f"""Generate a {query_format} query for the following question.

Dataset: {schema_context.get('dataset_name', 'unknown')}
Description: {schema_context.get('description', '')}

Schema:
{fields_text}

{examples_text}

Question: {question}

Generate only the {query_format} query. {"Include a brief explanation." if include_explanation else "Do not include explanation."}
"""
        return prompt
    
    def _extract_query(self, response: str, source_type: str) -> str:
        """Extract query from LLM response."""
        # Try to extract from code blocks
        if source_type in ("postgres", "mysql", "clickhouse"):
            # SQL code block
            match = re.search(r"```(?:sql)?\s*(.*?)```", response, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        elif source_type == "elasticsearch":
            # JSON code block
            match = re.search(r"```(?:json)?\s*(.*?)```", response, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: return full response
        return response.strip()
    
    # -------------------------------------------------------------------------
    # Example Management
    # -------------------------------------------------------------------------
    
    async def add_example(
        self,
        tenant_id: str,
        dataset_name: str,
        question: str,
        query: str,
        query_type: str,
        explanation: Optional[str] = None,
        verified: bool = False,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a Q&A example for a dataset.
        
        Examples are used to improve query generation quality.
        
        Args:
            tenant_id: Tenant identifier
            dataset_name: Dataset this example is for
            question: Natural language question
            query: Correct query answer
            query_type: Type of query (sql, elasticsearch, api)
            explanation: Optional explanation
            verified: Whether this example is verified
            created_by: User ID for audit
        
        Returns:
            Dict with status and created node ID
        """
        # Validate query_type
        valid_types = ["sql", "elasticsearch", "api"]
        if query_type not in valid_types:
            return {
                "status": "error",
                "error": f"Invalid query_type. Must be one of: {valid_types}",
            }
        
        try:
            content: Dict[str, Any] = {
                "question": question,
                "query": query,
                "query_type": query_type,
                "explanation": explanation,
                "verified": verified,
            }
            
            # Build embedding text
            embed_text = f"{question}\n{query}"
            embedding = await self.embedding_client.embed(embed_text)
            
            node = KnowledgeNode(
                tenant_id=tenant_id,
                node_type=NodeType.EXAMPLE,
                title=question[:100],  # Truncate for title
                summary=f"Example: {question[:50]}...",
                content=content,
                tags=[f"query_type:{query_type}"],
                dataset_name=dataset_name,
                status=KnowledgeStatus.PUBLISHED if verified else KnowledgeStatus.DRAFT,
                visibility=Visibility.INTERNAL,
                source="manual",
                created_by=created_by,
            )
            
            self.session.add(node)
            await self.session.flush()
            
            # Update embedding
            await self.session.execute(
                text("""
                    UPDATE agent.knowledge_nodes 
                    SET embedding = :embedding::vector 
                    WHERE id = :id
                """),
                {"id": node.id, "embedding": embedding}
            )
            
            # Link to schema_index if exists
            index_query = select(KnowledgeNode).where(
                KnowledgeNode.tenant_id == tenant_id,
                KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
                KnowledgeNode.dataset_name == dataset_name,
                KnowledgeNode.is_deleted == False,
            ).limit(1)
            index_result = await self.session.execute(index_query)
            index_node = index_result.scalar_one_or_none()
            
            if index_node:
                edge = KnowledgeEdge(
                    source_id=node.id,
                    target_id=index_node.id,
                    edge_type=EdgeType.EXAMPLE_OF,
                    is_auto_generated=True,
                    metadata_={"auto_generated": True},
                    created_by=created_by,
                )
                self.session.add(edge)
            
            await self.session.commit()
            await self.session.refresh(node)
            
            return {
                "status": "success",
                "example_id": node.id,
                "verified": verified,
            }
            
        except Exception as e:
            logger.exception(f"Failed to add example for {dataset_name}")
            return {
                "status": "error",
                "error": str(e),
            }
    
    async def verify_example(
        self,
        example_id: int,
        verified: bool = True,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark an example as verified or unverified."""
        try:
            query = select(KnowledgeNode).where(
                KnowledgeNode.id == example_id,
                KnowledgeNode.is_deleted == False,
            )
            result = await self.session.execute(query)
            node = result.scalar_one_or_none()
            
            if not node:
                return {"status": "error", "error": "Example not found"}
            
            if node.node_type != NodeType.EXAMPLE:
                return {"status": "error", "error": "Node is not an example"}
            
            # Update content
            content = dict(node.content)
            content["verified"] = verified
            
            node.content = content
            node.status = KnowledgeStatus.PUBLISHED if verified else KnowledgeStatus.DRAFT
            node.updated_by = updated_by
            node.updated_at = datetime.utcnow()
            node.version += 1
            
            await self.session.commit()
            await self.session.refresh(node)
            
            return {
                "status": "success",
                "example_id": example_id,
                "verified": verified,
            }
            
        except Exception as e:
            logger.exception(f"Failed to verify example {example_id}")
            return {"status": "error", "error": str(e)}
    
    async def list_examples(
        self,
        tenant_id: str,
        dataset_name: Optional[str] = None,
        verified_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List examples for a tenant/dataset."""
        query = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
            KnowledgeNode.is_deleted == False,
        )
        
        if dataset_name:
            query = query.where(KnowledgeNode.dataset_name == dataset_name)
        
        query = query.order_by(sql_desc(KnowledgeNode.created_at)).limit(limit)
        
        result = await self.session.execute(query)
        nodes = result.scalars().all()
        
        results = []
        for node in nodes:
            if verified_only and not node.content.get("verified", False):
                continue
            
            results.append({
                "id": node.id,
                "question": node.content.get("question", ""),
                "query": node.content.get("query", ""),
                "query_type": node.content.get("query_type", ""),
                "explanation": node.content.get("explanation"),
                "verified": node.content.get("verified", False),
                "dataset_name": node.dataset_name,
                "created_at": node.created_at.isoformat() if node.created_at else None,
            })
        
        return results
    
    # -------------------------------------------------------------------------
    # Dataset Management
    # -------------------------------------------------------------------------
    
    async def get_dataset(
        self,
        tenant_id: str,
        dataset_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Get dataset details including schema and examples."""
        # Get schema_index
        query = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.is_deleted == False,
        ).limit(1)
        result = await self.session.execute(query)
        index_node = result.scalar_one_or_none()
        
        if not index_node:
            return None
        
        # Get field count
        field_count_query = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.node_type == NodeType.SCHEMA_FIELD,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.is_deleted == False,
        )
        field_result = await self.session.execute(field_count_query)
        field_nodes = field_result.scalars().all()
        
        # Get example count
        example_query = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.is_deleted == False,
        )
        example_result = await self.session.execute(example_query)
        example_nodes = example_result.scalars().all()
        
        verified_count = sum(
            1 for e in example_nodes if e.content.get("verified", False)
        )
        
        return {
            "id": index_node.id,
            "tenant_id": tenant_id,
            "dataset_name": dataset_name,
            "source_type": index_node.content.get("source_type", "unknown"),
            "description": index_node.content.get("description", ""),
            "field_count": len(field_nodes),
            "example_count": len(example_nodes),
            "verified_example_count": verified_count,
            "tags": index_node.tags,
            "status": index_node.status.value,
            "created_at": index_node.created_at.isoformat() if index_node.created_at else None,
            "updated_at": index_node.updated_at.isoformat() if index_node.updated_at else None,
        }
    
    async def list_datasets(
        self,
        tenant_id: str,
        source_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List all datasets for a tenant."""
        query = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.node_type == NodeType.SCHEMA_INDEX,
            KnowledgeNode.is_deleted == False,
        ).order_by(sql_desc(KnowledgeNode.created_at)).limit(limit)
        
        result = await self.session.execute(query)
        nodes = result.scalars().all()
        
        results = []
        for node in nodes:
            node_source_type = node.content.get("source_type", "")
            
            # Filter by source_type if specified
            if source_type:
                mapped = SOURCE_TYPE_MAP.get(source_type, source_type)
                if node_source_type != mapped:
                    continue
            
            results.append({
                "id": node.id,
                "dataset_name": node.dataset_name,
                "source_type": node_source_type,
                "description": node.content.get("description", ""),
                "tags": node.tags,
                "status": node.status.value,
                "created_at": node.created_at.isoformat() if node.created_at else None,
            })
        
        return results
    
    async def delete_dataset(
        self,
        tenant_id: str,
        dataset_name: str,
    ) -> Dict[str, Any]:
        """
        Delete a dataset and all its associated nodes.
        
        Deletes:
        - schema_index node
        - All schema_field nodes
        - All example nodes
        - All edges between them
        """
        deleted_count = 0
        
        try:
            # Get all nodes for this dataset
            for node_type in [NodeType.SCHEMA_INDEX, NodeType.SCHEMA_FIELD, NodeType.EXAMPLE]:
                query = select(KnowledgeNode).where(
                    KnowledgeNode.tenant_id == tenant_id,
                    KnowledgeNode.node_type == node_type,
                    KnowledgeNode.dataset_name == dataset_name,
                    KnowledgeNode.is_deleted == False,
                )
                result = await self.session.execute(query)
                nodes = result.scalars().all()
                
                for node in nodes:
                    # Delete edges
                    await self.session.execute(
                        text("""
                            DELETE FROM agent.knowledge_edges 
                            WHERE source_id = :node_id OR target_id = :node_id
                        """),
                        {"node_id": node.id}
                    )
                    
                    # Soft delete node
                    node.is_deleted = True
                    node.updated_at = datetime.utcnow()
                    deleted_count += 1
            
            await self.session.commit()
            
            return {
                "status": "success",
                "dataset_name": dataset_name,
                "deleted_nodes": deleted_count,
            }
            
        except Exception as e:
            logger.exception(f"Failed to delete dataset {dataset_name}")
            return {
                "status": "error",
                "error": str(e),
                "deleted_nodes": deleted_count,
            }
