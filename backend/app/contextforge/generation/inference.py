"""
LLM-powered inference pipeline for schema analysis and metadata generation.

Includes:
- SchemaAnalyzer: Complexity detection and entity extraction
- FieldMetadataInferencer: Rich field metadata generation
- QAGenerator: Diverse Q&A example generation
- InferenceValidator: Quality scoring and validation

This module uses the app's InferenceClient for LLM calls.
"""

import json
import logging
import re
from typing import Any, List, Optional

from ..core.models import (
    Complexity,
    ComplexityReport,
    EntityMetadata,
    QueryType,
    ValidationResult,
    APIEndpointMetadata,
)
from ..schema.field_schema import FieldSpec
from ..schema.example_schema import ExampleSpec, ExampleContent
from .prompt_templates import (
    get_schema_analysis_prompt,
    get_field_inference_prompt,
    get_qa_generation_prompt,
    get_prompt_config,
)

logger = logging.getLogger(__name__)


class SchemaAnalyzer:
    """
    Analyze raw schema and determine processing strategy.

    Complexity Rules:
    - EASY: 1-2 entities, <20 fields total, no relationships
    - MEDIUM: 1 entity with 50+ fields OR 3-10 entities
    - COMPLEX: >10 entities OR relationships OR >200 fields
    """

    def __init__(
        self, llm_client: Optional[Any] = None, prompt_manager: Optional[Any] = None
    ):
        """
        Initialize schema analyzer.

        Args:
            llm_client: LLM client for schema parsing (optional, uses heuristics if None)
            prompt_manager: Langfuse prompt manager (optional, falls back to local templates)
        """
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager

    def _get_dialect_from_query_type(self, query_type: QueryType) -> str:
        """Map QueryType to dialect name for prompt selection."""
        dialect_map = {
            QueryType.POSTGRES: "postgres",
            QueryType.MYSQL: "mysql",
            QueryType.OPENSEARCH: "opensearch",
            QueryType.ELASTICSEARCH: "opensearch",
            QueryType.SQL_SERVER: "default",
            QueryType.ORACLE: "default",
            QueryType.MONGODB: "default",
            QueryType.REST_API: "default",
        }
        return dialect_map.get(query_type, "default")

    def _llm_analyze_schema(
        self,
        raw_schema: str,
        query_type: QueryType,
        business_domain: str = "",
        business_description: str = "",
    ) -> tuple[Optional[List[EntityMetadata]], Optional[List[str]]]:
        """
        Use LLM to analyze schema and extract entities.

        Args:
            raw_schema: Raw schema definition
            query_type: Type of query language
            business_domain: Business domain for context
            business_description: Business description for context

        Returns:
            Tuple of (entities, field_names) or (None, None) on failure
        """
        dialect = self._get_dialect_from_query_type(query_type)

        try:
            if self.prompt_manager:
                prompt_name = f"sql-{dialect}-schema-analysis-v1"
                prompt_text, config = self.prompt_manager.get_prompt(
                    document_name=prompt_name,
                    variables={
                        "raw_schema": raw_schema,
                        "business_domain": business_domain or "General",
                        "business_description": business_description or "No description provided",
                    },
                )
                logger.info(f"Using Langfuse prompt: {prompt_name}")
            else:
                prompt_template = get_schema_analysis_prompt(dialect)
                prompt_text = prompt_template.format(
                    raw_schema=raw_schema,
                    business_domain=business_domain or "General",
                    business_description=business_description or "No description provided",
                    dialect=query_type.value,
                )
                logger.info(f"Using local template for dialect: {dialect}")

            # Call LLM
            response = self.llm_client.submit_prompt(
                [
                    self.llm_client.system_message(
                        "You are a database schema analyzer. Return ONLY valid JSON."
                    ),
                    self.llm_client.user_message(prompt_text),
                ]
            )

            # Parse JSON response
            schema_data = json.loads(response)

            # Convert to EntityMetadata
            entities = []
            all_fields = []

            entity_name = schema_data.get("entity_name", "unknown")
            entity_type = schema_data.get("entity_type", "table")
            fields_data = schema_data.get("fields", [])
            relationships_data = schema_data.get("relationships", [])

            # Create FieldSpec objects
            field_specs = []
            for field_data in fields_data:
                field_name = field_data.get("name")
                field_type = field_data.get("type")
                description = field_data.get("description", "")

                field = FieldSpec(
                    name=field_name,
                    qualified_name=f"{entity_name}.{field_name}",
                    type=field_type,
                    description=description,
                    business_meaning="",  # To be inferred in next step
                )
                field_specs.append(field)
                all_fields.append(f"{entity_name}.{field_name}")

            # Create Relationship list
            from ..core.models import Relationship

            relationships = []
            for rel_data in relationships_data:
                rel = Relationship(
                    from_field=rel_data.get("source_field", ""),
                    to_entity=rel_data.get("target_entity", ""),
                    to_field=rel_data.get("target_field", ""),
                    relationship_type=rel_data.get("type", "UNKNOWN"),
                )
                relationships.append(rel)

            # Create EntityMetadata
            entity = EntityMetadata(
                name=entity_name,
                type=entity_type.lower(),
                fields=field_specs,
                relationships=relationships,
                description=schema_data.get("notes", f"{entity_type} {entity_name}"),
            )
            entities.append(entity)

            logger.info(
                f"LLM analyzed schema: {len(entities)} entities, {len(all_fields)} fields"
            )
            return entities, all_fields

        except Exception as e:
            logger.warning(
                f"LLM schema analysis failed: {e}, falling back to regex parsing"
            )
            return None, None

    def analyze_schema(
        self,
        raw_schema: str,
        query_type: QueryType,
        business_domain: str = "",
        business_description: str = "",
    ) -> ComplexityReport:
        """
        Parse schema and determine complexity.

        Args:
            raw_schema: Raw schema definition (DDL, JSON mapping, OpenAPI spec)
            query_type: Type of query language
            business_domain: Business domain for context (optional)
            business_description: Business description for context (optional)

        Returns:
            ComplexityReport with complexity level and parsed entities
        """
        logger.info(f"Analyzing schema for query_type: {query_type.value}")

        entities: Optional[List[EntityMetadata]] = None
        fields: Optional[List[str]] = None

        # Try LLM-based analysis first if LLM client is available
        if self.llm_client:
            entities, fields = self._llm_analyze_schema(
                raw_schema, query_type, business_domain, business_description
            )

        # Fall back to regex parsing if LLM not available or failed
        if entities is None:
            if query_type in [
                QueryType.SQL_SERVER,
                QueryType.MYSQL,
                QueryType.POSTGRES,
                QueryType.ORACLE,
                QueryType.SQLITE,
                QueryType.CLICKHOUSE,
            ]:
                entities, fields = self._parse_sql_schema(raw_schema)
            elif query_type in [QueryType.OPENSEARCH, QueryType.ELASTICSEARCH]:
                entities, fields = self._parse_opensearch_schema(raw_schema)
            elif query_type == QueryType.MONGODB:
                entities, fields = self._parse_nosql_schema(raw_schema)
            elif query_type == QueryType.REST_API:
                entities, fields = self._parse_api_schema(raw_schema)
            else:
                logger.warning(f"Unsupported query_type: {query_type}")
                entities, fields = [], []

        # Ensure we have valid lists
        entities = entities or []
        fields = fields or []

        # Calculate complexity
        total_entities = len(entities)
        total_fields = len(fields)
        max_fields_per_entity = (
            max(len(entity.fields) for entity in entities) if entities else 0
        )
        has_relationships = any(len(entity.relationships) > 0 for entity in entities)

        # Determine complexity level
        if total_entities <= 2 and total_fields < 20 and not has_relationships:
            complexity = Complexity.EASY
        elif (total_entities == 1 and total_fields >= 50) or (3 <= total_entities <= 10):
            complexity = Complexity.MEDIUM
        else:
            complexity = Complexity.COMPLEX

        logger.info(
            f"Schema complexity: {complexity.value} ({total_entities} entities, {total_fields} fields)"
        )

        return ComplexityReport(
            total_entities=total_entities,
            total_fields=total_fields,
            max_fields_per_entity=max_fields_per_entity,
            has_relationships=has_relationships,
            complexity=complexity,
            entities=entities,
            fields=fields,
            entity_context=self._build_entity_context(entities),
        )

    def _parse_sql_schema(self, ddl: str) -> tuple[List[EntityMetadata], List[str]]:
        """Parse SQL DDL into entities and fields."""
        entities = []
        all_fields: List[str] = []

        # Simple regex-based parsing
        create_table_pattern = r"CREATE TABLE\s+(\w+)\s*\((.*?)\);"
        matches = re.finditer(create_table_pattern, ddl, re.IGNORECASE | re.DOTALL)

        for match in matches:
            table_name = match.group(1)
            columns_text = match.group(2)

            # Parse columns
            field_specs = []
            column_pattern = r"(\w+)\s+(\w+(?:\([^)]+\))?)"
            for col_match in re.finditer(column_pattern, columns_text):
                field_name = col_match.group(1)
                field_type = col_match.group(2)

                field = FieldSpec(
                    name=field_name,
                    qualified_name=f"{table_name}.{field_name}",
                    type=field_type,
                    description=f"Column {field_name} in table {table_name}",
                )
                field_specs.append(field)
                all_fields.append(f"{table_name}.{field_name}")

            entity = EntityMetadata(
                name=table_name,
                type="table",
                fields=field_specs,
                relationships=[],
                description=f"Table {table_name}",
            )
            entities.append(entity)

        logger.debug(f"Parsed {len(entities)} SQL tables with {len(all_fields)} fields")
        return entities, all_fields

    def _parse_opensearch_schema(
        self, mapping: str
    ) -> tuple[List[EntityMetadata], List[str]]:
        """Parse OpenSearch mapping JSON into entities and fields."""
        try:
            mapping_dict = json.loads(mapping)
        except json.JSONDecodeError:
            logger.error("Failed to parse OpenSearch mapping JSON")
            return [], []

        entities = []
        all_fields: List[str] = []

        # Mapping format: {"index_name": {"mappings": {"properties": {...}}}}
        for index_name, index_config in mapping_dict.items():
            properties = index_config.get("mappings", {}).get("properties", {})

            field_specs = []
            for field_name, field_config in properties.items():
                field_type = field_config.get("type", "text")

                field = FieldSpec(
                    name=field_name,
                    qualified_name=f"{index_name}.{field_name}",
                    type=field_type,
                    description=f"Field {field_name} in index {index_name}",
                )
                field_specs.append(field)
                all_fields.append(f"{index_name}.{field_name}")

            entity = EntityMetadata(
                name=index_name,
                type="index",
                fields=field_specs,
                relationships=[],
                description=f"OpenSearch index {index_name}",
            )
            entities.append(entity)

        logger.debug(
            f"Parsed {len(entities)} OpenSearch indexes with {len(all_fields)} fields"
        )
        return entities, all_fields

    def _parse_nosql_schema(
        self, schema: str
    ) -> tuple[List[EntityMetadata], List[str]]:
        """Parse NoSQL schema (MongoDB collection schemas)."""
        try:
            schema_dict = json.loads(schema)
        except json.JSONDecodeError:
            return [], []

        entities = []
        all_fields: List[str] = []

        for collection_name, collection_schema in schema_dict.items():
            properties = collection_schema.get("properties", {})

            field_specs = []
            for field_name, field_config in properties.items():
                field_type = field_config.get("bsonType", "string")

                field = FieldSpec(
                    name=field_name,
                    qualified_name=f"{collection_name}.{field_name}",
                    type=field_type,
                    description=f"Field {field_name} in collection {collection_name}",
                )
                field_specs.append(field)
                all_fields.append(f"{collection_name}.{field_name}")

            entity = EntityMetadata(
                name=collection_name,
                type="collection",
                fields=field_specs,
                relationships=[],
                description=f"MongoDB collection {collection_name}",
            )
            entities.append(entity)

        return entities, all_fields

    def _parse_api_schema(
        self, openapi_spec: str
    ) -> tuple[List[EntityMetadata], List[str]]:
        """Parse OpenAPI/REST API specification into endpoints and fields."""
        try:
            spec_dict = json.loads(openapi_spec)
        except json.JSONDecodeError:
            return [], []

        entities = []
        all_fields: List[str] = []

        endpoints = spec_dict.get("endpoints", [])

        for endpoint in endpoints:
            endpoint_name = endpoint.get("name")
            response_schema = endpoint.get("response_schema", {}).get("items", {})

            field_specs = []
            for field_name, field_type in response_schema.items():
                field = FieldSpec(
                    name=field_name,
                    qualified_name=f"{endpoint_name}.{field_name}",
                    type=field_type,
                    description=f"Field {field_name} from endpoint {endpoint_name}",
                )
                field_specs.append(field)
                all_fields.append(f"{endpoint_name}.{field_name}")

            entity = EntityMetadata(
                name=endpoint_name,
                type="endpoint",
                fields=field_specs,
                relationships=[],
                description=endpoint.get("description", f"Endpoint {endpoint_name}"),
                metadata=APIEndpointMetadata(
                    http_method=endpoint.get("method", "GET"),
                    endpoint_path=endpoint.get("path", f"/{endpoint_name}"),
                    query_parameters=endpoint.get("query_parameters", []),
                ),
            )
            entities.append(entity)

        return entities, all_fields

    def _build_entity_context(self, entities: List[EntityMetadata]) -> str:
        """Build textual context about entities for inference."""
        lines = []
        for entity in entities:
            lines.append(f"Entity: {entity.name} (type: {entity.type})")
            lines.append(f"  Description: {entity.description}")
            lines.append(f"  Fields: {', '.join(f.name for f in entity.fields)}")
        return "\n".join(lines)


