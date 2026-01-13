"""
BM25 Index for Field Text Search

Provides BM25 (Best Matching 25) ranking for searching field metadata.
Indexes field paths, descriptions, aliases, and concept mappings.

Used by GraphContextRetriever for text-based field discovery.
"""

import logging
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..schema.yaml_schema import YAMLSchemaV1
from ..schema.field_schema import FieldSpec
from ..schema.api_schema import EndpointSpec, ParameterSpec

logger = logging.getLogger(__name__)


@dataclass
class BM25Config:
    """Configuration for BM25 ranking parameters"""
    # BM25 tuning parameters
    k1: float = 1.5  # Term frequency saturation parameter
    b: float = 0.75  # Length normalization parameter

    # Minimum score threshold
    min_score: float = 0.0

    # Field weighting for document construction
    path_weight: float = 2.0        # Field path is important
    description_weight: float = 1.5  # Descriptions are informative
    alias_weight: float = 1.0        # Aliases help matching
    concept_weight: float = 1.5      # Concept mapping is semantic


@dataclass
class BM25Document:
    """A document in the BM25 index"""
    field_path: str
    tokens: List[str]
    token_freqs: Dict[str, int]
    length: int

    # Source metadata for debugging
    source_text: str


@dataclass
class BM25SearchResult:
    """Result from BM25 search"""
    field_path: str
    score: float
    matched_terms: List[str]


