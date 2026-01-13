"""
OpenSearch Mapping to YAML Schema Converter.

Converts OpenSearch index mappings to the human-editable YAML schema format.
Supports:
- Flattening nested fields to dot-notation paths
- Auto-suggesting business concepts from field naming patterns
- Smart merging with existing YAML (preserving human annotations)
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from ...schema.yaml_schema import YAMLSchemaV1, ConceptSpec, FieldSpec, IndexSpec

logger = logging.getLogger(__name__)


CONCEPT_PATTERNS = [
    (r'^user\.', 'user'),
    (r'^customer\.', 'customer'),
    (r'^order\.', 'order'),
    (r'^orders\.', 'order'),
    (r'^product\.', 'product'),
    (r'^products\.', 'product'),
    (r'^item\.', 'item'),
    (r'^items\.', 'item'),
    (r'^transaction\.', 'transaction'),
    (r'^payment\.', 'payment'),
    (r'^shipping\.', 'shipping'),
    (r'^address\.', 'address'),
    (r'^billing\.', 'billing'),
    (r'^cart\.', 'cart'),
    (r'^session\.', 'session'),
    (r'^event\.', 'event'),
    (r'^log\.', 'log'),
    (r'^metric\.', 'metric'),
    (r'^error\.', 'error'),
    (r'^request\.', 'request'),
    (r'^response\.', 'response'),
    (r'^metadata\.', 'metadata'),
    (r'^config\.', 'config'),
    (r'^settings\.', 'settings'),
]

ID_PATTERNS = [
    r'.*_id$',
    r'.*Id$',
    r'^id$',
    r'.*_key$',
    r'.*_uuid$',
]

TIMESTAMP_PATTERNS = [
    r'.*_at$',
    r'.*_date$',
    r'.*_time$',
    r'^timestamp$',
    r'^created$',
    r'^updated$',
    r'^@timestamp$',
]


class MappingConverter:
    """
    Convert OpenSearch mappings to YAML schema format with smart merging.

    Usage:
        >>> converter = MappingConverter(mapping_json)
        >>> schema = converter.to_yaml_schema("orders-*", tenant_id="acme")
        >>> schema.to_yaml(Path("schema.yaml"))
    """

    def __init__(self, mapping_json: Dict[str, Any]):
        self.raw_mapping = mapping_json

    def to_yaml_schema(
        self,
        index_pattern: str,
        tenant_id: str,
        existing_schema: Optional["YAMLSchemaV1"] = None,
        infer_concepts: bool = True,
        query_mode: str = "PPL",
    ) -> "YAMLSchemaV1":
        """
        Convert mapping to YAML schema with optional merge.
        """
        from ...schema.yaml_schema import (
            YAMLSchemaV1, 
            IndexSpec, 
            FieldSpec, 
            ConceptSpec,
            QueryMode,
            SchemaType,
        )
        
        first_index = list(self.raw_mapping.keys())[0]
        mappings = self.raw_mapping[first_index].get("mappings", {})
        properties = mappings.get("properties", {})

        fields = self._flatten_properties(properties)
        logger.info(f"Flattened {len(fields)} fields from mapping")

        if existing_schema is None:
            schema = YAMLSchemaV1(
                tenant_id=tenant_id,
                version="1.0",
                schema_type=SchemaType.OPENSEARCH,
            )
        else:
            schema = existing_schema

        new_index = IndexSpec(
            name=index_pattern,
            description=f"Auto-imported from {first_index}",
            query_mode=QueryMode(query_mode) if isinstance(query_mode, str) else query_mode,
            fields=fields,
            timestamp_field=self._detect_timestamp_field(fields),
            primary_key=self._detect_primary_key(fields),
        )

        schema.merge_index(new_index, preserve_annotations=True)
        schema.last_synced = datetime.now()

        if infer_concepts:
            suggested = self._infer_concepts(fields)
            for concept in suggested:
                schema.add_concept(concept)
                self._auto_link_fields(schema, concept.name, concept.source_patterns)

        return schema

    def _flatten_properties(
        self,
        properties: Dict[str, Any],
        prefix: str = "",
    ) -> List["FieldSpec"]:
        from ...schema.yaml_schema import FieldSpec
        
        fields: List[FieldSpec] = []

        for field_name, field_config in properties.items():
            path = f"{prefix}.{field_name}" if prefix else field_name
            field_type = field_config.get("type", "object")

            nested_fields: List[FieldSpec] = []
            if field_type in ("nested", "object"):
                nested_props = field_config.get("properties", {})
                if nested_props:
                    nested_fields = self._flatten_properties(nested_props, path)

            field = FieldSpec(
                path=path,
                es_type=field_type,
                description=None,
                maps_to=None,
                nested_fields=nested_fields,
                auto_imported=True,
                last_updated=datetime.now(),
                searchable=field_type in ("text", "keyword", "nested"),
                aggregatable=field_type in ("keyword", "long", "integer", "float", "date", "boolean"),
            )

            fields.append(field)

        return fields

    def _infer_concepts(self, fields: List["FieldSpec"]) -> List["ConceptSpec"]:
        from ...schema.yaml_schema import ConceptSpec
        
        concept_matches: Dict[str, Set[str]] = defaultdict(set)
        concept_patterns_used: Dict[str, List[str]] = defaultdict(list)

        all_paths = []
        for field in fields:
            all_paths.append(field.path)
            for nested in field.nested_fields:
                all_paths.append(nested.path)

        for path in all_paths:
            for pattern, concept_name in CONCEPT_PATTERNS:
                if re.match(pattern, path, re.IGNORECASE):
                    concept_matches[concept_name].add(path)
                    if pattern not in concept_patterns_used[concept_name]:
                        concept_patterns_used[concept_name].append(pattern)

        prefix_counts: Dict[str, int] = defaultdict(int)
        for path in all_paths:
            if '.' in path:
                prefix = path.split('.')[0]
                prefix_counts[prefix] += 1

        for prefix, count in prefix_counts.items():
            if count >= 2:
                normalized = prefix.lower().rstrip('s')
                if normalized not in concept_matches:
                    concept_matches[normalized] = {
                        p for p in all_paths if p.startswith(f"{prefix}.")
                    }
                    concept_patterns_used[normalized].append(f"^{prefix}\\.")

        concepts: List[ConceptSpec] = []
        for concept_name, matched_paths in concept_matches.items():
            if len(matched_paths) >= 1:
                confidence = min(1.0, len(matched_paths) / 5.0)

                concept = ConceptSpec(
                    name=concept_name,
                    description=f"Auto-suggested from field pattern",
                    aliases=[],
                    related_to=[],
                    auto_suggested=True,
                    confidence=confidence,
                    source_patterns=concept_patterns_used.get(concept_name, []),
                )
                concepts.append(concept)

        concepts.sort(key=lambda c: c.confidence, reverse=True)
        return concepts

    def _auto_link_fields(
        self,
        schema: "YAMLSchemaV1",
        concept_name: str,
        patterns: List[str],
    ) -> None:
        for idx in schema.indices:
            for field in idx.fields:
                if field.maps_to is None:
                    for pattern in patterns:
                        if re.match(pattern, field.path, re.IGNORECASE):
                            field.maps_to = concept_name
                            break

                for nested in field.nested_fields:
                    if nested.maps_to is None:
                        for pattern in patterns:
                            if re.match(pattern, nested.path, re.IGNORECASE):
                                nested.maps_to = concept_name
                                break

    def _detect_timestamp_field(self, fields: List["FieldSpec"]) -> Optional[str]:
        for field in fields:
            for pattern in TIMESTAMP_PATTERNS:
                if re.match(pattern, field.path, re.IGNORECASE):
                    if field.es_type == "date":
                        return field.path
        return None

    def _detect_primary_key(self, fields: List["FieldSpec"]) -> Optional[str]:
        for field in fields:
            if field.path in ("id", "_id", "uuid"):
                return field.path
            if field.es_type == "keyword":
                for pattern in ID_PATTERNS:
                    if re.match(pattern, field.path, re.IGNORECASE):
                        return field.path
        return None


def import_mapping_from_file(
    mapping_path: Path,
    index_pattern: str,
    tenant_id: str,
    output_path: Optional[Path] = None,
    merge_existing: bool = True,
    infer_concepts: bool = True,
) -> "YAMLSchemaV1":
    """
    Convenience function to import mapping from JSON file.
    """
    import json
    from ...schema.yaml_schema import YAMLSchemaV1

    with open(mapping_path, 'r') as f:
        mapping_json = json.load(f)

    converter = MappingConverter(mapping_json)

    existing = None
    if merge_existing and output_path and output_path.exists():
        existing = YAMLSchemaV1.from_yaml(output_path)
        logger.info(f"Loaded existing schema from {output_path}")

    schema = converter.to_yaml_schema(
        index_pattern=index_pattern,
        tenant_id=tenant_id,
        existing_schema=existing,
        infer_concepts=infer_concepts,
    )

    if output_path:
        schema.to_yaml(output_path)
        logger.info(f"Saved schema to {output_path}")

    return schema
