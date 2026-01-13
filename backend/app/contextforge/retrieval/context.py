"""
Retrieval Context for Query Generation

Provides a unified container for all retrieved context:
- Schema fields from vector/graph search
- Expanded fields from graph traversal
- Q&A examples
- Field relationships for prompt formatting
- REST API endpoints (when source is REST API)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..schema.field_schema import FieldSpec

logger = logging.getLogger(__name__)


@dataclass
class RetrievalContext:
    """
    Unified context object for query generation.

    Contains all context needed for prompt assembly:
    - Schema fields from vector search
    - Expanded fields from graph traversal
    - Q&A examples
    - Field relationships for prompt formatting
    - REST API endpoints (when source is REST API)
    """

    # Core retrieval results
    fields: List['FieldSpec']  # Direct matches
    expanded_fields: List['FieldSpec']  # Graph-expanded fields
    examples: List[Any]  # Q&A examples
    documentation: List[str]

    # Graph context
    field_adjacency: Dict[str, List[tuple]]  # field -> [(related, edge_type)]
    expansion_stats: Dict[str, int]

    # Field scores from retrieval (field_path -> score)
    field_scores: Dict[str, float] = field(default_factory=dict)

    # Configuration used
    config: Dict[str, Any] = field(default_factory=dict)
    
    # REST API endpoints (when source type is REST API)
    endpoints: List[Any] = field(default_factory=list)  # List[EndpointMatch]

    @property
    def all_fields(self) -> List['FieldSpec']:
        """Combined list of seed + expanded fields (deduplicated)"""
        seen = set()
        result = []

        for f in self.fields:
            key = f.path
            if key not in seen:
                seen.add(key)
                result.append(f)

        for f in self.expanded_fields:
            key = f.path
            if key not in seen:
                seen.add(key)
                result.append(f)

        return result

    @property
    def field_count(self) -> int:
        """Total unique field count"""
        return len(self.all_fields)

    @property
    def example_count(self) -> int:
        """Number of Q&A examples"""
        return len(self.examples)

    @property
    def endpoint_count(self) -> int:
        """Number of matched REST API endpoints"""
        return len(self.endpoints)

    @property
    def has_endpoints(self) -> bool:
        """Whether this context contains REST API endpoints"""
        return len(self.endpoints) > 0

    @property
    def top_endpoint(self) -> Optional[Any]:
        """Highest scoring endpoint, if any (EndpointMatch object)"""
        return self.endpoints[0] if self.endpoints else None

    def endpoints_for_llm(self, threshold: float = 0.6) -> List[Any]:
        """
        Get endpoints above threshold for LLM context.
        
        Only endpoints with scores >= threshold are considered "relevant"
        enough to include in LLM context, reducing noise from low-quality matches.
        """
        return [e for e in self.endpoints if e.score >= threshold]

    def endpoints_excluded_from_llm(self, threshold: float = 0.6) -> List[Any]:
        """Get endpoints below threshold (excluded from LLM context)."""
        return [e for e in self.endpoints if e.score < threshold]

    def get_score(self, field_path: str) -> float:
        """Get the retrieval score for a field (0.0 if not found)"""
        return self.field_scores.get(field_path, 0.0)

    def all_fields_with_scores(self) -> List[tuple]:
        """Get all fields with their scores, sorted by score descending"""
        result = []
        for f in self.all_fields:
            key = f.path
            score = self.field_scores.get(key, 0.0)
            result.append((f, score))
        return sorted(result, key=lambda x: -x[1])

    def fields_for_llm(self, threshold: float = 0.6) -> List['FieldSpec']:
        """
        Get fields above threshold for LLM context.

        Args:
            threshold: Minimum score to include (default: 0.6)

        Returns:
            List of fields with score >= threshold, sorted by score descending
        """
        return [f for f, score in self.all_fields_with_scores() if score >= threshold]

    def fields_excluded_from_llm(self, threshold: float = 0.6) -> List[tuple]:
        """
        Get fields below threshold (excluded from LLM context).

        Args:
            threshold: Score threshold (default: 0.6)

        Returns:
            List of (field, score) tuples below threshold
        """
        return [(f, score) for f, score in self.all_fields_with_scores() if score < threshold]

    def filter_by_score(self, threshold: float = 0.6) -> "RetrievalContext":
        """
        Create a new RetrievalContext with only fields above score threshold.

        This is useful for hierarchical grouping where we only want to show
        fields that would be sent to the LLM.
        """
        # Get fields above threshold
        filtered_fields = []
        for f in self.fields:
            key = f.path
            if self.field_scores.get(key, 0.0) >= threshold:
                filtered_fields.append(f)

        # Filter expanded fields too
        filtered_expanded = []
        for f in self.expanded_fields:
            key = f.path
            if self.field_scores.get(key, 0.0) >= threshold:
                filtered_expanded.append(f)

        # Filter adjacency to only include relevant fields
        all_filtered_names = {f.path for f in filtered_fields + filtered_expanded}
        filtered_adjacency = {}
        for field_name, relations in self.field_adjacency.items():
            if field_name in all_filtered_names:
                filtered_adjacency[field_name] = [
                    (rel, edge) for rel, edge in relations
                    if rel in all_filtered_names
                ]

        return RetrievalContext(
            fields=filtered_fields,
            expanded_fields=filtered_expanded,
            examples=self.examples,
            documentation=self.documentation,
            field_adjacency=filtered_adjacency,
            expansion_stats=self.expansion_stats,
            field_scores=self.field_scores,
            config=self.config,
            endpoints=self.endpoints,
        )


class ContextFormatter:
    """
    Format RetrievalContext for prompt assembly.

    Provides methods to convert retrieval results into prompt-ready strings.
    """

    @staticmethod
    def format_schema_fields(
        context: RetrievalContext,
        include_expanded: bool = True,
        include_relationships: bool = True,
    ) -> str:
        """
        Format schema fields for prompt.

        Args:
            context: RetrievalContext from retriever
            include_expanded: Include graph-expanded fields
            include_relationships: Include field relationships
        """
        fields = context.all_fields if include_expanded else context.fields

        if not fields:
            return "No relevant schema fields found."

        lines = ["Relevant Schema Fields:"]

        for field_spec in fields:
            path = field_spec.path

            # Mark expanded fields
            is_expanded = field_spec in context.expanded_fields
            marker = " [related]" if is_expanded else ""

            lines.append(f"\n- {path} ({field_spec.es_type}){marker}")
            lines.append(f"  Description: {field_spec.description}")

            if field_spec.maps_to:
                lines.append(f"  Business meaning: {field_spec.maps_to}")

            # Value constraints
            if field_spec.allowed_values:
                values_display = field_spec.allowed_values[:5]
                if len(field_spec.allowed_values) > 5:
                    values_display.append(f"... ({len(field_spec.allowed_values)} total)")
                lines.append(f"  Allowed values: {', '.join(values_display)}")

            if field_spec.value_synonyms:
                # Show value encoding for coded fields
                encoding_strs = [f"{k}={v[0] if v else k}" for k, v in list(field_spec.value_synonyms.items())[:3]]
                lines.append(f"  Encoding: {', '.join(encoding_strs)}")

            if include_relationships and path in context.field_adjacency:
                related = context.field_adjacency[path]
                if related:
                    rel_strs = [f"{r[0]} ({r[1]})" for r in related[:3]]
                    lines.append(f"  Related via graph: {', '.join(rel_strs)}")

        return "\n".join(lines)

    @staticmethod
    def format_schema_fields_hierarchical(
        context: RetrievalContext,
        subgraphs: dict,
        include_scores: bool = True,
        verbose: bool = False,
    ) -> str:
        """
        Format schema fields as concept-centric hierarchies.

        Groups fields by their parent concept, showing parent-child relationships
        to help the LLM understand the schema structure.

        Args:
            context: RetrievalContext from retriever
            subgraphs: Dict of ConceptSubgraph from group_fields_by_concept()
            include_scores: Include fusion scores in output
            verbose: Include full field metadata

        Returns:
            Formatted string with hierarchical structure
        """
        if not subgraphs:
            return "No relevant schema fields found."

        lines = ["Relevant Schema Fields:"]
        seed_names = {f.path for f in context.fields}

        # Sort subgraphs by score (highest first) and whether matched
        sorted_concepts = sorted(
            subgraphs.items(),
            key=lambda x: (-int(x[1].is_matched), -x[1].fusion_score),
        )

        # Track which concepts are children (to skip in main loop)
        child_concepts = set()
        for _, sg in sorted_concepts:
            child_concepts.update(sg.children.keys())

        for concept_name, subgraph in sorted_concepts:
            # Skip if this is a child (will be rendered under parent)
            if concept_name in child_concepts:
                continue

            lines.extend(
                ContextFormatter._format_subgraph(
                    subgraph, seed_names, include_scores, indent=0, verbose=verbose
                )
            )

        return "\n".join(lines)

    @staticmethod
    def _format_subgraph(
        subgraph,
        seed_names: set,
        include_scores: bool,
        indent: int = 0,
        verbose: bool = False,
    ) -> list:
        """Recursively format a ConceptSubgraph with indentation."""
        lines = []
        prefix = "  " * indent

        # Format concept header
        score_str = f" - score: {subgraph.fusion_score:.2f}" if include_scores else ""
        match_marker = " [MATCHED]" if subgraph.is_matched else ""

        # Show relationships if any
        rel_str = ""
        if subgraph.relationships and indent > 0:
            edge_types = {e for _, e in subgraph.relationships}
            rel_str = f" via {', '.join(edge_types)}"

        lines.append(f"\n{prefix}[{subgraph.concept_name}]{rel_str}{score_str}{match_marker}")

        # Format fields within this concept
        field_count = len(subgraph.fields)
        for i, field_spec in enumerate(subgraph.fields):
            path = field_spec.path
            is_last_field = (i == field_count - 1) and not subgraph.children
            connector = "└─" if is_last_field else "├─"

            # Mark if this specific field was in seed results
            field_marker = " [MATCHED]" if path in seed_names else ""

            lines.append(f"{prefix}{connector} {path} ({field_spec.es_type}){field_marker}")

            # Continuation prefix for multi-line field details
            cont_prefix = "   " if is_last_field else "│  "

            # Add description if available
            if field_spec.description:
                desc = field_spec.description[:60] + "..." if len(field_spec.description) > 60 else field_spec.description
                lines.append(f"{prefix}{cont_prefix} {desc}")

            # Show allowed values inline
            if field_spec.allowed_values:
                values = field_spec.allowed_values[:4]
                values_str = ', '.join(values)
                if len(field_spec.allowed_values) > 4:
                    values_str += f"... (+{len(field_spec.allowed_values) - 4})"
                lines.append(f"{prefix}{cont_prefix} Values: {values_str}")

            # Show value encoding/synonyms
            if field_spec.value_synonyms:
                encoding_strs = [f"{k}={v[0] if v else k}" for k, v in list(field_spec.value_synonyms.items())[:5]]
                if len(field_spec.value_synonyms) > 5:
                    encoding_strs.append(f"... (+{len(field_spec.value_synonyms) - 5})")
                lines.append(f"{prefix}{cont_prefix} Value Meanings: {', '.join(encoding_strs)}")

            # Verbose mode: show additional metadata
            if verbose:
                if field_spec.aliases:
                    lines.append(f"{prefix}{cont_prefix} Aliases: {', '.join(field_spec.aliases[:3])}")

        # Format children recursively
        children = list(subgraph.children.items())
        for i, (child_name, child_subgraph) in enumerate(children):
            is_last_child = (i == len(children) - 1)
            child_prefix = "└─ " if is_last_child else "├─ "
            lines.append(f"{prefix}{child_prefix}")
            lines.extend(
                ContextFormatter._format_subgraph(
                    child_subgraph, seed_names, include_scores, indent + 1, verbose=verbose
                )
            )

        return lines

    @staticmethod
    def format_qa_examples(context: RetrievalContext) -> str:
        """Format Q&A examples for prompt"""
        if not context.examples:
            return "No similar examples found."

        lines = ["Similar Examples:"]
        for i, example in enumerate(context.examples, 1):
            # Handle both dict and object formats
            if isinstance(example, dict):
                question = example.get("title") or example.get("question", "")
                query = example.get("query", "")
                explanation = example.get("explanation", "")
            else:
                question = getattr(example, "title", "") or getattr(example, "question", "")
                query = getattr(example, "query", "")
                explanation = getattr(example, "explanation", "")
            
            lines.append(f"\n{i}. Question: {question}")
            lines.append(f"   Query: {query}")
            if explanation:
                lines.append(f"   Explanation: {explanation}")

        return "\n".join(lines)

    @staticmethod
    def format_documentation(
        context: RetrievalContext,
        static_doc: Optional[str] = None,
    ) -> str:
        """Format documentation for prompt"""
        if not context.documentation and not static_doc:
            return ""

        lines = ["Documentation:"]

        for i, doc in enumerate(context.documentation, 1):
            lines.append(f"\n{i}. {doc}")

        if static_doc:
            lines.append(f"\n\nAdditional Context:\n{static_doc}")

        return "\n".join(lines)

    @classmethod
    def format_full_context(
        cls,
        context: RetrievalContext,
        general_rules: str = "",
        static_doc: Optional[str] = None,
        subgraphs: Optional[dict] = None,
        use_hierarchical: bool = True,
    ) -> str:
        """
        Format complete context for prompt assembly.

        Combines all context sources into a single formatted string.

        Args:
            context: RetrievalContext from retriever
            general_rules: Additional rules to include
            static_doc: Static documentation to append
            subgraphs: Optional ConceptSubgraph dict for hierarchical format
            use_hierarchical: Use hierarchical format when subgraphs provided

        Returns:
            Formatted context string for LLM prompt
        """
        # Use hierarchical format if subgraphs provided
        if subgraphs and use_hierarchical:
            schema_str = cls.format_schema_fields_hierarchical(context, subgraphs)
        else:
            schema_str = cls.format_schema_fields(context)

        parts = [
            schema_str,
            cls.format_qa_examples(context),
        ]

        doc_str = cls.format_documentation(context, static_doc)
        if doc_str:
            parts.append(doc_str)

        if general_rules:
            parts.append(f"\nRules:\n{general_rules}")

        return "\n\n".join(parts)
