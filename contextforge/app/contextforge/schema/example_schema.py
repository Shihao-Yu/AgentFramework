"""
Example Schema for ContextForge.

This module defines the ExampleSpec model for Q&A examples used in few-shot learning.
Examples are linked to schema elements (concepts, fields, values) for graph-based retrieval.

Key Features:
- Variants: Alternative phrasings of the same question
- Schema Linking: Connect examples to concepts, fields, and values
- Graph Integration: Examples become nodes in the schema graph
- Hybrid Retrieval: Supports both vector and graph-based search
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ExampleContent(BaseModel):
    """
    Structured content for an example query/answer.
    
    Separates the query from its metadata for cleaner structure.
    
    Example:
        >>> content = ExampleContent(
        ...     query="SELECT * FROM orders WHERE status = 'pending'",
        ...     query_type="sql",
        ...     explanation="Filters orders table by pending status"
        ... )
    """
    
    query: str = Field(
        ...,
        description="The actual query (SQL, OpenSearch DSL, REST API JSON, etc.)"
    )
    query_type: str = Field(
        default="sql",
        description="Query type: sql, opensearch, rest_api, mongodb, etc."
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Explanation of why this query answers the question - helps LLM understand the logic"
    )
    
    model_config = ConfigDict(use_enum_values=True)


class ExampleSpec(BaseModel):
    """
    Q&A Example for few-shot learning in ContextForge.
    
    Designed for:
    1. Graph integration (linked to concepts, fields, values via edges)
    2. Hybrid retrieval (vector similarity + graph relevance)
    3. UI management (users add/edit via interface)
    
    Graph Edges Created:
    - EXAMPLE --DEMONSTRATES--> CONCEPT
    - EXAMPLE --USES_FIELD--> FIELD  
    - EXAMPLE --USES_VALUE--> VALUE
    - VARIANT --HAS_VARIANT--> EXAMPLE (keyword aliases)
    
    Example:
        >>> example = ExampleSpec(
        ...     title="Get pending orders",
        ...     description="Retrieves orders awaiting processing",
        ...     variants=["Show waiting orders", "List pending"],
        ...     content=ExampleContent(
        ...         query="SELECT * FROM orders WHERE status = 'P'",
        ...         query_type="sql",
        ...         explanation="Uses status='P' which represents pending orders"
        ...     ),
        ...     linked_concepts=["order", "status"],
        ...     linked_fields=["orders.status", "orders.id"],
        ...     linked_values={"orders.status": "P"},
        ...     additional_context="status='P' means pending, 'A' means approved"
        ... )
    """
    
    # === Identity ===
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this example"
    )
    
    # === Core Content ===
    title: str = Field(
        ...,
        description="Short descriptive title - the primary question text"
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed explanation of what this example demonstrates"
    )
    
    # === Variants (Alternative Phrasings) ===
    variants: List[str] = Field(
        default_factory=list,
        description="Alternative ways to ask the same question"
    )
    
    # === Structured Content ===
    content: ExampleContent = Field(
        ...,
        description="The query content with type and explanation"
    )
    
    # === Schema Linking (Graph Integration) ===
    linked_concepts: List[str] = Field(
        default_factory=list,
        description="Concepts this example demonstrates - used for graph traversal"
    )
    linked_fields: List[str] = Field(
        default_factory=list,
        description="Specific fields used in the query - for precise matching"
    )
    linked_values: Dict[str, str] = Field(
        default_factory=dict,
        description="Specific values used (field_path -> value, e.g., {'orders.status': 'P'})"
    )
    
    # === Additional Context ===
    additional_context: Optional[str] = Field(
        default=None,
        description="Extra context injected into prompt when this example is retrieved"
    )
    
    # === Metadata ===
    verified: bool = Field(
        default=False,
        description="Has been verified as correct by a human"
    )
    source: str = Field(
        default="user_provided",
        description="Origin: user_provided, llm_generated, learned"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="User-defined tags for organization and filtering"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this example was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="When this example was last updated"
    )
    usage_count: int = Field(
        default=0,
        description="Number of times this example was retrieved and used"
    )
    
    # === Computed (populated on storage) ===
    embedding: List[float] = Field(
        default_factory=list,
        description="Vector embedding of searchable text for semantic search"
    )
    
    model_config = ConfigDict(use_enum_values=True)
    
    def get_searchable_text(self) -> str:
        """
        Get combined text for embedding generation.
        
        Combines title, description, and variants into a single
        text suitable for creating a semantic embedding.
        
        Returns:
            Combined text separated by ' | '
        """
        parts = [self.title]
        if self.description:
            parts.append(self.description)
        parts.extend(self.variants)
        return " | ".join(parts)
    
    def get_variant_keywords(self, language: str = 'english') -> List[str]:
        """
        Extract keywords from title and variants for graph indexing.
        
        Uses proper stop word filtering and lemmatization via text_processing utility.
        These keywords are used to create HAS_VARIANT edges in the graph.
        
        Args:
            language: Language name for stopwords (default: 'english')
        
        Returns:
            List of unique lemmatized keywords
        """
        # Note: This method requires the text_processing utility
        # For now, return a simple implementation
        import re
        from typing import Set
        
        # Simple stopwords list
        stopwords: Set[str] = {
            'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
            'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
            'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
            'below', 'between', 'under', 'again', 'further', 'then', 'once',
            'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
            'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
            'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'and',
            'but', 'if', 'or', 'because', 'until', 'while', 'what', 'which',
            'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'i', 'me',
            'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your',
            'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself',
            'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they',
            'them', 'their', 'theirs', 'themselves', 'get', 'show', 'list',
            'find', 'give', 'tell', 'display',
        }
        
        # Combine title and variants
        text = f"{self.title} {' '.join(self.variants)}"
        
        # Extract words
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        
        # Filter stopwords and short words
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        return list(set(keywords))
    
    def increment_usage(self) -> None:
        """Increment the usage count for this example."""
        self.usage_count += 1
        self.updated_at = datetime.utcnow()
    
    def to_prompt_context(self) -> str:
        """
        Format example for inclusion in LLM prompt.
        
        Returns:
            Formatted string suitable for few-shot prompting
        """
        lines = [f"Question: {self.title}"]
        
        if self.content.query_type != "sql":
            lines.append(f"Type: {self.content.query_type}")
        
        lines.append(f"Query: {self.content.query}")
        
        if self.content.explanation:
            lines.append(f"Explanation: {self.content.explanation}")
        
        if self.additional_context:
            lines.append(f"Context: {self.additional_context}")
        
        return "\n".join(lines)
    
    def matches_concept(self, concept: str) -> bool:
        """Check if this example is linked to a concept."""
        concept_lower = concept.lower()
        return any(c.lower() == concept_lower for c in self.linked_concepts)
    
    def matches_field(self, field_path: str) -> bool:
        """Check if this example uses a specific field."""
        return field_path in self.linked_fields
    
    def matches_value(self, field_path: str, value: str) -> bool:
        """Check if this example uses a specific field:value combination."""
        return self.linked_values.get(field_path, "").lower() == value.lower()


# Type alias for backward compatibility
LangfuseQAExample = ExampleSpec