class FieldMetadataInferencer:
    """LLM-powered field metadata generation."""

    def __init__(self, llm_client: Any, prompt_manager: Optional[Any] = None):
        """
        Initialize field metadata inferencer.

        Args:
            llm_client: LLM client with submit_prompt method
            prompt_manager: Langfuse prompt manager (optional)
        """
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager

    def _get_dialect_from_query_type(self, query_type: QueryType) -> str:
        """Map QueryType to dialect name for prompt selection."""
        dialect_map = {
            QueryType.POSTGRES: "postgres",
            QueryType.MYSQL: "mysql",
            QueryType.OPENSEARCH: "opensearch",
            QueryType.ELASTICSEARCH: "opensearch",
            QueryType.SQL_SERVER: "default",
            QueryType.ORACLE: "default",
            QueryType.MONGODB: "default",
            QueryType.REST_API: "default",
        }
        return dialect_map.get(query_type, "default")

    async def infer_field_metadata(
        self,
        field_name: str,
        field_type: str,
        field_constraints: str,
        entity_name: str,
        business_domain: str,
        query_type: QueryType,
    ) -> FieldSpec:
        """
        Generate rich metadata for a single field using LLM.

        Args:
            field_name: Name of the field
            field_type: Data type of the field
            field_constraints: Constraints on the field
            entity_name: Parent entity/table name
            business_domain: Business domain for context
            query_type: Type of query language

        Returns:
            FieldSpec with LLM-inferred descriptions
        """
        dialect = self._get_dialect_from_query_type(query_type)

        try:
            if self.prompt_manager:
                prompt_name = f"sql-{dialect}-field-inference-v1"
                prompt_text, config = self.prompt_manager.get_prompt(
                    document_name=prompt_name,
                    variables={
                        "field_name": field_name,
                        "field_type": field_type,
                        "field_constraints": field_constraints or "None",
                        "table_name": entity_name if dialect != "opensearch" else None,
                        "index_name": entity_name if dialect == "opensearch" else None,
                        "entity_name": entity_name,
                        "business_domain": business_domain or "General",
                        "field_properties": field_constraints if dialect == "opensearch" else None,
                        "dialect": query_type.value,
                    },
                )
                logger.info(f"Using Langfuse prompt: {prompt_name}")
            else:
                prompt_template = get_field_inference_prompt(dialect)
                if dialect == "opensearch":
                    prompt_text = prompt_template.format(
                        field_name=field_name,
                        field_type=field_type,
                        field_properties=field_constraints or "None",
                        index_name=entity_name,
                        business_domain=business_domain or "General",
                    )
                else:
                    prompt_text = prompt_template.format(
                        field_name=field_name,
                        field_type=field_type,
                        field_constraints=field_constraints or "None",
                        table_name=entity_name,
                        business_domain=business_domain or "General",
                    )
                logger.info(f"Using local template for dialect: {dialect}")

            response = self.llm_client.submit_prompt(
                [
                    self.llm_client.system_message(
                        "You are a field metadata expert. Return ONLY valid JSON."
                    ),
                    self.llm_client.user_message(prompt_text),
                ]
            )

            # Parse response
            metadata_dict = json.loads(response)

            field = FieldSpec(
                name=field_name,
                qualified_name=f"{entity_name}.{field_name}",
                type=field_type,
                description=metadata_dict.get("description", ""),
                business_meaning=metadata_dict.get("business_meaning", ""),
                allowed_values=metadata_dict.get("allowed_values", []),
                value_examples=metadata_dict.get("value_examples", []),
                value_encoding=metadata_dict.get("value_encoding"),
                aliases=metadata_dict.get("aliases", []),
                search_guidance=metadata_dict.get("search_guidance", ""),
            )

            logger.info(f"Inferred metadata for field: {field_name}")
            return field

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response for field {field_name}: {e}")
            return FieldSpec(
                name=field_name,
                qualified_name=f"{entity_name}.{field_name}",
                type=field_type,
                description=f"Field {field_name}",
            )
        except Exception as e:
            logger.error(f"Error inferring metadata for field {field_name}: {e}")
            return FieldSpec(
                name=field_name,
                qualified_name=f"{entity_name}.{field_name}",
                type=field_type,
                description=f"Field {field_name}",
            )

    async def batch_infer_fields(
        self,
        fields: List[FieldSpec],
        entity_name: str,
        business_domain: str,
        query_type: QueryType,
        batch_size: int = 10,
    ) -> List[FieldSpec]:
        """
        Batch process fields to reduce LLM calls.

        Args:
            fields: List of FieldSpec objects with basic info
            entity_name: Parent entity name
            business_domain: Business domain for context
            query_type: Query type
            batch_size: Number of fields per batch

        Returns:
            List of enriched FieldSpec with LLM-inferred details
        """
        logger.info(f"Inferring metadata for {len(fields)} fields")

        field_specs = []
        for i in range(0, len(fields), batch_size):
            batch = fields[i : i + batch_size]
            for field in batch:
                field_meta = await self.infer_field_metadata(
                    field_name=field.name,
                    field_type=str(field.type),
                    field_constraints="",
                    entity_name=entity_name,
                    business_domain=business_domain,
                    query_type=query_type,
                )
                field_specs.append(field_meta)

        logger.info(f"Completed inference for {len(field_specs)} fields")
        return field_specs