class BM25FieldIndex:
    """
    BM25 index over field metadata for text-based retrieval.

    Indexes:
    - Field paths (e.g., "Status", "PurchaseOrder.Status")
    - Field descriptions
    - Field aliases
    - Mapped concept names

    Example:
        >>> index = BM25FieldIndex()
        >>> index.build_from_schema(schema)
        >>> results = index.search("pending status orders", top_k=5)
        >>> for r in results:
        ...     print(f"{r.field_path}: {r.score:.3f}")
    """

    def __init__(self, config: Optional[BM25Config] = None):
        self.config = config or BM25Config()
        self._documents: List[BM25Document] = []
        self._field_to_idx: Dict[str, int] = {}

        # Corpus statistics
        self._avgdl: float = 0.0
        self._doc_count: int = 0
        self._doc_freqs: Dict[str, int] = {}  # term -> number of docs containing term

        # Precomputed IDF values
        self._idf_cache: Dict[str, float] = {}

    def build_from_schema(self, schema: YAMLSchemaV1) -> None:
        """
        Build BM25 index from schema.

        Processes all fields in all indices, creating searchable
        documents from their metadata.
        """
        self._documents.clear()
        self._field_to_idx.clear()
        self._doc_freqs.clear()
        self._idf_cache.clear()

        # Collect all documents from indices
        for index in schema.indices:
            self._index_fields(index.fields, index.name)

        # Collect all documents from REST API endpoints
        for endpoint in schema.endpoints:
            self._index_endpoint_params(endpoint)

        # Calculate corpus statistics
        self._doc_count = len(self._documents)
        if self._doc_count > 0:
            total_length = sum(doc.length for doc in self._documents)
            self._avgdl = total_length / self._doc_count
        else:
            self._avgdl = 1.0

        # Precompute IDF for all terms
        self._precompute_idf()

        logger.info(
            f"Built BM25 index: {self._doc_count} documents, "
            f"{len(self._doc_freqs)} unique terms, avgdl={self._avgdl:.1f}"
        )

    def _index_fields(
        self,
        fields: List[FieldSpec],
        index_name: str,
        parent_path: str = "",
    ) -> None:
        """Recursively index fields including nested ones"""
        for field_spec in fields:
            # Build document text from field metadata
            doc_text = self._build_document_text(field_spec)
            tokens = self._tokenize(doc_text)

            if not tokens:
                continue

            # Calculate token frequencies
            token_freqs: Dict[str, int] = {}
            for token in tokens:
                token_freqs[token] = token_freqs.get(token, 0) + 1

            # Create document
            doc = BM25Document(
                field_path=field_spec.path,
                tokens=tokens,
                token_freqs=token_freqs,
                length=len(tokens),
                source_text=doc_text,
            )

            # Store document
            idx = len(self._documents)
            self._documents.append(doc)
            self._field_to_idx[field_spec.path] = idx

            # Update document frequencies
            for term in set(tokens):
                self._doc_freqs[term] = self._doc_freqs.get(term, 0) + 1

            # Recursively index nested fields
            if field_spec.nested_fields:
                self._index_fields(field_spec.nested_fields, index_name, field_spec.path)

    def _index_endpoint_params(self, endpoint: EndpointSpec) -> None:
        """
        Index REST API endpoint parameters.
        
        Parameters are treated like fields for BM25 search.
        """
        method_str = endpoint.method.value if hasattr(endpoint.method, 'value') else str(endpoint.method)
        endpoint_key = f"{method_str}:{endpoint.path}"
        
        for param in endpoint.parameters:
            # Build document text from parameter metadata
            doc_text = self._build_param_document_text(param, endpoint)
            tokens = self._tokenize(doc_text)
            
            if not tokens:
                continue
            
            # Calculate token frequencies
            token_freqs: Dict[str, int] = {}
            for token in tokens:
                token_freqs[token] = token_freqs.get(token, 0) + 1
            
            # Get qualified name for the param
            qualified_name = param.get_qualified_name() if hasattr(param, 'get_qualified_name') else param.name
            
            # Create document
            doc = BM25Document(
                field_path=qualified_name,
                tokens=tokens,
                token_freqs=token_freqs,
                length=len(tokens),
                source_text=doc_text,
            )
            
            # Store document
            idx = len(self._documents)
            self._documents.append(doc)
            self._field_to_idx[qualified_name] = idx
            
            # Update document frequencies
            for term in set(tokens):
                self._doc_freqs[term] = self._doc_freqs.get(term, 0) + 1

    def _build_param_document_text(self, param: ParameterSpec, endpoint: EndpointSpec) -> str:
        """
        Build searchable text from parameter metadata.
        
        Similar to _build_document_text but for ParameterSpec.
        """
        cfg = self.config
        parts: List[str] = []
        
        # Parameter name (weighted like path)
        name_parts = param.name.replace(".", " ").split()
        for _ in range(int(cfg.path_weight)):
            parts.extend(name_parts)
        
        # Endpoint path context
        path_tokens = self._tokenize(endpoint.path.replace("/", " ").replace("{", " ").replace("}", " "))
        parts.extend(path_tokens)
        
        # Description (weighted)
        if param.description:
            desc_tokens = self._tokenize(param.description)
            for _ in range(int(cfg.description_weight)):
                parts.extend(desc_tokens)
        
        # Business meaning
        if hasattr(param, 'business_meaning') and param.business_meaning:
            meaning_tokens = self._tokenize(param.business_meaning)
            for _ in range(int(cfg.description_weight)):
                parts.extend(meaning_tokens)
        
        # Mapped concept (weighted)
        if param.maps_to:
            concept_tokens = self._tokenize(param.maps_to)
            for _ in range(int(cfg.concept_weight)):
                parts.extend(concept_tokens)
        
        # Allowed values
        if param.allowed_values:
            for val in param.allowed_values:
                val_tokens = self._tokenize(val)
                parts.extend(val_tokens)
        
        return " ".join(parts)

    def _build_document_text(self, field_spec: FieldSpec) -> str:
        """
        Build searchable text from field metadata.

        Applies weights by repeating important terms.
        """
        cfg = self.config
        parts: List[str] = []

        # Field path (weighted)
        path_parts = field_spec.path.replace(".", " ").split()
        for _ in range(int(cfg.path_weight)):
            parts.extend(path_parts)

        # Description (weighted)
        if field_spec.description:
            desc_tokens = self._tokenize(field_spec.description)
            for _ in range(int(cfg.description_weight)):
                parts.extend(desc_tokens)

        # Aliases (weighted)
        for alias in field_spec.aliases:
            alias_tokens = self._tokenize(alias)
            for _ in range(int(cfg.alias_weight)):
                parts.extend(alias_tokens)

        # Mapped concept (weighted)
        if field_spec.maps_to:
            concept_tokens = self._tokenize(field_spec.maps_to)
            for _ in range(int(cfg.concept_weight)):
                parts.extend(concept_tokens)

        return " ".join(parts)

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into lowercase terms.

        Handles:
        - CamelCase splitting
        - Underscore/dot splitting
        - Lowercase normalization
        - Short token filtering
        """
        if not text:
            return []

        # Split CamelCase
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

        # Split on non-alphanumeric
        tokens = re.findall(r'[a-zA-Z0-9]+', text.lower())

        # Filter short tokens
        return [t for t in tokens if len(t) >= 2]

    def _precompute_idf(self) -> None:
        """Precompute IDF values for all terms"""
        n = self._doc_count
        if n == 0:
            return

        for term, df in self._doc_freqs.items():
            # BM25 IDF formula
            idf = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
            self._idf_cache[term] = idf

    def _get_idf(self, term: str) -> float:
        """Get IDF for a term"""
        return self._idf_cache.get(term, 0.0)

    def _score_document(
        self,
        doc: BM25Document,
        query_tokens: List[str],
    ) -> Tuple[float, List[str]]:
        """
        Calculate BM25 score for a document given query tokens.

        Returns (score, matched_terms).
        """
        k1 = self.config.k1
        b = self.config.b

        score = 0.0
        matched_terms: List[str] = []

        # Length normalization factor
        len_norm = 1 - b + b * (doc.length / self._avgdl) if self._avgdl > 0 else 1.0

        for term in query_tokens:
            if term not in doc.token_freqs:
                continue

            matched_terms.append(term)

            # Term frequency in document
            tf = doc.token_freqs[term]

            # IDF
            idf = self._get_idf(term)

            # BM25 term score
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * len_norm
            term_score = idf * (numerator / denominator)

            score += term_score

        return score, matched_terms

    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: Optional[float] = None,
    ) -> List[BM25SearchResult]:
        """
        Search the index with a text query.

        Args:
            query: Natural language query
            top_k: Maximum results to return
            min_score: Minimum score threshold (default: from config)

        Returns:
            List of BM25SearchResult sorted by score descending
        """
        if not self._documents:
            return []

        min_score = min_score if min_score is not None else self.config.min_score
        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        # Score all documents
        results: List[BM25SearchResult] = []
        for doc in self._documents:
            score, matched = self._score_document(doc, query_tokens)

            if score >= min_score and matched:
                results.append(BM25SearchResult(
                    field_path=doc.field_path,
                    score=score,
                    matched_terms=matched,
                ))

        # Sort by score descending and limit
        results.sort(key=lambda r: -r.score)
        return results[:top_k]

    def search_fields(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        """
        Convenience method returning (field_path, score) tuples.

        Compatible with fusion search interface.
        """
        results = self.search(query, top_k)
        return [(r.field_path, r.score) for r in results]

    def get_field_score(self, field_path: str, query: str) -> float:
        """Get BM25 score for a specific field given a query"""
        if field_path not in self._field_to_idx:
            return 0.0

        idx = self._field_to_idx[field_path]
        doc = self._documents[idx]
        query_tokens = self._tokenize(query)

        score, _ = self._score_document(doc, query_tokens)
        return score

    def has_documents(self) -> bool:
        """Check if index has any documents"""
        return len(self._documents) > 0

    @property
    def document_count(self) -> int:
        """Number of indexed documents"""
        return self._doc_count

    @property
    def vocabulary_size(self) -> int:
        """Number of unique terms"""
        return len(self._doc_freqs)

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            "document_count": self._doc_count,
            "vocabulary_size": len(self._doc_freqs),
            "avg_doc_length": self._avgdl,
            "total_tokens": sum(doc.length for doc in self._documents),
        }

    def __repr__(self) -> str:
        return (
            f"BM25FieldIndex("
            f"docs={self._doc_count}, "
            f"vocab={len(self._doc_freqs)}, "
            f"avgdl={self._avgdl:.1f})"
        )
