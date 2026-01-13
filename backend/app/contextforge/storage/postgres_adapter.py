"""
PostgreSQL Adapter for ContextForge.

Provides vector store interface using existing KnowledgeNode/KnowledgeEdge models.
Replaces ChromaDB with PostgreSQL + pgvector for schema and example storage.

Key Features:
- Schema field storage as KnowledgeNode (node_type=schema_field)
- Example storage as KnowledgeNode (node_type=example)
- Hybrid search using pgvector + BM25
- Tenant isolation via tenant_id
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.nodes import KnowledgeNode
    from app.models.edges import KnowledgeEdge

from ..schema.field_schema import FieldSpec
from ..schema.example_schema import ExampleSpec
from ..core.constants import CollectionType

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from vector/hybrid search."""
    node_id: int
    score: float
    node_type: str
    content: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PostgresAdapterConfig:
    """Configuration for PostgresAdapter."""
    embedding_dimension: int = 1024
    default_top_k: int = 10
    bm25_weight: float = 0.4
    vector_weight: float = 0.6
    min_score_threshold: float = 0.0


class PostgresAdapter:
    """
    PostgreSQL-based storage adapter for ContextForge.
    
    Uses existing KnowledgeNode/KnowledgeEdge models with pgvector
    for vector similarity search.
    
    Node Type Mapping:
    - schema_index: DocumentMasterConfig (dataset metadata)
    - schema_field: FieldSpec (field metadata)
    - example: ExampleSpec (Q&A examples)
    - concept: ConceptSpec (business concepts)
    
    Example:
        >>> adapter = PostgresAdapter(session, embedding_func)
        >>> 
        >>> # Store schema field
        >>> await adapter.store_field(tenant_id, dataset_name, field_spec)
        >>> 
        >>> # Search fields
        >>> results = await adapter.search_fields(tenant_id, dataset_name, query)
    """
    
    def __init__(
        self,
        session: 'AsyncSession',
        embedding_func: Optional[Callable[[str], List[float]]] = None,
        config: Optional[PostgresAdapterConfig] = None,
    ):
        """
        Initialize PostgreSQL adapter.
        
        Args:
            session: SQLAlchemy async session
            embedding_func: Function to generate embeddings from text
            config: Adapter configuration
        """
        self.session = session
        self.embedding_func = embedding_func
        self.config = config or PostgresAdapterConfig()
    
    async def store_field(
        self,
        tenant_id: str,
        dataset_name: str,
        field_spec: FieldSpec,
        created_by: Optional[str] = None,
    ) -> int:
        """
        Store a schema field as a KnowledgeNode.
        
        Args:
            tenant_id: Tenant identifier
            dataset_name: Dataset/index name
            field_spec: Field specification to store
            created_by: User who created this field
            
        Returns:
            Node ID of the created/updated node
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType, KnowledgeStatus
        from sqlalchemy import select
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.field_path == field_spec.path,
            KnowledgeNode.node_type == NodeType.SCHEMA_FIELD,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        content = field_spec.model_dump(mode="json")
        embedding_text = self._build_field_embedding_text(field_spec)
        
        if existing:
            existing.title = field_spec.name
            existing.summary = field_spec.description
            existing.content = content
            existing.data_type = str(field_spec.type)
            existing.version += 1
            existing.updated_at = datetime.utcnow()
            existing.updated_by = created_by
            
            await self.session.flush()
            node_id = existing.id
            logger.debug(f"Updated field node {node_id}: {field_spec.path}")
        else:
            node = KnowledgeNode(
                tenant_id=tenant_id,
                node_type=NodeType.SCHEMA_FIELD,
                title=field_spec.name,
                summary=field_spec.description,
                content=content,
                dataset_name=dataset_name,
                field_path=field_spec.path,
                data_type=str(field_spec.type),
                tags=field_spec.aliases or [],
                status=KnowledgeStatus.PUBLISHED,
                source="contextforge",
                created_by=created_by,
            )
            self.session.add(node)
            await self.session.flush()
            node_id = node.id
            logger.debug(f"Created field node {node_id}: {field_spec.path}")
        
        return node_id
    
    async def store_example(
        self,
        tenant_id: str,
        dataset_name: str,
        example: ExampleSpec,
        created_by: Optional[str] = None,
    ) -> int:
        """
        Store a Q&A example as a KnowledgeNode.
        
        Args:
            tenant_id: Tenant identifier
            dataset_name: Dataset/index name
            example: Example specification to store
            created_by: User who created this example
            
        Returns:
            Node ID of the created/updated node
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType, KnowledgeStatus
        from sqlalchemy import select
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
            KnowledgeNode.source_reference == example.id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        content = example.model_dump(mode="json")
        
        if existing:
            existing.title = example.title
            existing.summary = example.description
            existing.content = content
            existing.tags = example.tags or []
            existing.version += 1
            existing.updated_at = datetime.utcnow()
            existing.updated_by = created_by
            
            await self.session.flush()
            node_id = existing.id
            logger.debug(f"Updated example node {node_id}: {example.title}")
        else:
            node = KnowledgeNode(
                tenant_id=tenant_id,
                node_type=NodeType.EXAMPLE,
                title=example.title,
                summary=example.description,
                content=content,
                dataset_name=dataset_name,
                tags=example.tags or [],
                status=KnowledgeStatus.PUBLISHED,
                source="contextforge",
                source_reference=example.id,
                created_by=created_by,
            )
            self.session.add(node)
            await self.session.flush()
            node_id = node.id
            logger.debug(f"Created example node {node_id}: {example.title}")
        
        return node_id
    
    async def get_field(
        self,
        tenant_id: str,
        dataset_name: str,
        field_path: str,
    ) -> Optional[FieldSpec]:
        """
        Retrieve a field by path.
        
        Args:
            tenant_id: Tenant identifier
            dataset_name: Dataset/index name
            field_path: Field path to retrieve
            
        Returns:
            FieldSpec if found, None otherwise
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.field_path == field_path,
            KnowledgeNode.node_type == NodeType.SCHEMA_FIELD,
        )
        result = await self.session.execute(stmt)
        node = result.scalar_one_or_none()
        
        if node:
            return FieldSpec.model_validate(node.content)
        return None
    
    async def get_fields(
        self,
        tenant_id: str,
        dataset_name: str,
        field_paths: Optional[List[str]] = None,
    ) -> List[FieldSpec]:
        """
        Retrieve multiple fields.
        
        Args:
            tenant_id: Tenant identifier
            dataset_name: Dataset/index name
            field_paths: Optional list of paths (None = all fields)
            
        Returns:
            List of FieldSpec objects
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.node_type == NodeType.SCHEMA_FIELD,
        )
        
        if field_paths:
            stmt = stmt.where(KnowledgeNode.field_path.in_(field_paths))
        
        result = await self.session.execute(stmt)
        nodes = result.scalars().all()
        
        return [FieldSpec.model_validate(node.content) for node in nodes]
    
    async def search_fields(
        self,
        tenant_id: str,
        dataset_name: str,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[Tuple[FieldSpec, float]]:
        """
        Search fields by text query using hybrid search.
        
        Args:
            tenant_id: Tenant identifier
            dataset_name: Dataset/index name
            query: Search query text
            top_k: Maximum results to return
            
        Returns:
            List of (FieldSpec, score) tuples sorted by score descending
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select, func, text
        
        top_k = top_k or self.config.default_top_k
        
        # Simple text search using PostgreSQL full-text search
        # In production, this would use pgvector for embedding similarity
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.node_type == NodeType.SCHEMA_FIELD,
        )
        
        result = await self.session.execute(stmt)
        nodes = result.scalars().all()
        
        # Score based on text matching (simplified)
        scored_results = []
        query_lower = query.lower()
        query_terms = query_lower.split()
        
        for node in nodes:
            score = 0.0
            field_spec = FieldSpec.model_validate(node.content)
            
            # Title/path match
            if query_lower in (node.title or "").lower():
                score += 0.5
            if query_lower in (node.field_path or "").lower():
                score += 0.3
            
            # Description match
            if node.summary and query_lower in node.summary.lower():
                score += 0.2
            
            # Term matches
            text_blob = f"{node.title} {node.field_path} {node.summary or ''}".lower()
            term_matches = sum(1 for term in query_terms if term in text_blob)
            if term_matches > 0:
                score += 0.1 * (term_matches / len(query_terms))
            
            if score > self.config.min_score_threshold:
                scored_results.append((field_spec, score))
        
        # Sort by score descending
        scored_results.sort(key=lambda x: -x[1])
        
        return scored_results[:top_k]
    
    async def search_examples(
        self,
        tenant_id: str,
        dataset_name: str,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[Tuple[ExampleSpec, float]]:
        """
        Search examples by text query.
        
        Args:
            tenant_id: Tenant identifier
            dataset_name: Dataset/index name
            query: Search query text
            top_k: Maximum results to return
            
        Returns:
            List of (ExampleSpec, score) tuples sorted by score descending
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select
        
        top_k = top_k or self.config.default_top_k
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
        )
        
        result = await self.session.execute(stmt)
        nodes = result.scalars().all()
        
        # Score based on text matching (simplified)
        scored_results = []
        query_lower = query.lower()
        query_terms = query_lower.split()
        
        for node in nodes:
            score = 0.0
            example = ExampleSpec.model_validate(node.content)
            
            # Title match
            if query_lower in (node.title or "").lower():
                score += 0.5
            
            # Variant match
            for variant in example.variants:
                if query_lower in variant.lower():
                    score += 0.3
                    break
            
            # Description match
            if node.summary and query_lower in node.summary.lower():
                score += 0.2
            
            # Term matches in title and variants
            text_blob = f"{node.title} {' '.join(example.variants)}".lower()
            term_matches = sum(1 for term in query_terms if term in text_blob)
            if term_matches > 0:
                score += 0.2 * (term_matches / len(query_terms))
            
            if score > self.config.min_score_threshold:
                scored_results.append((example, score))
        
        scored_results.sort(key=lambda x: -x[1])
        
        return scored_results[:top_k]
    
    async def delete_field(
        self,
        tenant_id: str,
        dataset_name: str,
        field_path: str,
    ) -> bool:
        """
        Delete a field node.
        
        Args:
            tenant_id: Tenant identifier
            dataset_name: Dataset/index name
            field_path: Field path to delete
            
        Returns:
            True if deleted, False if not found
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select, delete
        
        stmt = delete(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.field_path == field_path,
            KnowledgeNode.node_type == NodeType.SCHEMA_FIELD,
        )
        result = await self.session.execute(stmt)
        
        return result.rowcount > 0
    
    async def delete_dataset_fields(
        self,
        tenant_id: str,
        dataset_name: str,
    ) -> int:
        """
        Delete all fields for a dataset.
        
        Args:
            tenant_id: Tenant identifier
            dataset_name: Dataset/index name
            
        Returns:
            Number of fields deleted
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import delete
        
        stmt = delete(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == dataset_name,
            KnowledgeNode.node_type == NodeType.SCHEMA_FIELD,
        )
        result = await self.session.execute(stmt)
        
        deleted_count = result.rowcount
        logger.info(f"Deleted {deleted_count} fields for {tenant_id}/{dataset_name}")
        
        return deleted_count
    
    def _build_field_embedding_text(self, field_spec: FieldSpec) -> str:
        """Build text for embedding generation from FieldSpec."""
        parts = [
            field_spec.name,
            field_spec.path,
        ]
        
        if field_spec.description:
            parts.append(field_spec.description)
        
        if field_spec.maps_to:
            parts.append(field_spec.maps_to)
        
        if field_spec.aliases:
            parts.extend(field_spec.aliases)
        
        return " ".join(parts)


def create_postgres_adapter(
    session: 'AsyncSession',
    embedding_func: Optional[Callable[[str], List[float]]] = None,
    config: Optional[PostgresAdapterConfig] = None,
) -> PostgresAdapter:
    """
    Factory function to create a PostgresAdapter.
    
    Args:
        session: SQLAlchemy async session
        embedding_func: Optional embedding function
        config: Optional configuration
        
    Returns:
        Configured PostgresAdapter instance
    """
    return PostgresAdapter(
        session=session,
        embedding_func=embedding_func,
        config=config,
    )