class QAGenerator:
    """Generate training Q&A pairs from schema."""

    def __init__(self, llm_client: Any, prompt_manager: Optional[Any] = None):
        """
        Initialize Q&A generator.

        Args:
            llm_client: LLM client with submit_prompt method
            prompt_manager: Langfuse prompt manager (optional)
        """
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager

    def _get_dialect_from_query_type(self, query_type: QueryType) -> str:
        """Map QueryType to dialect name for prompt selection."""
        dialect_map = {
            QueryType.POSTGRES: "postgres",
            QueryType.MYSQL: "mysql",
            QueryType.OPENSEARCH: "opensearch",
            QueryType.ELASTICSEARCH: "opensearch",
            QueryType.SQL_SERVER: "default",
            QueryType.ORACLE: "default",
            QueryType.MONGODB: "default",
            QueryType.REST_API: "default",
        }
        return dialect_map.get(query_type, "default")

    async def generate_qa_pairs(
        self,
        schema_metadata: List[FieldSpec],
        entity_metadata: List[EntityMetadata],
        query_type: QueryType,
        business_documentation: str = "",
        target_count: int = 20,
    ) -> List[ExampleSpec]:
        """
        Generate diverse Q&A examples using LLM.

        Args:
            schema_metadata: Field metadata
            entity_metadata: Entity metadata
            query_type: Query type
            business_documentation: Additional business context
            target_count: Target number of examples

        Returns:
            List of ExampleSpec with diverse query examples
        """
        logger.info(
            f"Generating {target_count} Q&A pairs for {query_type.value} schema using LLM"
        )

        dialect = self._get_dialect_from_query_type(query_type)

        # Build schema context
        schema_context = self._build_schema_context(entity_metadata)
        field_metadata_context = self._build_field_metadata_context(schema_metadata)

        try:
            if self.prompt_manager:
                prompt_name = f"sql-{dialect}-qa-generation-v1"
                prompt_text, config = self.prompt_manager.get_prompt(
                    document_name=prompt_name,
                    variables={
                        "schema_context": schema_context,
                        "field_metadata": field_metadata_context,
                        "business_documentation": business_documentation or "No additional documentation",
                    },
                )
                logger.info(f"Using Langfuse prompt: {prompt_name}")
            else:
                prompt_template = get_qa_generation_prompt(dialect)
                prompt_text = prompt_template.format(
                    schema_context=schema_context,
                    field_metadata=field_metadata_context,
                    business_documentation=business_documentation or "No additional documentation",
                    dialect=query_type.value,
                )
                logger.info(f"Using local template for dialect: {dialect}")

            # Call LLM
            response = self.llm_client.submit_prompt(
                [
                    self.llm_client.system_message(
                        "You are a query generation expert. Return ONLY valid JSON array."
                    ),
                    self.llm_client.user_message(prompt_text),
                ]
            )

            # Parse JSON response
            qa_data = json.loads(response)

            # Convert to ExampleSpec objects
            qa_pairs = []
            for qa_item in qa_data[:target_count]:
                question = qa_item.get("question", "")
                query = qa_item.get("sql") or qa_item.get("dsl") or qa_item.get("query", "")
                complexity = qa_item.get("complexity", "MEDIUM")
                explanation = qa_item.get("explanation", "")

                # Map complexity to confidence
                confidence_map = {"EASY": 0.9, "MEDIUM": 0.8, "HARD": 0.7}
                confidence = confidence_map.get(complexity, 0.8)

                qa_pairs.append(
                    ExampleSpec(
                        title=question,
                        source="llm_generated",
                        content=ExampleContent(
                            query=query,
                            query_type=query_type.value,
                            explanation=explanation,
                        ),
                        confidence=confidence,
                        entities_involved=[e.name for e in entity_metadata],
                        fields_involved=[f.name for f in schema_metadata],
                        operations=self._extract_operations(query),
                    )
                )

            logger.info(f"Generated {len(qa_pairs)} Q&A pairs using LLM")
            return qa_pairs

        except Exception as e:
            logger.error(f"LLM Q&A generation failed: {e}, falling back to templates")
            return self._generate_template_qa_pairs(entity_metadata, query_type)

    def _build_schema_context(self, entity_metadata: List[EntityMetadata]) -> str:
        """Build schema context string from entity metadata."""
        lines = []
        for entity in entity_metadata:
            lines.append(f"Entity: {entity.name} (type: {entity.type})")
            lines.append(f"  Description: {entity.description}")
            lines.append("  Fields:")
            for field in entity.fields:
                field_type = field.type if hasattr(field, "type") else "unknown"
                lines.append(f"    - {field.name} ({field_type})")
            if entity.relationships:
                lines.append("  Relationships:")
                for rel in entity.relationships:
                    lines.append(
                        f"    - {rel.relationship_type}: {rel.from_field} -> {rel.to_entity}.{rel.to_field}"
                    )
        return "\n".join(lines)

    def _build_field_metadata_context(self, schema_metadata: List[FieldSpec]) -> str:
        """Build field metadata context string."""
        lines = []
        for field in schema_metadata:
            lines.append(f"Field: {field.qualified_name}")
            if field.business_meaning:
                lines.append(f"  Business Meaning: {field.business_meaning}")
            if field.search_guidance:
                lines.append(f"  Search Guidance: {field.search_guidance}")
            if field.value_examples:
                lines.append(f"  Example Values: {', '.join(field.value_examples)}")
        return "\n".join(lines)

    def _extract_operations(self, query: str) -> List[str]:
        """Extract SQL/DSL operations from query."""
        operations = []
        query_upper = query.upper()

        keywords = [
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "JOIN",
            "WHERE",
            "GROUP BY",
            "ORDER BY",
            "HAVING",
            "LIMIT",
        ]
        for keyword in keywords:
            if keyword in query_upper:
                operations.append(keyword)

        return operations if operations else ["UNKNOWN"]

    def _generate_template_qa_pairs(
        self, entity_metadata: List[EntityMetadata], query_type: QueryType
    ) -> List[ExampleSpec]:
        """Fallback template-based Q&A generation."""
        qa_pairs = []

        for entity in entity_metadata[:10]:
            question = f"Get all {entity.name} records"
            query = f"SELECT * FROM {entity.name}"

            qa_pairs.append(
                ExampleSpec(
                    title=question,
                    source="template_generated",
                    content=ExampleContent(
                        query=query,
                        query_type=query_type.value,
                        explanation=f"Simple select from {entity.name}",
                    ),
                    confidence=0.7,
                    entities_involved=[entity.name],
                    fields_involved=[f.name for f in entity.fields],
                    operations=["SELECT"],
                )
            )

        logger.info(f"Generated {len(qa_pairs)} template Q&A pairs")
        return qa_pairs


