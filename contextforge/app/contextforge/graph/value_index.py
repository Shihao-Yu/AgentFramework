"""
Value Synonym Index for Semantic Retrieval

Provides fast lookup for:
- Value synonyms: "waiting" -> (order_status, "pending", confidence)
- Pronouns: "my" -> [requestor, owner]

Used by GraphContextRetriever for parallel fusion search.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..schema.yaml_schema import YAMLSchemaV1
    from ..schema.field_schema import FieldSpec

logger = logging.getLogger(__name__)


@dataclass
class ValueMatch:
    """Result of a value synonym lookup"""
    concept_name: str
    canonical_value: str
    is_exact_match: bool  # True if matched canonical, False if matched synonym
    # Track field-level matches for precise field retrieval
    field_path: Optional[str] = None  # Field that has this value (for field-level synonyms)
    source: str = "concept"  # "concept" or "field" to indicate where the synonym came from

    def get_score(self, exact_score: float, synonym_score: float) -> float:
        """Get score based on match type"""
        return exact_score if self.is_exact_match else synonym_score

    def is_field_level(self) -> bool:
        """True if this match came from field-level value_synonyms"""
        return self.source == "field" and self.field_path is not None


@dataclass
class ValueSynonymIndex:
    """
    Fast lookup index for value synonyms and pronouns.

    Built from schema concepts, enables O(1) lookups for:
    - Value -> Concept mapping (e.g., "pending" -> order_status)
    - Pronoun -> Concept mapping (e.g., "my" -> requestor)

    Example:
        >>> index = ValueSynonymIndex()
        >>> index.build_from_schema(schema)
        >>> matches = index.lookup_value("waiting")
        >>> for m in matches:
        ...     print(f"{m.concept_name}: {m.canonical_value}")
        order_status: pending
    """
    # Value synonym index: lowercase value -> list of matches
    _value_map: Dict[str, List[ValueMatch]] = field(default_factory=dict)

    # Pronoun index: lowercase pronoun -> list of concept names
    _pronoun_map: Dict[str, List[str]] = field(default_factory=dict)

    # Reverse index: concept name -> set of indexed values
    _concept_values: Dict[str, Set[str]] = field(default_factory=dict)

    # Stats for debugging
    _stats: Dict[str, int] = field(default_factory=dict)

    def build_from_schema(self, schema: 'YAMLSchemaV1') -> None:
        """
        Build indexes from schema concepts AND field-level value_synonyms.

        Indexes both canonical values and their synonyms from:
        1. Concept-level value_synonyms (legacy, for backwards compatibility)
        2. Field-level value_synonyms (preferred for LLM context)

        Field-level synonyms are more specific and link values to actual fields,
        which is critical for query generation context.
        """
        self._value_map.clear()
        self._pronoun_map.clear()
        self._concept_values.clear()

        value_count = 0
        synonym_count = 0
        pronoun_count = 0
        field_value_count = 0
        field_synonym_count = 0

        # 1. Index concept-level value synonyms (backwards compatibility)
        for concept in schema.concepts:
            self._concept_values[concept.name] = set()

            # Index value synonyms from concept
            for canonical, synonyms in concept.value_synonyms.items():
                # Index the canonical value itself (exact match)
                self._add_value(
                    canonical.lower(),
                    ValueMatch(
                        concept_name=concept.name,
                        canonical_value=canonical,
                        is_exact_match=True,
                        field_path=None,
                        source="concept",
                    )
                )
                self._concept_values[concept.name].add(canonical.lower())
                value_count += 1

                # Index each synonym
                for syn in synonyms:
                    self._add_value(
                        syn.lower(),
                        ValueMatch(
                            concept_name=concept.name,
                            canonical_value=canonical,
                            is_exact_match=False,
                            field_path=None,
                            source="concept",
                        )
                    )
                    self._concept_values[concept.name].add(syn.lower())
                    synonym_count += 1

            # Index pronouns
            for pronoun in concept.related_pronouns:
                pronoun_lower = pronoun.lower()
                if pronoun_lower not in self._pronoun_map:
                    self._pronoun_map[pronoun_lower] = []
                if concept.name not in self._pronoun_map[pronoun_lower]:
                    self._pronoun_map[pronoun_lower].append(concept.name)
                    pronoun_count += 1

        # 2. Index field-level value synonyms (preferred)
        for index in schema.indices:
            for field_spec in index.fields:
                fv, fs = self._index_field_values(field_spec, index.name)
                field_value_count += fv
                field_synonym_count += fs
                # Also process nested fields
                for nested in field_spec.nested_fields:
                    nv, ns = self._index_field_values(nested, index.name)
                    field_value_count += nv
                    field_synonym_count += ns

        self._stats = {
            "canonical_values": value_count,
            "synonyms": synonym_count,
            "pronouns": pronoun_count,
            "field_values": field_value_count,
            "field_synonyms": field_synonym_count,
            "concepts_with_values": len([c for c in schema.concepts if c.value_synonyms]),
            "concepts_with_pronouns": len([c for c in schema.concepts if c.related_pronouns]),
            "fields_with_values": len([
                f for idx in schema.indices
                for f in idx.fields
                if f.value_synonyms
            ]),
        }

        logger.info(
            f"Built ValueSynonymIndex: {value_count} concept values, "
            f"{synonym_count} concept synonyms, {pronoun_count} pronouns, "
            f"{field_value_count} field values, {field_synonym_count} field synonyms"
        )

    def _index_field_values(
        self,
        field_spec: 'FieldSpec',
        index_name: str,
    ) -> Tuple[int, int]:
        """
        Index value_synonyms from a field.

        Field-level synonyms link directly to the field path, providing
        better context for LLM query generation.

        Returns:
            (value_count, synonym_count) for this field
        """
        if not field_spec.value_synonyms:
            return 0, 0

        value_count = 0
        synonym_count = 0

        # Determine concept name from field's maps_to attribute
        concept_name = field_spec.maps_to or field_spec.path.split('.')[0]

        for canonical, synonyms in field_spec.value_synonyms.items():
            # Index the canonical value (exact match, field-level)
            self._add_value(
                canonical.lower(),
                ValueMatch(
                    concept_name=concept_name,
                    canonical_value=canonical,
                    is_exact_match=True,
                    field_path=field_spec.path,
                    source="field",
                )
            )
            if concept_name not in self._concept_values:
                self._concept_values[concept_name] = set()
            self._concept_values[concept_name].add(canonical.lower())
            value_count += 1

            # Index each synonym
            for syn in synonyms:
                self._add_value(
                    syn.lower(),
                    ValueMatch(
                        concept_name=concept_name,
                        canonical_value=canonical,
                        is_exact_match=False,
                        field_path=field_spec.path,
                        source="field",
                    )
                )
                self._concept_values[concept_name].add(syn.lower())
                synonym_count += 1

        return value_count, synonym_count

    def _add_value(self, key: str, match: ValueMatch) -> None:
        """Add a value to the index"""
        if key not in self._value_map:
            self._value_map[key] = []
        # Avoid duplicates
        for existing in self._value_map[key]:
            if (existing.concept_name == match.concept_name and
                existing.canonical_value == match.canonical_value):
                return
        self._value_map[key].append(match)

    def lookup_value(self, keyword: str) -> List[ValueMatch]:
        """
        Find concepts where keyword is a value or synonym.

        Args:
            keyword: Value to search for (case-insensitive)

        Returns:
            List of ValueMatch objects with concept and canonical value
        """
        return self._value_map.get(keyword.lower(), [])

    def lookup_pronoun(self, pronoun: str) -> List[str]:
        """
        Find concepts referenced by a pronoun.

        Args:
            pronoun: Pronoun to search for (case-insensitive)

        Returns:
            List of concept names
        """
        return self._pronoun_map.get(pronoun.lower(), [])

    def find_pronouns_in_text(self, text: str) -> Dict[str, List[str]]:
        """
        Find all pronouns that appear in the text.

        Args:
            text: Text to search

        Returns:
            Dict of pronoun -> [concept_names]
        """
        text_lower = text.lower()
        found = {}

        for pronoun, concepts in self._pronoun_map.items():
            # Check for word boundaries to avoid false matches
            # e.g., "my" shouldn't match "mystery"
            if self._pronoun_in_text(pronoun, text_lower):
                found[pronoun] = concepts

        return found

    def _pronoun_in_text(self, pronoun: str, text: str) -> bool:
        """Check if pronoun appears as a word in text"""
        # Match pronoun as whole word
        pattern = r'\b' + re.escape(pronoun) + r'\b'
        return bool(re.search(pattern, text))

    def get_concept_values(self, concept_name: str) -> Set[str]:
        """Get all indexed values for a concept"""
        return self._concept_values.get(concept_name, set())

    def has_values(self) -> bool:
        """Check if any values are indexed"""
        return len(self._value_map) > 0

    def has_pronouns(self) -> bool:
        """Check if any pronouns are indexed"""
        return len(self._pronoun_map) > 0

    @property
    def stats(self) -> Dict[str, int]:
        """Get index statistics"""
        return self._stats.copy()

    def __repr__(self) -> str:
        return (
            f"ValueSynonymIndex("
            f"values={len(self._value_map)}, "
            f"pronouns={len(self._pronoun_map)})"
        )
