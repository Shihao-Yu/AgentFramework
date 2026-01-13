"""
Hybrid Example Retrieval for ContextForge.

Combines:
1. Graph-based retrieval (concept/field/value linkage via edges)
2. Vector-based retrieval (semantic similarity via embeddings)
3. Keyword-based retrieval (variant matching via graph)

This module provides the HybridExampleRetriever class which fuses
all three retrieval signals for optimal example selection.

Example:
    >>> retriever = HybridExampleRetriever(schema_graph, vector_store)
    >>> examples = retriever.retrieve(
    ...     question="Show pending orders",
    ...     matched_concepts=["order", "status"],
    ...     matched_fields=["orders.status"],
    ...     matched_values=[("orders.status", "P")],
    ... )
    >>> for ex in examples:
    ...     print(f"{ex.example['title']} (score: {ex.combined_score:.2f})")
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from ..schema.example_schema import ExampleSpec, ExampleContent

if TYPE_CHECKING:
    from ..graph.schema_graph import SchemaGraph

logger = logging.getLogger(__name__)


# Simple keyword extraction without nltk dependency
def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    """
    Extract keywords from text.
    
    Simple implementation without nltk - splits on word boundaries,
    removes common stopwords and short words.
    """
    # Common English stopwords
    stopwords = {
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
        'it', 'its', 'this', 'that', 'these', 'those', 'what', 'which',
        'who', 'whom', 'whose', 'when', 'where', 'why', 'how', 'all', 'each',
        'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
        'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
        'also', 'now', 'show', 'me', 'get', 'find', 'list', 'give', 'i', 'my',
    }
    
    # Extract words
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    
    # Filter
    keywords = [
        w for w in words
        if len(w) >= min_length and w not in stopwords
    ]
    
    # Deduplicate while preserving order
    seen = set()
    result = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    
    return result


@dataclass
class ExampleMatch:
    """
    Scored example match from hybrid retrieval.
    
    Combines scores from multiple retrieval signals and provides
    a unified combined_score for ranking.
    """
    
    example: Dict[str, Any]  # Example data from graph
    
    # Component scores (0-1 range)
    concept_score: float = 0.0    # From DEMONSTRATES edges
    field_score: float = 0.0      # From USES_FIELD edges
    value_score: float = 0.0      # From USES_VALUE edges
    keyword_score: float = 0.0    # From variant keyword match
    vector_score: float = 0.0     # From embedding similarity
    
    # Match details for debugging
    matched_concepts: List[str] = field(default_factory=list)
    matched_fields: List[str] = field(default_factory=list)
    matched_values: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)
    
    @property
    def combined_score(self) -> float:
        """
        Weighted combination of all scores.
        
        Weights are tuned for optimal relevance:
        - Concept: 30% (semantic alignment)
        - Vector: 25% (semantic similarity)
        - Field: 20% (structural alignment)
        - Value: 15% (exact data matching)
        - Keyword: 10% (variant matching)
        """
        return (
            0.30 * self.concept_score +
            0.25 * self.vector_score +
            0.20 * self.field_score +
            0.15 * self.value_score +
            0.10 * self.keyword_score
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            **self.example,
            "scores": {
                "combined": round(self.combined_score, 3),
                "concept": round(self.concept_score, 3),
                "field": round(self.field_score, 3),
                "value": round(self.value_score, 3),
                "keyword": round(self.keyword_score, 3),
                "vector": round(self.vector_score, 3),
            },
            "match_details": {
                "concepts": self.matched_concepts,
                "fields": self.matched_fields,
                "values": self.matched_values,
                "keywords": self.matched_keywords,
            },
        }
    
    def to_example_spec(self) -> ExampleSpec:
        """Convert to ExampleSpec for backward compatibility."""
        ex = self.example
        return ExampleSpec(
            id=ex.get("id", ""),
            title=ex.get("title", ""),
            description=ex.get("description"),
            variants=ex.get("variants", []),
            content=ExampleContent(
                query=ex.get("query", ""),
                query_type=ex.get("query_type", "sql"),
                explanation=ex.get("explanation"),
            ),
            linked_concepts=ex.get("linked_concepts", []),
            linked_fields=ex.get("linked_fields", []),
            linked_values=ex.get("linked_values", {}),
            additional_context=ex.get("additional_context"),
            verified=ex.get("verified", False),
            source=ex.get("source", "graph"),
            tags=ex.get("tags", []),
            usage_count=ex.get("usage_count", 0),
        )


@dataclass
class ExampleRetrievalConfig:
    """Configuration for hybrid example retrieval."""
    
    # Score weights (should sum to 1.0)
    concept_weight: float = 0.30
    field_weight: float = 0.20
    value_weight: float = 0.15
    keyword_weight: float = 0.10
    vector_weight: float = 0.25
    
    # Retrieval limits
    max_examples: int = 5
    max_candidates: int = 20  # Candidates before final ranking
    
    # Thresholds
    min_combined_score: float = 0.2  # Minimum score to include
    
    # Feature toggles
    enable_vector_search: bool = True
    enable_keyword_search: bool = True
    enable_graph_search: bool = True


class HybridExampleRetriever:
    """
    Hybrid example retrieval combining graph and vector search.
    
    Retrieval Flow:
    1. Graph Search: Find examples linked to matched concepts/fields/values
    2. Keyword Search: Find examples whose variants match question keywords
    3. Vector Search: Find semantically similar examples (if enabled)
    4. Fusion: Combine scores and rank
    
    Example:
        >>> from contextforge.graph import SchemaGraph
        >>> graph = SchemaGraph()
        >>> graph.load_from_yaml(Path("schema.yaml"))
        >>> 
        >>> retriever = HybridExampleRetriever(graph)
        >>> examples = retriever.retrieve(
        ...     question="Show pending orders",
        ...     matched_concepts=["order", "status"],
        ...     matched_fields=["orders.status"],
        ...     matched_values=[("orders.status", "P")],
        ... )
    """
    
    def __init__(
        self,
        schema_graph: 'SchemaGraph',
        vector_store: Optional[Any] = None,
        embedding_func: Optional[Callable[[str], List[float]]] = None,
        config: Optional[ExampleRetrievalConfig] = None,
    ):
        """
        Initialize the hybrid example retriever.
        
        Args:
            schema_graph: Loaded SchemaGraph with examples
            vector_store: Optional vector store for semantic search
            embedding_func: Optional function to generate embeddings
            config: Retrieval configuration
        """
        self.graph = schema_graph
        self.vector_store = vector_store
        self.embedding_func = embedding_func
        self.config = config or ExampleRetrievalConfig()
    
    def retrieve(
        self,
        question: str,
        matched_concepts: List[str],
        matched_fields: List[str],
        matched_values: List[Tuple[str, str]],
        question_keywords: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
        document_name: Optional[str] = None,
    ) -> List[ExampleMatch]:
        """
        Retrieve examples using hybrid approach.
        
        Args:
            question: User's natural language question
            matched_concepts: Concepts found during schema retrieval
            matched_fields: Fields found during schema retrieval
            matched_values: (field, value) pairs found during retrieval
            question_keywords: Pre-extracted keywords (optional)
            tenant_id: For vector store scoping
            document_name: For vector store scoping
        
        Returns:
            List of ExampleMatch objects, sorted by combined score
        """
        # Collect all candidate examples with their scores
        candidates: Dict[str, ExampleMatch] = {}
        
        if self.config.enable_graph_search:
            # 1. Graph-based: Concept linkage
            self._score_by_concepts(matched_concepts, candidates)
            
            # 2. Graph-based: Field linkage
            self._score_by_fields(matched_fields, candidates)
            
            # 3. Graph-based: Value linkage
            self._score_by_values(matched_values, candidates)
        
        # 4. Keyword-based: Variant matching
        if self.config.enable_keyword_search:
            keywords = question_keywords or extract_keywords(question)
            self._score_by_keywords(keywords, candidates)
        
        # 5. Vector-based: Semantic similarity
        if self.config.enable_vector_search and self.vector_store:
            self._score_by_vector(
                question, tenant_id, document_name, candidates
            )
        
        # Filter and sort by combined score
        results = [
            match for match in candidates.values()
            if match.combined_score >= self.config.min_combined_score
        ]
        results.sort(key=lambda x: -x.combined_score)
        
        logger.info(
            f"Hybrid example retrieval: {len(candidates)} candidates -> "
            f"{len(results)} above threshold -> returning top {self.config.max_examples}"
        )
        
        return results[:self.config.max_examples]
    
    def _score_by_concepts(
        self,
        concepts: List[str],
        candidates: Dict[str, ExampleMatch],
    ) -> None:
        """Score examples by concept linkage."""
        if not concepts:
            return
        
        # Check if graph has the method
        if not hasattr(self.graph, 'get_examples_for_concepts'):
            logger.debug("SchemaGraph does not have get_examples_for_concepts method")
            return
        
        examples_by_concept = self.graph.get_examples_for_concepts(concepts)
        
        for concept, examples in examples_by_concept.items():
            for ex_data in examples:
                ex_id = ex_data.get("id", "")
                if not ex_id:
                    continue
                
                if ex_id not in candidates:
                    candidates[ex_id] = ExampleMatch(example=ex_data)
                
                match = candidates[ex_id]
                match.matched_concepts.append(concept)
                # Score increases with more concept matches
                match.concept_score = min(
                    1.0,
                    len(match.matched_concepts) / max(len(concepts), 1)
                )
    
    def _score_by_fields(
        self,
        fields: List[str],
        candidates: Dict[str, ExampleMatch],
    ) -> None:
        """Score examples by field linkage."""
        if not fields:
            return
        
        # Check if graph has the method
        if not hasattr(self.graph, 'get_examples_for_fields'):
            logger.debug("SchemaGraph does not have get_examples_for_fields method")
            return
        
        examples_by_field = self.graph.get_examples_for_fields(fields)
        
        for field_path, examples in examples_by_field.items():
            for ex_data in examples:
                ex_id = ex_data.get("id", "")
                if not ex_id:
                    continue
                
                if ex_id not in candidates:
                    candidates[ex_id] = ExampleMatch(example=ex_data)
                
                match = candidates[ex_id]
                match.matched_fields.append(field_path)
                match.field_score = min(
                    1.0,
                    len(match.matched_fields) / max(len(fields), 1)
                )
    
    def _score_by_values(
        self,
        field_values: List[Tuple[str, str]],
        candidates: Dict[str, ExampleMatch],
    ) -> None:
        """Score examples by value linkage."""
        if not field_values:
            return
        
        # Check if graph has the method
        if not hasattr(self.graph, 'get_examples_for_values'):
            logger.debug("SchemaGraph does not have get_examples_for_values method")
            return
        
        examples = self.graph.get_examples_for_values(field_values)
        
        for ex_data in examples:
            ex_id = ex_data.get("id", "")
            if not ex_id:
                continue
            
            if ex_id not in candidates:
                candidates[ex_id] = ExampleMatch(example=ex_data)
            
            match = candidates[ex_id]
            # Check which values matched
            ex_values = ex_data.get("linked_values", {})
            for field_path, value in field_values:
                if ex_values.get(field_path, "").lower() == value.lower():
                    match.matched_values.append(f"{field_path}={value}")
            
            match.value_score = min(
                1.0,
                len(match.matched_values) / max(len(field_values), 1)
            )
    
    def _score_by_keywords(
        self,
        keywords: List[str],
        candidates: Dict[str, ExampleMatch],
    ) -> None:
        """Score examples by variant keyword matching."""
        if not keywords:
            return
        
        # Check if graph has the method
        if not hasattr(self.graph, 'get_examples_by_keywords'):
            logger.debug("SchemaGraph does not have get_examples_by_keywords method")
            return
        
        keyword_matches = self.graph.get_examples_by_keywords(keywords)
        
        for ex_data, match_count in keyword_matches:
            ex_id = ex_data.get("id", "")
            if not ex_id:
                continue
            
            if ex_id not in candidates:
                candidates[ex_id] = ExampleMatch(example=ex_data)
            
            match = candidates[ex_id]
            match.keyword_score = min(1.0, match_count / max(len(keywords), 1))
            # Approximate which keywords matched
            match.matched_keywords = keywords[:match_count]
    
    def _score_by_vector(
        self,
        question: str,
        tenant_id: Optional[str],
        document_name: Optional[str],
        candidates: Dict[str, ExampleMatch],
    ) -> None:
        """Score examples by vector similarity."""
        if not self.vector_store:
            return
        
        try:
            # Get vector-similar examples from store
            # Try different method signatures for compatibility
            vector_results = []
            
            if hasattr(self.vector_store, 'get_similar_examples'):
                vector_results = self.vector_store.get_similar_examples(
                    tenant_id=tenant_id,
                    document_name=document_name,
                    question=question,
                    top_n=self.config.max_candidates,
                )
            elif hasattr(self.vector_store, 'get_similar_qa_examples'):
                vector_results = self.vector_store.get_similar_qa_examples(
                    tenant_id=tenant_id,
                    document_name=document_name,
                    question=question,
                    top_n=self.config.max_candidates,
                )
            
            for i, ex in enumerate(vector_results):
                # Handle both ExampleSpec and dict formats
                if hasattr(ex, 'id'):
                    ex_id = ex.id
                    ex_data = {
                        "id": ex.id,
                        "title": ex.title if hasattr(ex, 'title') else ex.question,
                        "query": ex.content.query if hasattr(ex, 'content') else ex.query,
                        "query_type": ex.content.query_type if hasattr(ex, 'content') else getattr(ex, 'query_type', 'sql'),
                    }
                elif isinstance(ex, dict):
                    ex_id = ex.get('id', '')
                    ex_data = ex
                else:
                    continue
                
                # Calculate similarity score (rank-based if no explicit score)
                similarity = 1.0 - (i / max(len(vector_results), 1))
                
                if ex_id in candidates:
                    candidates[ex_id].vector_score = similarity
                else:
                    candidates[ex_id] = ExampleMatch(
                        example=ex_data,
                        vector_score=similarity,
                    )
        
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