class InferenceValidator:
    """
    Validate LLM-generated metadata before storage.

    Uses comprehensive domain-specific validation rules to ensure
    high-quality metadata for query generation.
    """

    def validate_field_metadata(self, metadata: FieldSpec) -> ValidationResult:
        """
        Validate field metadata quality with essential, dialect-agnostic checks.

        Validation Categories:
        - Required field presence
        - Minimum description length
        - Value examples presence (warning only)
        - Business meaning presence (warning only)

        Args:
            metadata: Field metadata to validate

        Returns:
            ValidationResult with is_valid, quality_score, issues, and warnings
        """
        issues = []
        warnings = []

        # Required fields validation
        if not metadata.name:
            issues.append("Missing required field: name")
        if not metadata.type:
            issues.append("Missing required field: type")

        # Minimum description length
        if metadata.description and len(metadata.description) < 10:
            issues.append(f"Field {metadata.name}: Description too short (< 10 chars)")
        elif not metadata.description:
            issues.append(f"Field {metadata.name}: Missing description")

        # Value examples - helpful for query generation (warning only)
        if not metadata.value_examples:
            warnings.append(
                f"Field {metadata.name}: No value examples provided - examples improve query accuracy"
            )
        elif len(metadata.value_examples) == 1:
            warnings.append(
                f"Field {metadata.name}: Only 1 example - recommend 2-3 diverse examples"
            )

        # Business meaning - improves semantic understanding (warning only)
        if not metadata.business_meaning or len(metadata.business_meaning) < 10:
            warnings.append(
                f"Field {metadata.name}: Missing or brief business meaning"
            )

        # Calculate quality score
        quality_score = self._calculate_quality_score(metadata, issues, warnings)

        return ValidationResult(
            is_valid=len(issues) == 0,
            quality_score=quality_score,
            issues=issues,
            warnings=warnings,
        )

    def _calculate_quality_score(
        self, metadata: FieldSpec, issues: List[str], warnings: List[str]
    ) -> float:
        """
        Calculate quality score with objective factors.

        Scoring:
        - Base: 100 points
        - Each issue: -30 points
        - Each warning: -5 points
        - Bonus for completeness: Up to +15 points
        """
        score = 100.0

        # Deduct for critical issues
        score -= len(issues) * 30

        # Deduct for warnings
        score -= len(warnings) * 5

        # Bonus for helpful optional fields
        completeness_bonus = 0
        if metadata.business_meaning and len(metadata.business_meaning) >= 10:
            completeness_bonus += 5
        if metadata.search_guidance and len(metadata.search_guidance) >= 10:
            completeness_bonus += 5
        if metadata.value_examples and len(metadata.value_examples) >= 2:
            completeness_bonus += 3
        if metadata.aliases:
            completeness_bonus += 2

        score += completeness_bonus

        return max(0.0, min(100.0, score))

    def quality_score(
        self,
        field_specs: List[FieldSpec],
        qa_pairs: List[ExampleSpec],
    ) -> float:
        """
        Calculate overall quality score (0-100).

        Factors:
        - Field coverage (% of fields with rich metadata)
        - Q&A diversity
        - Validation pass rate
        - Confidence scores
        """
        if not field_specs:
            return 0.0

        # Field coverage score
        rich_fields = sum(
            1 for f in field_specs if f.business_meaning and f.search_guidance
        )
        coverage_score = (rich_fields / len(field_specs)) * 100

        # Q&A confidence score
        if qa_pairs:
            avg_confidence = sum(qa.confidence for qa in qa_pairs) / len(qa_pairs)
            confidence_score = avg_confidence * 100
        else:
            confidence_score = 0

        # Weighted average
        overall_score = (coverage_score * 0.6) + (confidence_score * 0.4)

        logger.info(f"Quality score: {overall_score:.2f}/100")
        return overall_score
