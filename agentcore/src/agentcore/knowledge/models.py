"""Knowledge models for ContextForge integration."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeType(str, Enum):
    """Types of knowledge nodes in ContextForge."""

    SCHEMA = "schema"
    CONCEPT = "concept"
    PLAYBOOK = "playbook"
    FAQ = "faq"
    ENTITY = "entity"
    PERMISSION = "permission"
    FIELD = "field"
    RELATIONSHIP = "relationship"


class KnowledgeNode(BaseModel):
    """A single knowledge node from ContextForge.
    
    Maps to KnowledgeItem in ContextForge but with agent-focused fields.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Unique node identifier")
    type: KnowledgeType = Field(description="Type of knowledge")
    title: str = Field(description="Node title")
    content: str = Field(description="Main content")
    
    # Optional fields
    summary: Optional[str] = Field(default=None, description="Short summary")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Search result fields
    score: Optional[float] = Field(default=None, description="Relevance score from search")
    
    # Graph fields
    edges: list[str] = Field(default_factory=list, description="Connected node IDs")
    tenant: Optional[str] = Field(default=None, description="Tenant/domain this belongs to")

    def to_prompt_text(self, include_metadata: bool = False) -> str:
        """Convert to text suitable for LLM prompts.
        
        Args:
            include_metadata: Whether to include metadata in output
            
        Returns:
            Formatted text for prompt context
        """
        parts = [f"## {self.title} ({self.type.value})"]
        
        if self.summary:
            parts.append(f"\n{self.summary}")
        
        parts.append(f"\n{self.content}")
        
        if include_metadata and self.metadata:
            parts.append(f"\nMetadata: {self.metadata}")
        
        return "\n".join(parts)

    def truncate(self, max_length: int = 2000) -> "KnowledgeNode":
        """Return a copy with truncated content."""
        if len(self.content) <= max_length:
            return self
        
        truncated_content = self.content[:max_length] + f"... [truncated, {len(self.content)} total chars]"
        return self.model_copy(update={"content": truncated_content})


class SearchResult(BaseModel):
    """A single search result from ContextForge."""

    model_config = ConfigDict(frozen=True)

    node: KnowledgeNode
    score: float = Field(ge=0.0, le=1.0, description="Relevance score")
    highlights: list[str] = Field(default_factory=list, description="Text highlights")

    @classmethod
    def from_node(cls, node: KnowledgeNode, score: float = 0.0) -> "SearchResult":
        """Create from a KnowledgeNode."""
        return cls(
            node=node.model_copy(update={"score": score}) if node.score != score else node,
            score=score,
        )


class SearchResults(BaseModel):
    """Collection of search results from ContextForge."""

    model_config = ConfigDict(frozen=True)

    results: list[SearchResult] = Field(default_factory=list)
    total_count: int = Field(default=0, description="Total matches (may be more than returned)")
    query: str = Field(default="", description="Original query")

    @property
    def nodes(self) -> list[KnowledgeNode]:
        """Get just the nodes from results."""
        return [r.node for r in self.results]

    def top(self, n: int = 5) -> "SearchResults":
        """Get top N results."""
        return self.model_copy(update={"results": self.results[:n]})

    def filter_by_type(self, *types: KnowledgeType) -> "SearchResults":
        """Filter results by knowledge type."""
        filtered = [r for r in self.results if r.node.type in types]
        return self.model_copy(update={"results": filtered})

    def to_prompt_context(self, max_chars: int = 8000) -> str:
        """Convert results to prompt context text.
        
        Args:
            max_chars: Maximum total characters
            
        Returns:
            Formatted text for LLM prompt
        """
        if not self.results:
            return "No relevant knowledge found."
        
        parts = []
        total_chars = 0
        
        for result in self.results:
            text = result.node.to_prompt_text()
            if total_chars + len(text) > max_chars:
                # Truncate this result
                remaining = max_chars - total_chars
                if remaining > 100:
                    text = text[:remaining] + "..."
                    parts.append(text)
                break
            parts.append(text)
            total_chars += len(text) + 10  # Account for separators
        
        return "\n\n---\n\n".join(parts)


