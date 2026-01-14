"""
Graph-based Context Retriever for Query Generation

Retrieves context from SchemaGraph using multiple search strategies:
- Concept-based: keyword -> concept -> fields
- Field-based: field path match -> expansion
- Hybrid: concept first, vector fallback
- Fusion: parallel search with weighted scoring

Integrates with the existing RetrievalContext format for compatibility
with the QueryGenerationPipeline.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..graph.bm25_index import BM25FieldIndex
from ..graph.schema_graph import SchemaGraph, SearchResult
from ..graph.value_index import ValueSynonymIndex
from ..schema.field_schema import FieldSpec
from .context import RetrievalContext
from .example_retriever import (
    HybridExampleRetriever,
    ExampleMatch,
    ExampleRetrievalConfig,
    extract_keywords,
)


class RetrievalStrategy(str, Enum):
    """Search strategy for context retrieval"""
    CONCEPT = "concept"    # keyword -> concept -> fields
    FIELD = "field"        # keyword -> field path match -> expand
    HYBRID = "hybrid"      # concept first, field/vector fallback
    FUSION = "fusion"      # parallel search with weighted scoring


logger = logging.getLogger(__name__)


# Query-related keywords that indicate operations
OPERATION_KEYWORDS = {
    'count': 'aggregation',
    'sum': 'aggregation',
    'average': 'aggregation',
    'avg': 'aggregation',
    'max': 'aggregation',
    'min': 'aggregation',
    'total': 'aggregation',
    'group': 'aggregation',
    'filter': 'filtering',
    'where': 'filtering',
    'with': 'filtering',
    'without': 'filtering',
    'greater': 'comparison',
    'less': 'comparison',
    'more': 'comparison',
    'fewer': 'comparison',
    'between': 'range',
    'last': 'time',
    'recent': 'time',
    'today': 'time',
    'yesterday': 'time',
    'week': 'time',
    'month': 'time',
    'year': 'time',
    'order': 'sorting',
    'sort': 'sorting',
    'top': 'limit',
    'first': 'limit',
    'limit': 'limit',
}


@dataclass
class ScoringConfig:
    """
    Centralized scoring weights for retrieval.

    All tunable scores in one place for easy adjustment.
    Can be loaded from YAML config or set programmatically.
    """
    # === Match Type Scores ===
    # How confident are we in different types of matches?
    exact_canonical_match: float = 1.0    # "pending" matches canonical "pending"
    synonym_match: float = 0.9            # "waiting" matches synonym of "pending"
    alias_match: float = 0.85             # Concept alias match
    fuzzy_match: float = 0.7              # Fuzzy string similarity match
    field_path_match: float = 0.6         # Keyword found in field path

    # === Fusion Weights ===
    # How much weight does each search strategy contribute?
    # These should sum to 1.0 for normalized scoring
    concept_weight: float = 0.30          # Graph concept traversal
    value_weight: float = 0.35            # Value synonym matching
    pronoun_weight: float = 0.15          # Pronoun reference matching
    bm25_weight: float = 0.20             # BM25 text search

    # === Thresholds ===
    min_fusion_score: float = 0.1         # Minimum score to include in results
    high_confidence_threshold: float = 0.8  # Score above this is "high confidence"
    llm_context_threshold: float = 0.6    # Minimum score to send to LLM context

    def validate(self) -> None:
        """Validate that weights are sensible"""
        total = self.concept_weight + self.value_weight + self.pronoun_weight + self.bm25_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Fusion weights should sum to 1.0, got {total}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScoringConfig":
        """Create from dictionary (e.g., loaded from YAML)"""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class EndpointScoringConfig:
    """Configuration for endpoint relevance scoring.
    
    Scoring weights control how different match types contribute
    to the final endpoint score. Weights should sum to 1.0.
    
    Thresholds:
    - min_score_threshold: Very low bar to include in raw results (0.1)
    - llm_score_threshold: Higher bar for endpoints sent to LLM context (0.4)
    
    Only endpoints >= llm_score_threshold are considered "relevant" for LLM.
    """
    # Scoring weights
    concept_weight: float = 0.40   # Endpoint.maps_to matches a concept
    path_weight: float = 0.25      # Keywords appear in URL path segments
    param_weight: float = 0.20     # Matched params / total params ratio
    text_weight: float = 0.15      # Keywords in summary/description
    
    # Thresholds
    min_score_threshold: float = 0.1   # Minimum to include in results at all
    llm_score_threshold: float = 0.4   # Minimum to send to LLM context
    
    # Limits (applied AFTER threshold filtering)
    max_endpoints: int = 10        # Maximum endpoints to return
    
    def __post_init__(self):
        total = self.concept_weight + self.path_weight + self.param_weight + self.text_weight
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Endpoint scoring weights sum to {total}, not 1.0")


@dataclass
class EndpointMatch:
    """Scored endpoint match with relevance breakdown.
    
    Used for ranking endpoints by relevance to user query.
    """
    endpoint: Any  # EndpointSpec - use Any to avoid circular import
    score: float
    match_reasons: List[str] = field(default_factory=list)
    
    # Score breakdown (for debugging/tuning)
    concept_score: float = 0.0
    path_score: float = 0.0
    param_score: float = 0.0
    text_score: float = 0.0
    response_score: float = 0.0  # Bonus for response field matches
    
    def __repr__(self) -> str:
        return f"EndpointMatch({self.endpoint.method} {self.endpoint.path}, score={self.score:.2f})"


@dataclass
class GraphRetrievalConfig:
    """Configuration for graph-based retrieval"""
    # Search strategy (accepts string or enum)
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID

    # Limits
    max_fields: int = 30
    max_concepts: int = 5
    expansion_hops: int = 2

    # Matching thresholds
    fuzzy_threshold: float = 0.8
    min_keyword_length: int = 3

    # Fallback to vector search
    enable_vector_fallback: bool = True
    vector_top_k: int = 10

    # Parallel fusion components
    enable_value_search: bool = True
    enable_pronoun_search: bool = True
    enable_bm25_search: bool = True

    # Scoring configuration
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    
    # Endpoint scoring configuration (for REST API sources)
    endpoint_scoring: EndpointScoringConfig = field(default_factory=EndpointScoringConfig)

    def __post_init__(self):
        """Normalize strategy to enum (allows string input for convenience)"""
        if isinstance(self.strategy, str):
            try:
                self.strategy = RetrievalStrategy(self.strategy)
            except ValueError:
                raise ValueError(
                    f"Invalid strategy '{self.strategy}'. "
                    f"Valid options: {[s.value for s in RetrievalStrategy]}"
                )


class GraphContextRetriever:
    """
    Retrieves context from SchemaGraph for query generation.

    Combines:
    - Graph traversal (structural relationships)
    - Keyword matching (semantic concepts)
    - Optional vector search fallback

    Example:
        >>> graph = SchemaGraph()
        >>> graph.load_from_yaml(Path("schema.yaml"))
        >>> retriever = GraphContextRetriever(graph)
        >>> context = retriever.retrieve("Show me orders from last week")
        >>> print(f"Found {len(context.matched_fields)} relevant fields")
    """

    def __init__(
        self,
        schema_graph: SchemaGraph,
        vector_store: Optional[Any] = None,
        embedding_model: Optional[Any] = None,
        config: Optional[GraphRetrievalConfig] = None,
        value_index: Optional[ValueSynonymIndex] = None,
        bm25_index: Optional[BM25FieldIndex] = None,
    ):
        """
        Initialize the retriever.

        Args:
            schema_graph: Loaded SchemaGraph with indices, fields, concepts
            vector_store: Optional vector store for fallback search
            embedding_model: Optional embedding model for vector search
            config: Retrieval configuration
            value_index: Optional pre-built value index (auto-built if not provided)
            bm25_index: Optional pre-built BM25 index (auto-built if not provided)
        """
        self.graph = schema_graph
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.config = config or GraphRetrievalConfig()

        # Build value index from schema if not provided
        if value_index is not None:
            self.value_index = value_index
        elif schema_graph.schema is not None:
            self.value_index = ValueSynonymIndex()
            self.value_index.build_from_schema(schema_graph.schema)
        else:
            self.value_index = ValueSynonymIndex()  # Empty index

        # Build BM25 index from schema if not provided
        if bm25_index is not None:
            self.bm25_index = bm25_index
        elif schema_graph.schema is not None:
            self.bm25_index = BM25FieldIndex()
            self.bm25_index.build_from_schema(schema_graph.schema)
        else:
            self.bm25_index = BM25FieldIndex()  # Empty index
        
        # Initialize example retriever for hybrid example search
        self.example_retriever = HybridExampleRetriever(
            schema_graph=schema_graph,
            vector_store=vector_store,
            embedding_func=None,  # Will use vector_store's embedding
            config=ExampleRetrievalConfig(),
        )

    def retrieve(
        self,
        question: str,
        index_pattern: Optional[str] = None,
        strategy: Optional[Union[RetrievalStrategy, str]] = None,
        max_fields: Optional[int] = None,
        expansion_hops: Optional[int] = None,
        tenant_id: Optional[str] = None,
        document_name: Optional[str] = None,
    ) -> RetrievalContext:
        """
        Retrieve context for a natural language question.

        Strategies:
        - CONCEPT: keyword -> concept -> fields
        - FIELD: keyword -> field path match -> expand
        - HYBRID: try concept first, fall back to field/vector
        - FUSION: parallel search (concept + value + pronoun) with weighted scoring

        Args:
            question: Natural language question
            index_pattern: Optional index to scope search
            strategy: Override default strategy (enum or string)
            max_fields: Override max fields limit
            expansion_hops: Override expansion hops
            tenant_id: Optional tenant ID for vector store scoping
            document_name: Optional document name for vector store scoping

        Returns:
            RetrievalContext compatible with QueryGenerationPipeline
        """
        # Normalize strategy to enum if string passed
        if strategy is None:
            strategy = self.config.strategy
        elif isinstance(strategy, str):
            strategy = RetrievalStrategy(strategy)

        max_fields = max_fields or self.config.max_fields
        expansion_hops = expansion_hops or self.config.expansion_hops

        # Extract keywords from question
        keywords = self._extract_keywords_for_retrieval(question)
        operations = self._detect_operations(question)

        logger.debug(f"Extracted keywords: {keywords}")
        logger.debug(f"Detected operations: {operations}")

        # Execute search based on strategy
        if strategy == RetrievalStrategy.CONCEPT:
            result = self._concept_search(keywords, expansion_hops)
        elif strategy == RetrievalStrategy.FIELD:
            result = self._field_search(keywords, index_pattern, expansion_hops)
        elif strategy == RetrievalStrategy.FUSION:
            result = self._fusion_search(
                question, keywords, index_pattern, expansion_hops, max_fields
            )
        else:  # HYBRID (default)
            result = self._hybrid_search(
                keywords, index_pattern, expansion_hops, max_fields
            )

        # Apply index filter if specified
        if index_pattern:
            result = self._filter_by_index(result, index_pattern)

        # Limit results - sort by score (descending) to keep highest scoring fields
        field_scores = result.field_scores or {}
        sorted_fields = sorted(
            result.expanded_fields,
            key=lambda f: -field_scores.get(f, 0.0)
        )
        all_fields = sorted_fields[:max_fields]

        # Get field metadata
        field_metadata = self._get_field_metadata(all_fields, index_pattern)

        context = self._build_context(
            field_metadata=field_metadata,
            search_result=result,
            question=question,
            operations=operations,
            config={
                "strategy": strategy.value,
                "max_fields": max_fields,
                "expansion_hops": expansion_hops,
                "index_pattern": index_pattern,
            },
            tenant_id=tenant_id,
            document_name=document_name,
        )

        logger.info(
            f"Retrieved {context.field_count} fields for question "
            f"(strategy={strategy}, concepts={len(result.matched_concepts)})"
        )

        return context

    def retrieve_for_concepts(
        self,
        concepts: List[str],
        include_related: bool = True,
        max_hops: int = 1,
    ) -> RetrievalContext:
        """
        Retrieve context for explicit concept list.

        Useful when concepts are known ahead of time (e.g., from planning).

        Args:
            concepts: List of concept names to retrieve
            include_related: Also get fields from related concepts
            max_hops: Relationship hops to traverse

        Returns:
            RetrievalContext with fields mapped to these concepts
        """
        all_fields: Set[str] = set()
        all_concepts: List[Tuple[str, float]] = []
        adjacency: Dict[str, List[Tuple[str, str]]] = {}

        for concept in concepts:
            result = self.graph.find_fields_by_concept(
                concept,
                include_related=include_related,
                max_hops=max_hops,
            )
            all_fields.update(result.expanded_fields)
            all_concepts.extend(result.matched_concepts)
            adjacency.update(result.adjacency)

        # Get field metadata
        field_metadata = self._get_field_metadata(list(all_fields))

        # Build combined search result for context building
        combined = SearchResult(
            matched_concepts=list(set(all_concepts)),
            matched_fields=list(all_fields),
            expanded_fields=all_fields,
            adjacency=adjacency,
            traversal_path=[],
            hop_count=max_hops,
        )

        return self._build_context(
            field_metadata=field_metadata,
            search_result=combined,
            question="",
            operations=[],
            config={"mode": "explicit_concepts", "concepts": concepts},
        )

    def _extract_keywords_for_retrieval(self, question: str) -> List[str]:
        """
        Extract key terms from question for matching.

        Uses simple keyword extraction with stopword removal.
        
        Args:
            question: User's natural language question
        
        Returns:
            List of unique keywords with stopwords removed
        """
        return extract_keywords(
            question, 
            min_length=self.config.min_keyword_length,
        )

    def _detect_operations(self, question: str) -> List[str]:
        """Detect query operations from question keywords"""
        operations = set()
        question_lower = question.lower()

        for keyword, operation in OPERATION_KEYWORDS.items():
            if keyword in question_lower:
                operations.add(operation)

        return list(operations)

    def _concept_search(
        self,
        keywords: List[str],
        expansion_hops: int,
    ) -> SearchResult:
        """Search by matching keywords to concepts"""
        return self.graph.find_fields_by_keywords(
            keywords,
            fuzzy_threshold=self.config.fuzzy_threshold,
        )

    def _field_search(
        self,
        keywords: List[str],
        index_pattern: Optional[str],
        expansion_hops: int,
    ) -> SearchResult:
        """Search by matching keywords to field paths"""
        matched_fields: List[str] = []
        expanded_fields: Set[str] = set()

        # Get all fields from target index (or all indices)
        if index_pattern:
            all_paths = self.graph.get_all_index_fields(index_pattern)
        else:
            all_paths = list(self.graph._field_to_concepts.keys())

        # Match keywords to field paths
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for path in all_paths:
                if keyword_lower in path.lower():
                    matched_fields.append(path)

        # Expand each matched field
        for field_path in matched_fields:
            result = self.graph.find_related_fields(
                field_path,
                index_name=index_pattern,
                max_hops=expansion_hops,
            )
            expanded_fields.update(result.expanded_fields)

        return SearchResult(
            matched_concepts=[],
            matched_fields=list(set(matched_fields)),
            expanded_fields=expanded_fields,
            adjacency={},
            traversal_path=[],
            hop_count=expansion_hops,
        )

    def _hybrid_search(
        self,
        keywords: List[str],
        index_pattern: Optional[str],
        expansion_hops: int,
        max_fields: int,
    ) -> SearchResult:
        """
        Hybrid search: concept + value search, then field fallback.

        1. Try to match keywords to concepts AND value synonyms (parallel)
        2. If few results, also do field path matching
        3. If still few results, fall back to vector search
        """
        # Step 1a: Concept search
        concept_result = self._concept_search(keywords, expansion_hops)

        # Step 1b: Value synonym search (matches keywords like "pending" to field values)
        value_result = None
        if self.config.enable_value_search and self.value_index.has_values():
            value_result = self._value_search(keywords, expansion_hops)
            # Merge value search results into concept results
            if value_result.expanded_fields:
                concept_result = SearchResult(
                    matched_concepts=list(set(
                        concept_result.matched_concepts + value_result.matched_concepts
                    )),
                    matched_fields=list(set(
                        concept_result.matched_fields + value_result.matched_fields
                    )),
                    expanded_fields=concept_result.expanded_fields | value_result.expanded_fields,
                    adjacency={**concept_result.adjacency, **value_result.adjacency},
                    traversal_path=concept_result.traversal_path + value_result.traversal_path,
                    hop_count=concept_result.hop_count,
                    field_scores={
                        **(concept_result.field_scores or {}),
                        **(value_result.field_scores or {}),
                    },
                )

        # If we have enough fields, apply scores and return
        if len(concept_result.expanded_fields) >= max_fields // 2:
            # Get fields directly mapped to matched concepts (these should score 1.0)
            concept_direct_fields: Set[str] = set()
            for concept_name, _score in concept_result.matched_concepts:
                direct_fields = self.graph._concept_to_fields.get(concept_name, set())
                concept_direct_fields.update(direct_fields)

            # Compute field scores
            field_scores = {}
            for f in concept_result.matched_fields:
                field_scores[f] = 1.0
            for f in concept_direct_fields:
                field_scores[f] = 1.0
            for f in concept_result.expanded_fields:
                if f not in field_scores:
                    field_scores[f] = 0.5

            return SearchResult(
                matched_concepts=concept_result.matched_concepts,
                matched_fields=list(concept_direct_fields | set(concept_result.matched_fields)),
                expanded_fields=concept_result.expanded_fields,
                adjacency=concept_result.adjacency,
                traversal_path=concept_result.traversal_path,
                hop_count=concept_result.hop_count,
                field_scores=field_scores,
            )

        # Step 2: Field path search
        field_result = self._field_search(keywords, index_pattern, expansion_hops)

        # Merge results with scores
        merged_matched = list(set(
            concept_result.matched_fields + field_result.matched_fields
        ))
        merged_expanded = concept_result.expanded_fields | field_result.expanded_fields

        # Get fields directly mapped to matched concepts (these should score 1.0)
        concept_direct_fields: Set[str] = set()
        for concept_name, _score in concept_result.matched_concepts:
            direct_fields = self.graph._concept_to_fields.get(concept_name, set())
            concept_direct_fields.update(direct_fields)

        # Compute field scores:
        # - Fields directly matched via path or directly mapped to matched concepts: 1.0
        # - Fields expanded via graph traversal: 0.5
        field_scores = {}
        for f in merged_matched:
            field_scores[f] = 1.0
        for f in concept_direct_fields:
            field_scores[f] = 1.0  # Direct concept mapping = high confidence
        for f in merged_expanded:
            if f not in field_scores:
                field_scores[f] = 0.5

        merged = SearchResult(
            matched_concepts=concept_result.matched_concepts,
            matched_fields=merged_matched,
            expanded_fields=merged_expanded,
            adjacency={**concept_result.adjacency, **field_result.adjacency},
            traversal_path=concept_result.traversal_path + field_result.traversal_path,
            hop_count=expansion_hops,
            field_scores=field_scores,
        )

        # Step 3: Vector fallback if enabled and still not enough
        if (
            self.config.enable_vector_fallback
            and self.vector_store
            and len(merged.expanded_fields) < max_fields // 3
        ):
            vector_fields = self._vector_search(keywords, index_pattern)
            merged.expanded_fields.update(vector_fields)
            merged.matched_fields.extend(
                f for f in vector_fields if f not in merged.matched_fields
            )

        return merged

    def _vector_search(
        self,
        keywords: List[str],
        index_pattern: Optional[str],
    ) -> Set[str]:
        """Fallback to vector search for unmatched keywords"""
        if not self.vector_store:
            return set()

        # This is a placeholder - actual implementation depends on
        # the vector store interface being used
        logger.debug("Vector fallback not fully implemented")
        return set()

    # === FUSION SEARCH METHODS ===

    def _fusion_search(
        self,
        question: str,
        keywords: List[str],
        index_pattern: Optional[str],
        expansion_hops: int,
        max_fields: int,
    ) -> SearchResult:
        """
        Parallel fusion search with weighted scoring.

        Runs multiple search strategies in parallel and fuses results
        using configurable weights from ScoringConfig.

        Strategies:
        1. Concept search (graph traversal)
        2. Value search (value synonym matching)
        3. Pronoun search (pronoun -> concept mapping)
        4. BM25 search (optional text search)

        Args:
            question: Original question text (for pronoun detection)
            keywords: Extracted keywords for matching
            index_pattern: Optional index filter
            expansion_hops: Graph traversal depth
            max_fields: Maximum fields to return

        Returns:
            Fused SearchResult with weighted scoring
        """
        scoring = self.config.scoring
        results_with_weights: List[Tuple[SearchResult, float]] = []

        # 1. Concept search (always enabled)
        concept_result = self._concept_search(keywords, expansion_hops)
        results_with_weights.append((concept_result, scoring.concept_weight))

        # 2. Value synonym search
        if self.config.enable_value_search and self.value_index.has_values():
            value_result = self._value_search(keywords, expansion_hops)
            results_with_weights.append((value_result, scoring.value_weight))
        else:
            # Redistribute weight if disabled
            logger.debug("Value search disabled or no values indexed")

        # 3. Pronoun search
        if self.config.enable_pronoun_search and self.value_index.has_pronouns():
            pronoun_result = self._pronoun_search(question, expansion_hops)
            results_with_weights.append((pronoun_result, scoring.pronoun_weight))
        else:
            logger.debug("Pronoun search disabled or no pronouns indexed")

        # 4. BM25 text search
        if self.config.enable_bm25_search and self.bm25_index.has_documents():
            bm25_result = self._bm25_search(question, expansion_hops)
            results_with_weights.append((bm25_result, scoring.bm25_weight))
        else:
            logger.debug("BM25 search disabled or no documents indexed")

        # Fuse results with weighted scoring
        return self._fuse_results(results_with_weights, max_fields)

    def _value_search(
        self,
        keywords: List[str],
        expansion_hops: int,
    ) -> SearchResult:
        """
        Search by value synonym matching.

        Matches keywords against value_synonyms defined in:
        1. Field-level: Direct field path retrieval (highest precision)
        2. Concept-level: Concept -> fields expansion (broader coverage)

        e.g., "pending" -> Status field (field-level) or order_status concept (concept-level)

        Args:
            keywords: Keywords to match against values
            expansion_hops: Graph traversal for field expansion

        Returns:
            SearchResult with matched concepts and fields, with field_scores
        """
        scoring = self.config.scoring
        matched_concepts: List[Tuple[str, float]] = []
        matched_fields: Set[str] = set()
        field_scores: Dict[str, float] = {}  # Track scores per field
        value_info: Dict[str, str] = {}  # For debugging: keyword -> canonical

        for keyword in keywords:
            matches = self.value_index.lookup_value(keyword)
            for match in matches:
                # Calculate score based on match type
                score = match.get_score(
                    exact_score=scoring.exact_canonical_match,
                    synonym_score=scoring.synonym_match,
                )
                matched_concepts.append((match.concept_name, score))
                value_info[keyword] = match.canonical_value

                # CRITICAL FIX: For field-level value_synonyms, add the specific field directly
                # This ensures "pending" -> Status field, not just "purchaseorder" concept expansion
                if match.is_field_level() and match.field_path:
                    # Direct field match from field-level value_synonyms
                    matched_fields.add(match.field_path)
                    # Give field-level matches the full score (they're most precise)
                    current_score = field_scores.get(match.field_path, 0.0)
                    field_scores[match.field_path] = max(current_score, score)
                    logger.debug(
                        f"Field-level value match: '{keyword}' -> {match.field_path} "
                        f"(canonical: {match.canonical_value}, score: {score})"
                    )
                else:
                    # Concept-level value_synonyms: expand via concept graph
                    concept_fields = self.graph.find_fields_by_concept(
                        match.concept_name,
                        include_related=expansion_hops > 0,
                        max_hops=expansion_hops,
                    )
                    matched_fields.update(concept_fields.expanded_fields)
                    # Concept-level matches get slightly lower score (less precise)
                    concept_score = score * 0.8
                    for field in concept_fields.expanded_fields:
                        current_score = field_scores.get(field, 0.0)
                        field_scores[field] = max(current_score, concept_score)

        if value_info:
            logger.debug(f"Value matches: {value_info}")

        return SearchResult(
            matched_concepts=matched_concepts,
            matched_fields=list(matched_fields),
            expanded_fields=matched_fields,
            adjacency={},
            traversal_path=[f"value_search:{list(value_info.keys())}"],
            hop_count=expansion_hops,
            field_scores=field_scores,
        )

    def _pronoun_search(
        self,
        question: str,
        expansion_hops: int,
    ) -> SearchResult:
        """
        Search by pronoun references in question.

        Finds concepts whose related_pronouns appear in the question.
        e.g., "my orders" -> "my" matches requestor -> RequesterUser fields

        Args:
            question: Original question text
            expansion_hops: Graph traversal for field expansion

        Returns:
            SearchResult with pronoun-matched concepts and fields
        """
        found_pronouns = self.value_index.find_pronouns_in_text(question)

        if not found_pronouns:
            return SearchResult(
                matched_concepts=[],
                matched_fields=[],
                expanded_fields=set(),
                adjacency={},
                traversal_path=[],
                hop_count=0,
            )

        scoring = self.config.scoring
        matched_concepts: List[Tuple[str, float]] = []
        matched_fields: Set[str] = set()

        for pronoun, concept_names in found_pronouns.items():
            for concept_name in concept_names:
                # Pronoun matches get a distinct score
                matched_concepts.append((concept_name, scoring.alias_match))

                # Get fields mapped to this concept
                concept_fields = self.graph.find_fields_by_concept(
                    concept_name,
                    include_related=expansion_hops > 0,
                    max_hops=expansion_hops,
                )
                matched_fields.update(concept_fields.expanded_fields)

        logger.debug(f"Pronoun matches: {list(found_pronouns.keys())}")

        return SearchResult(
            matched_concepts=matched_concepts,
            matched_fields=list(matched_fields),
            expanded_fields=matched_fields,
            adjacency={},
            traversal_path=[f"pronoun_search:{list(found_pronouns.keys())}"],
            hop_count=expansion_hops,
        )

    def _bm25_search(
        self,
        question: str,
        expansion_hops: int,
        top_k: int = 15,
    ) -> SearchResult:
        """
        Search using BM25 text matching on field metadata.

        Matches the question against field paths, descriptions,
        aliases, and concept mappings using BM25 ranking.

        Args:
            question: Original question text
            expansion_hops: Graph traversal for field expansion
            top_k: Maximum fields from BM25 search

        Returns:
            SearchResult with BM25-matched fields
        """
        # Get top BM25 matches
        bm25_results = self.bm25_index.search(question, top_k=top_k)

        if not bm25_results:
            return SearchResult(
                matched_concepts=[],
                matched_fields=[],
                expanded_fields=set(),
                adjacency={},
                traversal_path=[],
                hop_count=0,
            )

        matched_fields: Set[str] = set()
        matched_concepts: List[Tuple[str, float]] = []

        # Collect matched fields and their concepts
        for result in bm25_results:
            matched_fields.add(result.field_path)

            # Try to find concept mapping for this field
            concepts = self.graph._field_to_concepts.get(result.field_path, [])
            for concept_name in concepts:
                # Normalize BM25 score to [0,1] range (using log normalization)
                # BM25 scores can vary widely, so we cap at reasonable values
                normalized_score = min(result.score / 10.0, 1.0)
                matched_concepts.append((concept_name, normalized_score))

        # Optionally expand fields
        expanded_fields = matched_fields.copy()
        if expansion_hops > 0:
            for field_path in list(matched_fields):
                related = self.graph.find_related_fields(
                    field_path,
                    max_hops=expansion_hops,
                )
                expanded_fields.update(related.expanded_fields)

        logger.debug(
            f"BM25 matches: {len(bm25_results)} fields, "
            f"top score={bm25_results[0].score:.2f}"
        )

        return SearchResult(
            matched_concepts=matched_concepts,
            matched_fields=list(matched_fields),
            expanded_fields=expanded_fields,
            adjacency={},
            traversal_path=[f"bm25_search:top_{len(bm25_results)}"],
            hop_count=expansion_hops,
        )

    def _fuse_results(
        self,
        results_with_weights: List[Tuple[SearchResult, float]],
        max_fields: int,
    ) -> SearchResult:
        """
        Combine multiple search results with weighted scoring.

        Each field accumulates scores from all strategies that found it.
        Final ranking is based on total weighted score.

        Args:
            results_with_weights: List of (SearchResult, weight) tuples
            max_fields: Maximum fields to return

        Returns:
            Fused SearchResult sorted by total score
        """
        scoring = self.config.scoring

        # Accumulate scores per field
        field_scores: Dict[str, float] = {}
        all_concepts: List[Tuple[str, float]] = []
        all_adjacency: Dict[str, List[Tuple[str, str]]] = {}
        traversal_paths: List[str] = []

        for result, weight in results_with_weights:
            # Accumulate field scores
            for field in result.expanded_fields:
                field_scores[field] = field_scores.get(field, 0.0) + weight

            # Collect concepts with their scores
            all_concepts.extend(result.matched_concepts)

            # Merge adjacency info
            all_adjacency.update(result.adjacency)

            # Collect traversal paths
            traversal_paths.extend(result.traversal_path)

        # Filter by minimum score threshold
        filtered_fields = {
            f: s for f, s in field_scores.items()
            if s >= scoring.min_fusion_score
        }

        # Sort by score (descending) and limit
        sorted_fields = sorted(
            filtered_fields.items(),
            key=lambda x: -x[1],
        )
        top_fields = [f for f, _ in sorted_fields[:max_fields]]

        # Preserve scores for top fields
        top_field_scores = {f: s for f, s in sorted_fields[:max_fields]}

        # Deduplicate concepts while preserving highest score
        concept_best: Dict[str, float] = {}
        for concept, score in all_concepts:
            if concept not in concept_best or score > concept_best[concept]:
                concept_best[concept] = score
        unique_concepts = [(c, s) for c, s in concept_best.items()]

        logger.debug(
            f"Fusion results: {len(top_fields)} fields from {len(results_with_weights)} strategies"
        )

        return SearchResult(
            matched_concepts=unique_concepts,
            matched_fields=top_fields,
            expanded_fields=set(top_fields),
            adjacency=all_adjacency,
            traversal_path=traversal_paths,
            hop_count=max(r.hop_count for r, _ in results_with_weights) if results_with_weights else 0,
            field_scores=top_field_scores,
        )

    def _filter_by_index(
        self,
        result: SearchResult,
        index_pattern: str,
    ) -> SearchResult:
        """Filter result to only include fields from specified index"""
        index_fields = set(self.graph.get_all_index_fields(index_pattern))

        return SearchResult(
            matched_concepts=result.matched_concepts,
            matched_fields=[f for f in result.matched_fields if f in index_fields],
            expanded_fields=result.expanded_fields & index_fields,
            adjacency=result.adjacency,
            traversal_path=result.traversal_path,
            hop_count=result.hop_count,
        )

    def _get_field_metadata(
        self,
        field_paths: List[str],
        index_name: Optional[str] = None,
    ) -> List[FieldSpec]:
        """
        Convert field paths to FieldSpec for pipeline compatibility.

        Args:
            field_paths: List of field paths to retrieve
            index_name: Optional index to scope the lookup

        Returns:
            List of FieldSpec for pipeline use
        """
        # Get typed FieldSpec objects from graph
        return self.graph.get_field_metadata(field_paths, index_name)

    def _build_context(
        self,
        field_metadata: List[FieldSpec],
        search_result: SearchResult,
        question: str,
        operations: List[str],
        config: Dict[str, Any],
        tenant_id: Optional[str] = None,
        document_name: Optional[str] = None,
    ) -> RetrievalContext:
        """
        Build RetrievalContext from search results.
        
        Now integrates hybrid example retrieval using the HybridExampleRetriever
        for graph-based + vector-based example matching.
        
        Args:
            field_metadata: Retrieved field metadata
            search_result: SearchResult from graph/fusion search
            question: User's natural language question
            operations: Detected operations (aggregation, filtering, etc.)
            config: Configuration dict for context
            tenant_id: Optional tenant ID for vector store scoping
            document_name: Optional document name for vector store scoping
        
        Returns:
            RetrievalContext with fields, examples, endpoints
        """
        # Separate seed fields (directly matched) from expanded
        seed_names = set(search_result.matched_fields)
        seed_fields = [f for f in field_metadata if f.path in seed_names]
        expanded_fields = [f for f in field_metadata if f.path not in seed_names]

        # Convert adjacency to expected format
        field_adjacency = {}
        for concept, relations in search_result.adjacency.items():
            for related, edge_type in relations:
                if concept not in field_adjacency:
                    field_adjacency[concept] = []
                field_adjacency[concept].append((related, edge_type))

        keywords = self._extract_keywords_for_retrieval(question)
        
        # Build concept scores dict from search result
        concept_scores = {name: score for name, score in search_result.matched_concepts}

        # Find and RANK REST API endpoints by relevance
        matched_endpoints = self._find_matched_endpoints(
            matched_field_paths=list(search_result.expanded_fields),
            matched_concepts=[c[0] for c in search_result.matched_concepts],
            concept_scores=concept_scores,
            keywords=keywords,
            matched_endpoint_keys=getattr(search_result, 'matched_endpoint_keys', None),
        )
        
        example_matches: List[ExampleMatch] = []
        try:
            matched_values = getattr(search_result, 'matched_values', [])
            example_matches = self.example_retriever.retrieve(
                question=question,
                matched_concepts=[c[0] for c in search_result.matched_concepts],
                matched_fields=list(search_result.matched_fields),
                matched_values=list(matched_values),
                question_keywords=keywords,
                tenant_id=tenant_id,
                document_name=document_name,
            )
        except Exception as e:
            logger.warning(f"Example retrieval failed: {e}")
        
        examples = [em.to_example_spec() for em in example_matches]

        return RetrievalContext(
            fields=seed_fields,
            expanded_fields=expanded_fields,
            examples=examples,
            documentation=[],
            field_adjacency=field_adjacency,
            expansion_stats={
                "seed_count": len(seed_fields),
                "expanded_count": len(expanded_fields),
                "total_count": len(field_metadata),
                "concept_count": len(search_result.matched_concepts),
                "hop_count": search_result.hop_count,
                "endpoint_count": len(matched_endpoints),
                "example_count": len(examples),
            },
            field_scores=search_result.field_scores,
            config={
                **config,
                "question": question,
                "operations": operations,
            },
            endpoints=matched_endpoints,
        )

    def _find_matched_endpoints(
        self,
        matched_field_paths: List[str],
        matched_concepts: Optional[List[str]] = None,
        concept_scores: Optional[Dict[str, float]] = None,
        keywords: Optional[List[str]] = None,
        matched_endpoint_keys: Optional[Set[str]] = None,
    ) -> List[EndpointMatch]:
        """
        Find and RANK REST API endpoints by relevance.
        
        Scoring factors (configurable weights):
        1. Concept match: endpoint.maps_to matches high-scoring concept
        2. Path segment match: keywords appear in URL path segments
        3. Parameter match ratio: matched_params / total_params
        4. Text match: keywords in summary/description
        5. Response field bonus: endpoint was matched via response search
        
        Args:
            matched_field_paths: List of matched parameter qualified names
            matched_concepts: List of matched concept names
            concept_scores: Dict mapping concept names to their match scores
            keywords: Extracted keywords from user question
            matched_endpoint_keys: Endpoint keys matched via path/response search
        
        Returns:
            List[EndpointMatch] sorted by score descending, limited to max_endpoints
        """
        if not self.graph.schema or not hasattr(self.graph.schema, 'endpoints'):
            return []
        
        endpoints = getattr(self.graph.schema, 'endpoints', []) or []
        if not endpoints:
            return []
        
        # Get scoring config
        scoring = self.config.endpoint_scoring
        
        # Normalize inputs
        matched_paths_set = set(matched_field_paths)
        matched_concepts_set = set(matched_concepts or [])
        concept_scores = concept_scores or {}
        keywords = keywords or []
        matched_endpoint_keys = matched_endpoint_keys or set()
        keywords_lower = [k.lower() for k in keywords]
        
        matches: List[EndpointMatch] = []
        seen_endpoints: Set[str] = set()
        
        for endpoint in endpoints:
            method_str = endpoint.method.value if hasattr(endpoint.method, 'value') else str(endpoint.method)
            endpoint_key = f"{method_str}:{endpoint.path}"
            if endpoint_key in seen_endpoints:
                continue
            seen_endpoints.add(endpoint_key)
            
            reasons = []
            
            # === 1. Concept Match Score ===
            concept_score = 0.0
            if endpoint.maps_to and endpoint.maps_to in matched_concepts_set:
                concept_score = concept_scores.get(endpoint.maps_to, 0.8)
                reasons.append(f"concept:{endpoint.maps_to}={concept_score:.2f}")
            
            # === 2. Path Segment Match Score ===
            path_score = 0.0
            if keywords_lower:
                path_segments = self._extract_path_segments_for_scoring(endpoint.path)
                path_matches = 0
                for kw in keywords_lower:
                    for seg in path_segments:
                        if kw == seg or kw in seg or seg in kw:
                            path_matches += 1
                            break
                if path_matches:
                    path_score = min(1.0, path_matches / len(keywords_lower))
                    reasons.append(f"path:{path_matches}/{len(keywords_lower)}")
            
            # === 3. Parameter Match Score ===
            param_score = 0.0
            matched_params = []
            if endpoint.parameters:
                for param in endpoint.parameters:
                    qualified_name = param.get_qualified_name() if hasattr(param, 'get_qualified_name') else param.name
                    if qualified_name in matched_paths_set:
                        matched_params.append(param)
                if matched_params:
                    param_score = len(matched_params) / len(endpoint.parameters)
                    reasons.append(f"params:{len(matched_params)}/{len(endpoint.parameters)}")
            
            # === 4. Text Match Score (summary/description) ===
            text_score = 0.0
            if keywords_lower:
                text_blob = f"{endpoint.summary or ''} {endpoint.description or ''}".lower()
                text_matches = sum(1 for kw in keywords_lower if kw in text_blob)
                if text_matches:
                    text_score = min(1.0, text_matches / len(keywords_lower))
                    reasons.append(f"text:{text_matches}/{len(keywords_lower)}")
            
            # === 5. Response Field Bonus ===
            response_bonus = 0.0
            if endpoint_key in matched_endpoint_keys:
                response_bonus = 0.2
                reasons.append("response_match")
            
            # === Combined Score ===
            final_score = (
                concept_score * scoring.concept_weight +
                path_score * scoring.path_weight +
                param_score * scoring.param_weight +
                text_score * scoring.text_weight +
                response_bonus  # Additive bonus
            )
            
            # Include if score exceeds threshold OR was directly matched via path/response
            if final_score >= scoring.min_score_threshold or endpoint_key in matched_endpoint_keys:
                from ..schema.api_schema import EndpointSpec
                
                # Include all params if concept/path match is strong, else only matched
                include_all_params = concept_score > 0 or path_score > 0.5
                
                filtered_endpoint = EndpointSpec(
                    path=endpoint.path,
                    method=endpoint.method,
                    operation_id=endpoint.operation_id,
                    summary=endpoint.summary,
                    description=endpoint.description,
                    maps_to=endpoint.maps_to,
                    tags=endpoint.tags,
                    parameters=endpoint.parameters if include_all_params else matched_params,
                    response_fields=endpoint.response_fields,
                    auth_required=endpoint.auth_required,
                    deprecated=endpoint.deprecated,
                )
                
                matches.append(EndpointMatch(
                    endpoint=filtered_endpoint,
                    score=final_score,
                    match_reasons=reasons,
                    concept_score=concept_score,
                    path_score=path_score,
                    param_score=param_score,
                    text_score=text_score,
                    response_score=response_bonus,
                ))
        
        # Sort by score descending and limit
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:scoring.max_endpoints]
    
    def _extract_path_segments_for_scoring(self, path: str) -> List[str]:
        """Extract searchable segments from URL path for scoring.
        
        Similar to SchemaGraph._extract_path_segments but used for scoring.
        """
        segments: Set[str] = set()
        raw_segments = [s for s in path.split('/') if s and not s.startswith('{')]
        
        for segment in raw_segments:
            segment_lower = segment.lower()
            if len(segment_lower) > 2:
                segments.add(segment_lower)
            
            # Split camelCase
            camel_parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', segment)
            for part in camel_parts:
                if len(part) > 2:
                    segments.add(part.lower())
            
            # Split snake_case
            snake_parts = segment.split('_')
            for part in snake_parts:
                if len(part) > 2:
                    segments.add(part.lower())
        
        return list(segments)


def create_graph_retriever(
    schema_graph: SchemaGraph,
    vector_store: Optional[Any] = None,
    embedding_model: Optional[Any] = None,
    config: Optional[GraphRetrievalConfig] = None,
) -> GraphContextRetriever:
    """
    Factory function to create a GraphContextRetriever.
    
    Convenience function for creating a retriever with common defaults.
    
    Args:
        schema_graph: Loaded SchemaGraph
        vector_store: Optional vector store
        embedding_model: Optional embedding model
        config: Optional configuration
    
    Returns:
        Configured GraphContextRetriever instance
    """
    return GraphContextRetriever(
        schema_graph=schema_graph,
        vector_store=vector_store,
        embedding_model=embedding_model,
        config=config,
    )