class KnowledgeBundle(BaseModel):
    """Bundle of knowledge retrieved for a query.
    
    Organizes knowledge by type for easy access in agent prompts.
    """

    model_config = ConfigDict(frozen=True)

    query: str = Field(description="Original query")
    
    # Organized by type
    schemas: list[KnowledgeNode] = Field(default_factory=list, description="Schema definitions")
    concepts: list[KnowledgeNode] = Field(default_factory=list, description="High-level concepts")
    playbooks: list[KnowledgeNode] = Field(default_factory=list, description="Step-by-step guides")
    faqs: list[KnowledgeNode] = Field(default_factory=list, description="FAQs")
    entities: list[KnowledgeNode] = Field(default_factory=list, description="Entity definitions")
    other: list[KnowledgeNode] = Field(default_factory=list, description="Other knowledge types")

    @classmethod
    def from_search_results(cls, query: str, results: SearchResults) -> "KnowledgeBundle":
        """Create a bundle from search results, organized by type."""
        bundle_data: dict[str, list[KnowledgeNode]] = {
            "schemas": [],
            "concepts": [],
            "playbooks": [],
            "faqs": [],
            "entities": [],
            "other": [],
        }
        
        type_mapping = {
            KnowledgeType.SCHEMA: "schemas",
            KnowledgeType.CONCEPT: "concepts",
            KnowledgeType.PLAYBOOK: "playbooks",
            KnowledgeType.FAQ: "faqs",
            KnowledgeType.ENTITY: "entities",
        }
        
        for result in results.results:
            key = type_mapping.get(result.node.type, "other")
            bundle_data[key].append(result.node)
        
        return cls(query=query, **bundle_data)

    @property
    def all_nodes(self) -> list[KnowledgeNode]:
        """Get all nodes in the bundle."""
        return (
            self.schemas +
            self.concepts +
            self.playbooks +
            self.faqs +
            self.entities +
            self.other
        )

    @property
    def is_empty(self) -> bool:
        """Check if bundle has any knowledge."""
        return len(self.all_nodes) == 0

    def to_prompt_context(self, max_chars: int = 8000) -> str:
        """Convert bundle to prompt context text.
        
        Prioritizes playbooks, then schemas, then concepts, then others.
        
        Args:
            max_chars: Maximum total characters
            
        Returns:
            Formatted text for LLM prompt
        """
        if self.is_empty:
            return "No relevant knowledge found."
        
        sections = []
        total_chars = 0
        
        # Priority order
        ordered_groups = [
            ("Playbooks", self.playbooks),
            ("Schemas", self.schemas),
            ("Concepts", self.concepts),
            ("FAQs", self.faqs),
            ("Entities", self.entities),
            ("Other", self.other),
        ]
        
        for section_name, nodes in ordered_groups:
            if not nodes:
                continue
            
            section_parts = [f"### {section_name}"]
            for node in nodes:
                text = node.to_prompt_text()
                if total_chars + len(text) > max_chars:
                    remaining = max_chars - total_chars
                    if remaining > 100:
                        text = text[:remaining] + "..."
                        section_parts.append(text)
                    break
                section_parts.append(text)
                total_chars += len(text) + 10
            
            if len(section_parts) > 1:  # Has content besides header
                sections.append("\n".join(section_parts))
            
            if total_chars >= max_chars:
                break
        
        return "\n\n".join(sections)

    def get_for_planning(self) -> str:
        """Get knowledge context for planning sub-agent.
        
        Focuses on playbooks and high-level concepts.
        """
        nodes = self.playbooks + self.concepts
        if not nodes:
            return "No planning guidance found."
        
        return "\n\n---\n\n".join(n.to_prompt_text() for n in nodes[:5])

    def get_for_research(self) -> str:
        """Get knowledge context for research sub-agent.
        
        Includes schemas and FAQs.
        """
        nodes = self.schemas + self.faqs + self.entities
        if not nodes:
            return "No research context found."
        
        return "\n\n---\n\n".join(n.to_prompt_text() for n in nodes[:10])

    def get_schema(self, entity_name: str) -> Optional[KnowledgeNode]:
        """Get schema for a specific entity name."""
        entity_lower = entity_name.lower()
        for schema in self.schemas:
            if entity_lower in schema.title.lower():
                return schema
        return None
