"""
Fallback Prompt Templates for ContextForge.

This module provides default prompt templates that are used when Langfuse is unavailable.
These templates support multiple dialects (postgres, mysql, opensearch, rest_api, default).

Each template is organized by:
1. Operation type (schema_analysis, field_inference, qa_generation, query_generation)
2. Dialect (postgres, mysql, opensearch, default)

Usage:
    from app.contextforge.generation.prompt_templates import SCHEMA_ANALYSIS_PROMPTS
    
    prompt_template = SCHEMA_ANALYSIS_PROMPTS['postgres']
    filled_prompt = prompt_template.format(
        raw_schema=schema,
        business_domain=domain,
        business_description=description
    )
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..retrieval.context import RetrievalContext
    from ..schema.api_schema import EndpointSpec

# ============================================================================
# SCHEMA ANALYSIS PROMPTS
# ============================================================================

SCHEMA_ANALYSIS_PROMPTS: Dict[str, str] = {
    "postgres": """You are an expert PostgreSQL database schema analyzer.

=== SCHEMA TO ANALYZE ===
{raw_schema}

=== BUSINESS CONTEXT ===
Business Domain: {business_domain}
Description: {business_description}

=== TASK ===
Analyze the schema above and extract structured information.

Return a JSON object with the following structure:
{{
  "entity_name": "string (table/collection name)",
  "entity_type": "string (TABLE, VIEW, INDEX, etc.)",
  "fields": [
    {{
      "name": "string (field name)",
      "type": "string (PostgreSQL data type)",
      "constraints": ["string (PRIMARY KEY, NOT NULL, UNIQUE, etc.)"],
      "description": "string (inferred purpose)"
    }}
  ],
  "relationships": [
    {{
      "type": "string (FOREIGN_KEY, ONE_TO_MANY, etc.)",
      "target_entity": "string (related table name)",
      "source_field": "string",
      "target_field": "string"
    }}
  ],
  "complexity": "string (EASY, MEDIUM, or COMPLEX)",
  "notes": "string (any important observations)"
}}

=== ANALYSIS GUIDELINES ===
1. Identify all fields with their PostgreSQL-specific types (SERIAL, JSONB, ARRAY, etc.)
2. Extract constraints (PRIMARY KEY, FOREIGN KEY, NOT NULL, UNIQUE, CHECK)
3. Identify relationships by analyzing foreign key constraints
4. Assess complexity based on number of fields and relationships
5. Note any PostgreSQL-specific features (triggers, partitions, indexes)

Return ONLY valid JSON, no explanations or markdown.""",
    "mysql": """You are an expert MySQL database schema analyzer.

=== SCHEMA TO ANALYZE ===
{raw_schema}

=== BUSINESS CONTEXT ===
Business Domain: {business_domain}
Description: {business_description}

=== TASK ===
Analyze the schema above and extract structured information.

Return a JSON object with the following structure:
{{
  "entity_name": "string (table name)",
  "entity_type": "string (TABLE, VIEW, INDEX, etc.)",
  "fields": [
    {{
      "name": "string (field name)",
      "type": "string (MySQL data type)",
      "constraints": ["string (PRIMARY KEY, NOT NULL, UNIQUE, etc.)"],
      "description": "string (inferred purpose)"
    }}
  ],
  "relationships": [...],
  "complexity": "string (EASY, MEDIUM, or COMPLEX)",
  "notes": "string (any important observations)"
}}

=== ANALYSIS GUIDELINES ===
1. Identify all fields with their MySQL-specific types (INT AUTO_INCREMENT, ENUM, etc.)
2. Extract constraints (PRIMARY KEY, FOREIGN KEY, NOT NULL, UNIQUE, CHECK)
3. Note any MySQL-specific features (storage engine, character sets)

Return ONLY valid JSON, no explanations or markdown.""",
    "opensearch": """You are an expert OpenSearch/Elasticsearch index schema analyzer.

=== INDEX MAPPING TO ANALYZE ===
{raw_schema}

=== BUSINESS CONTEXT ===
Business Domain: {business_domain}
Description: {business_description}

=== TASK ===
Analyze the index mapping above and extract structured information.

Return a JSON object with the following structure:
{{
  "entity_name": "string (index name)",
  "entity_type": "INDEX",
  "fields": [
    {{
      "name": "string (field name)",
      "type": "string (OpenSearch field type)",
      "properties": ["string (analyzed, keyword, nested, etc.)"],
      "description": "string (inferred purpose)"
    }}
  ],
  "nested_objects": [
    {{
      "path": "string (nested object path)",
      "fields": ["string (nested field names)"]
    }}
  ],
  "complexity": "string (EASY, MEDIUM, or COMPLEX)",
  "notes": "string (any important observations)"
}}

=== ANALYSIS GUIDELINES ===
1. Identify all fields with OpenSearch types (text, keyword, date, nested, object, etc.)
2. Extract field properties (analyzer, format, index settings)
3. Identify nested objects and their structures
4. Note any OpenSearch-specific features (analyzers, mappings)

Return ONLY valid JSON, no explanations or markdown.""",
    "default": """You are an expert database schema analyzer.

=== SCHEMA TO ANALYZE ===
{raw_schema}

=== BUSINESS CONTEXT ===
Business Domain: {business_domain}
Description: {business_description}
Database Dialect: {dialect}

=== TASK ===
Analyze the schema above and extract structured information.

Return a JSON object with the following structure:
{{
  "entity_name": "string (table/collection/index name)",
  "entity_type": "string (TABLE, VIEW, INDEX, COLLECTION, etc.)",
  "fields": [
    {{
      "name": "string (field name)",
      "type": "string (data type)",
      "constraints": ["string (constraints if applicable)"],
      "description": "string (inferred purpose)"
    }}
  ],
  "relationships": [...],
  "complexity": "string (EASY, MEDIUM, or COMPLEX)",
  "notes": "string (any important observations)"
}}

Return ONLY valid JSON, no explanations or markdown.""",
}

# ============================================================================
# FIELD INFERENCE PROMPTS
# ============================================================================

FIELD_INFERENCE_PROMPTS: Dict[str, str] = {
    "postgres": """You are an expert at understanding PostgreSQL database field semantics.

=== FIELD TO ANALYZE ===
Field Name: {field_name}
Data Type: {field_type}
Constraints: {field_constraints}

=== TABLE CONTEXT ===
Table Name: {table_name}
Business Domain: {business_domain}

=== TASK ===
Infer the business meaning and usage patterns of this field.

Return a JSON object:
{{
  "field_name": "string",
  "business_meaning": "string (what this field represents in business terms)",
  "semantic_type": "string (identifier, amount, timestamp, status, etc.)",
  "likely_values": "string (description of expected values or examples)",
  "usage_patterns": "string (how this field is typically used in queries)",
  "relationships": "string (how it relates to other fields/tables)",
  "query_relevance": "string (HIGH, MEDIUM, LOW - likelihood of appearing in user queries)"
}}

Return ONLY valid JSON, no explanations or markdown.""",
    "mysql": """You are an expert at understanding MySQL database field semantics.

=== FIELD TO ANALYZE ===
Field Name: {field_name}
Data Type: {field_type}
Constraints: {field_constraints}

=== TABLE CONTEXT ===
Table Name: {table_name}
Business Domain: {business_domain}

=== TASK ===
Infer the business meaning and usage patterns of this field.

Return a JSON object:
{{
  "field_name": "string",
  "business_meaning": "string (what this field represents in business terms)",
  "semantic_type": "string (identifier, amount, timestamp, status, etc.)",
  "likely_values": "string (description of expected values or examples)",
  "usage_patterns": "string (how this field is typically used in queries)",
  "query_relevance": "string (HIGH, MEDIUM, LOW)"
}}

Return ONLY valid JSON, no explanations or markdown.""",
    "opensearch": """You are an expert at understanding OpenSearch/Elasticsearch field semantics.

=== FIELD TO ANALYZE ===
Field Name: {field_name}
Field Type: {field_type}
Properties: {field_properties}

=== INDEX CONTEXT ===
Index Name: {index_name}
Business Domain: {business_domain}

=== TASK ===
Infer the business meaning and search patterns of this field.

Return a JSON object:
{{
  "field_name": "string",
  "business_meaning": "string (what this field represents in business terms)",
  "semantic_type": "string (full_text, identifier, timestamp, category, etc.)",
  "likely_values": "string (description of expected values or examples)",
  "search_patterns": "string (how this field is typically used in searches)",
  "indexing_notes": "string (analyzer, keyword vs text, etc.)",
  "query_relevance": "string (HIGH, MEDIUM, LOW)"
}}

Return ONLY valid JSON, no explanations or markdown.""",
    "default": """You are an expert at understanding database field semantics.

=== FIELD TO ANALYZE ===
Field Name: {field_name}
Data Type: {field_type}
Constraints: {field_constraints}

=== ENTITY CONTEXT ===
Entity Name: {entity_name}
Business Domain: {business_domain}
Database Dialect: {dialect}

=== TASK ===
Infer the business meaning and usage patterns of this field.

Return a JSON object:
{{
  "field_name": "string",
  "business_meaning": "string (what this field represents in business terms)",
  "semantic_type": "string (identifier, amount, timestamp, status, etc.)",
  "likely_values": "string (description of expected values or examples)",
  "usage_patterns": "string (how this field is typically used)",
  "query_relevance": "string (HIGH, MEDIUM, LOW)"
}}

Return ONLY valid JSON, no explanations or markdown.""",
}

# ============================================================================
# Q&A GENERATION PROMPTS
# ============================================================================

QA_GENERATION_PROMPTS: Dict[str, str] = {
    "postgres": """You are an expert PostgreSQL query writer creating training examples.

=== SCHEMA CONTEXT ===
{schema_context}

=== FIELD METADATA ===
{field_metadata}

=== BUSINESS DOCUMENTATION ===
{business_documentation}

=== TASK ===
Generate realistic question-SQL training pairs that users would ask about this data.

Return a JSON array:
[
  {{
    "question": "string (natural language question)",
    "sql": "string (PostgreSQL query)",
    "complexity": "string (EASY, MEDIUM, HARD)",
    "explanation": "string (why this query answers the question)"
  }}
]

=== GENERATION GUIDELINES ===
1. Create diverse questions: filtering, aggregation, joins, sorting, grouping
2. Use PostgreSQL-specific features where appropriate (JSONB, arrays, CTEs, window functions)
3. Include easy questions (single table SELECT) and complex ones (multi-join aggregations)
4. Generate 5-10 examples covering different query patterns
5. Ensure SQL is syntactically correct and executable

Return ONLY valid JSON array, no explanations or markdown.""",
    "mysql": """You are an expert MySQL query writer creating training examples.

=== SCHEMA CONTEXT ===
{schema_context}

=== FIELD METADATA ===
{field_metadata}

=== BUSINESS DOCUMENTATION ===
{business_documentation}

=== TASK ===
Generate realistic question-SQL training pairs.

Return a JSON array:
[
  {{
    "question": "string (natural language question)",
    "sql": "string (MySQL query)",
    "complexity": "string (EASY, MEDIUM, HARD)",
    "explanation": "string (why this query answers the question)"
  }}
]

=== GENERATION GUIDELINES ===
1. Create diverse questions: filtering, aggregation, joins, sorting, grouping
2. Use MySQL-specific syntax where appropriate (LIMIT, DATE functions)
3. Generate 5-10 examples covering different query patterns

Return ONLY valid JSON array, no explanations or markdown.""",
    "opensearch": """You are an expert OpenSearch DSL query writer creating training examples.

=== INDEX MAPPING ===
{schema_context}

=== FIELD METADATA ===
{field_metadata}

=== BUSINESS DOCUMENTATION ===
{business_documentation}

=== TASK ===
Generate realistic question-DSL training pairs.

Return a JSON array:
[
  {{
    "question": "string (natural language question)",
    "dsl": "object (OpenSearch DSL query)",
    "complexity": "string (EASY, MEDIUM, HARD)",
    "explanation": "string (why this query answers the question)"
  }}
]

=== GENERATION GUIDELINES ===
1. Create diverse queries: match, term, range, bool, aggregations
2. Use OpenSearch features: full-text search, filters, aggregations
3. Generate 5-10 examples covering different query patterns

Return ONLY valid JSON array, no explanations or markdown.""",
    "default": """You are an expert query writer creating training examples.

=== SCHEMA CONTEXT ===
{schema_context}

=== FIELD METADATA ===
{field_metadata}

=== BUSINESS DOCUMENTATION ===
{business_documentation}

=== DATABASE DIALECT ===
{dialect}

=== TASK ===
Generate realistic question-query training pairs.

Return a JSON array:
[
  {{
    "question": "string (natural language question)",
    "query": "string (query in appropriate syntax)",
    "complexity": "string (EASY, MEDIUM, HARD)",
    "explanation": "string (why this query answers the question)"
  }}
]

Return ONLY valid JSON array, no explanations or markdown.""",
}

# ============================================================================
# QUERY GENERATION PROMPTS
# ============================================================================

QUERY_GENERATION_PROMPTS: Dict[str, str] = {
    "postgres": """You are an expert PostgreSQL query generator.

=== DATABASE SCHEMA ===
{ddl_section}

=== DOCUMENTATION ===
{documentation_section}

=== SIMILAR EXAMPLES ===
{examples_section}

=== USER QUESTION ===
{question}

=== TASK ===
Generate a PostgreSQL query that answers the user's question.

=== GUIDELINES ===
1. Use the schema to understand available tables and fields
2. Reference the documentation for business context
3. Learn from similar examples to match query patterns
4. Use PostgreSQL-specific features when appropriate (JSONB, CTEs, window functions)
5. Ensure the query is syntactically correct and executable
6. Use proper JOIN syntax, not implicit joins
7. Add helpful aliases for readability

Return ONLY the SQL query wrapped in ```sql blocks, no explanations outside the block.

Example:
```sql
SELECT
    c.customer_name,
    SUM(o.total_amount) as total_revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.order_date >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY c.customer_id, c.customer_name
ORDER BY total_revenue DESC
LIMIT 5;
```""",
    "mysql": """You are an expert MySQL query generator.

=== DATABASE SCHEMA ===
{ddl_section}

=== DOCUMENTATION ===
{documentation_section}

=== SIMILAR EXAMPLES ===
{examples_section}

=== USER QUESTION ===
{question}

=== TASK ===
Generate a MySQL query that answers the user's question.

=== GUIDELINES ===
1. Use the schema to understand available tables and fields
2. Reference the documentation for business context
3. Use MySQL-specific syntax (LIMIT, DATE functions)
4. Use proper JOIN syntax, not implicit joins

Return ONLY the SQL query wrapped in ```sql blocks.""",
    "opensearch": """You are an expert OpenSearch DSL query generator.

=== INDEX MAPPING ===
{ddl_section}

=== DOCUMENTATION ===
{documentation_section}

=== SIMILAR EXAMPLES ===
{examples_section}

=== USER QUESTION ===
{question}

=== TASK ===
Generate an OpenSearch DSL query that answers the user's question.

=== GUIDELINES ===
1. Use the mapping to understand available fields and types
2. Choose appropriate query types: match (full-text), term (exact), range, bool
3. Use aggregations for analytics questions
4. Handle nested objects properly
5. Use keyword fields for exact matches, text fields for search

Return ONLY the DSL query wrapped in ```json blocks.

Example:
```json
{{
  "query": {{
    "bool": {{
      "must": [
        {{"match": {{"product_name": "laptop"}}}}
      ],
      "filter": [
        {{"range": {{"price": {{"gte": 500, "lte": 2000}}}}}}
      ]
    }}
  }},
  "aggs": {{
    "by_brand": {{
      "terms": {{"field": "brand.keyword"}}
    }}
  }},
  "size": 10
}}
```""",
    "rest_api": """You are an expert REST API request generator.

=== AVAILABLE ENDPOINTS ===
{endpoints_section}

=== DOCUMENTATION ===
{documentation_section}

=== SIMILAR EXAMPLES ===
{examples_section}

=== USER QUESTION ===
{question}

=== TASK ===
Generate a REST API request that answers the user's question.

=== OUTPUT FORMAT ===
Return a JSON object representing the API request:
{{
    "method": "GET|POST|PUT|PATCH|DELETE",
    "path": "/api/endpoint/path",
    "params": {{"query_param1": "value1"}},
    "headers": {{"Custom-Header": "value"}},
    "body": {{"field1": "value1"}}
}}

=== GUIDELINES ===
1. Choose the endpoint that best matches the user's intent
2. Use CANONICAL values for enum parameters, not synonyms
3. Include only necessary parameters
4. For GET requests, use "params" for query parameters
5. For POST/PUT/PATCH requests, use "body" for request body

=== VALUE MAPPINGS ===
{value_mappings}

Return ONLY valid JSON wrapped in ```json blocks.""",
    "default": """You are an expert query generator.

=== SCHEMA ===
{ddl_section}

=== DOCUMENTATION ===
{documentation_section}

=== SIMILAR EXAMPLES ===
{examples_section}

=== USER QUESTION ===
{question}

=== DATABASE DIALECT ===
{dialect}

=== TASK ===
Generate a query that answers the user's question using the specified dialect.

Return ONLY the query wrapped in appropriate code blocks.""",
}

# ============================================================================
# PLANNING PROMPTS
# ============================================================================

PLAN_ANALYSIS_PROMPT = """You are an expert query planner. Analyze the following user question and schema context.

## User Question
{question}

## Available Schema Fields
{schema_fields}

## Example Q&A Pairs
{examples}

## Your Task
1. Identify any ambiguities in the question that need clarification
2. For each ambiguity, suggest clarification questions with options
3. Determine if this requires single or multi-step query execution
4. Suggest the query approach and steps

## Response Format (JSON only)
{{
    "summary": "Brief analysis summary",
    "ambiguities": ["List of identified ambiguities as strings"],
    "clarification_needs": [
        {{
            "question": "Clarifying question text",
            "category": "time|scope|filter|aggregation|metric|entity|general",
            "options": [
                {{"value": "option_key", "label": "Display Label", "description": "Why this option"}}
            ],
            "allows_custom": true,
            "required": true
        }}
    ],
    "approach": "Recommended query strategy description",
    "requires_multi_step": false,
    "suggested_steps": [
        {{
            "description": "Step description",
            "question": "Natural language question for this step",
            "depends_on": [],
            "context_from_previous": {{}}
        }}
    ]
}}

Respond with ONLY valid JSON, no explanations or markdown."""


STEP_REGENERATION_PROMPT = """You are an expert query planner. The user has answered clarification questions.
Regenerate the query plan steps based on their answers.

## Original Question
{original_question}

## User Answers
{user_answers}

## Available Schema Fields
{schema_fields}

## Task
Generate updated query steps that incorporate the user's clarifications.

## Response Format (JSON only)
{{
    "steps": [
        {{
            "description": "Step description",
            "question": "Natural language question for this step incorporating clarifications",
            "depends_on": ["list of step_ids this depends on"],
            "context_from_previous": {{"placeholder_name": "source_step_id"}}
        }}
    ]
}}

Respond with ONLY valid JSON, no explanations or markdown."""


# ============================================================================
# PROMPT CONFIGS (Model & Temperature settings per operation)
# ============================================================================

PROMPT_CONFIGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "schema_analysis": {
        "postgres": {
            "model": "gemini-2.5-flash",
            "temperature": 0.3,
            "operation": "schema_analysis",
            "extraction": {"type": "json", "format": "structured"},
        },
        "mysql": {
            "model": "gemini-2.5-flash",
            "temperature": 0.3,
            "operation": "schema_analysis",
            "extraction": {"type": "json", "format": "structured"},
        },
        "opensearch": {
            "model": "gemini-2.5-flash",
            "temperature": 0.3,
            "operation": "schema_analysis",
            "extraction": {"type": "json", "format": "structured"},
        },
        "default": {
            "model": "gemini-2.5-flash",
            "temperature": 0.3,
            "operation": "schema_analysis",
            "extraction": {"type": "json", "format": "structured"},
        },
    },
    "field_inference": {
        "postgres": {
            "model": "gemini-2.5-flash",
            "temperature": 0.5,
            "operation": "field_inference",
            "extraction": {"type": "json", "format": "structured"},
        },
        "default": {
            "model": "gemini-2.5-flash",
            "temperature": 0.5,
            "operation": "field_inference",
            "extraction": {"type": "json", "format": "structured"},
        },
    },
    "qa_generation": {
        "postgres": {
            "model": "gemini-2.5-flash",
            "temperature": 0.7,
            "operation": "qa_generation",
            "extraction": {"type": "json", "format": "array"},
        },
        "default": {
            "model": "gemini-2.5-flash",
            "temperature": 0.7,
            "operation": "qa_generation",
            "extraction": {"type": "json", "format": "array"},
        },
    },
    "query_generation": {
        "postgres": {
            "model": "gemini-2.5-flash",
            "temperature": 0.7,
            "query_type": "postgres",
            "extraction": {
                "type": "hybrid",
                "patterns": {"code_block": r"```sql\n(.+?)\n```", "select": r"\bSELECT\b.*?;"},
            },
        },
        "opensearch": {
            "model": "gemini-2.5-flash",
            "temperature": 0.7,
            "query_type": "opensearch",
            "extraction": {
                "type": "hybrid",
                "patterns": {"code_block": r"```json\n(.+?)\n```", "json": r"\{.*?\}"},
            },
        },
        "rest_api": {
            "model": "gemini-2.5-flash",
            "temperature": 0.5,
            "query_type": "rest_api",
            "extraction": {
                "type": "json",
                "patterns": {"code_block": r"```json\n(.+?)\n```", "json": r"\{[\s\S]*?\}"},
            },
        },
        "default": {
            "model": "gemini-2.5-flash",
            "temperature": 0.7,
            "query_type": "sql",
            "extraction": {
                "type": "hybrid",
                "patterns": {"code_block": r"```sql\n(.+?)\n```", "select": r"\bSELECT\b.*?;"},
            },
        },
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_schema_analysis_prompt(dialect: str = "default") -> str:
    """Get schema analysis prompt template for specified dialect."""
    return SCHEMA_ANALYSIS_PROMPTS.get(dialect, SCHEMA_ANALYSIS_PROMPTS["default"])


def get_field_inference_prompt(dialect: str = "default") -> str:
    """Get field inference prompt template for specified dialect."""
    return FIELD_INFERENCE_PROMPTS.get(dialect, FIELD_INFERENCE_PROMPTS["default"])


def get_qa_generation_prompt(dialect: str = "default") -> str:
    """Get Q&A generation prompt template for specified dialect."""
    return QA_GENERATION_PROMPTS.get(dialect, QA_GENERATION_PROMPTS["default"])


def get_query_generation_prompt(dialect: str = "default") -> str:
    """Get query generation prompt template for specified dialect."""
    return QUERY_GENERATION_PROMPTS.get(dialect, QUERY_GENERATION_PROMPTS["default"])


def get_plan_analysis_prompt() -> str:
    """Get the plan analysis prompt template."""
    return PLAN_ANALYSIS_PROMPT


def get_step_regeneration_prompt() -> str:
    """Get the step regeneration prompt template."""
    return STEP_REGENERATION_PROMPT


def get_all_prompts_for_dialect(dialect: str = "default") -> Dict[str, str]:
    """Get all 4 prompt templates for a specific dialect."""
    return {
        "schema_analysis": get_schema_analysis_prompt(dialect),
        "field_inference": get_field_inference_prompt(dialect),
        "qa_generation": get_qa_generation_prompt(dialect),
        "query_generation": get_query_generation_prompt(dialect),
    }


def get_prompt_config(operation: str, dialect: str = "default") -> Dict[str, Any]:
    """Get configuration for a specific operation and dialect."""
    operation_configs = PROMPT_CONFIGS.get(operation, {})
    return operation_configs.get(dialect, operation_configs.get("default", {}))


# ============================================================================
# REST API FORMATTING HELPERS
# ============================================================================


def format_endpoint_for_prompt(endpoint: "EndpointSpec") -> str:
    """
    Format an EndpointSpec for inclusion in prompts.

    Args:
        endpoint: EndpointSpec object

    Returns:
        Formatted string describing the endpoint
    """
    lines = [f"\n{endpoint.method} {endpoint.path}"]

    if endpoint.summary:
        lines.append(f"  Summary: {endpoint.summary}")

    if endpoint.description:
        lines.append(f"  Description: {endpoint.description[:200]}")

    if endpoint.maps_to:
        lines.append(f"  Concept: {endpoint.maps_to}")

    if endpoint.parameters:
        lines.append("  Parameters:")
        for param in endpoint.parameters:
            required_str = " (required)" if param.required else ""
            lines.append(f"    - {param.name} ({param.location}, {param.param_type}{required_str})")
            if param.description:
                lines.append(f"      Description: {param.description}")
            if param.allowed_values:
                lines.append(f"      Allowed values: {', '.join(param.allowed_values[:5])}")
            if param.value_synonyms:
                syn_strs = [f"{k}={', '.join(v[:3])}" for k, v in list(param.value_synonyms.items())[:3]]
                lines.append(f"      Value synonyms: {'; '.join(syn_strs)}")

    return "\n".join(lines)


def format_value_mappings_for_prompt(endpoints: List["EndpointSpec"]) -> str:
    """
    Extract all value_synonyms from endpoints for LLM reference.

    Args:
        endpoints: List of EndpointSpec objects

    Returns:
        Formatted string with all value mappings
    """
    mappings = []
    seen: set = set()

    for endpoint in endpoints:
        for param in endpoint.parameters:
            if param.value_synonyms:
                for canonical, synonyms in param.value_synonyms.items():
                    key = (param.name, canonical)
                    if key not in seen:
                        seen.add(key)
                        syn_str = ", ".join(synonyms[:5])
                        mappings.append(f'- {param.name}: "{syn_str}" -> "{canonical}"')

    return "\n".join(mappings) if mappings else "(no value mappings defined)"


def format_hierarchical_fields(context: "RetrievalContext", group_by_concept: bool = True) -> str:
    """
    Format fields hierarchically for enhanced prompts.

    Groups fields by concept and includes scores, value encodings.

    Args:
        context: RetrievalContext with fields and scores
        group_by_concept: Whether to group by concept (True) or flat list (False)

    Returns:
        Formatted string for prompt inclusion
    """
    if not context.all_fields:
        return "No relevant fields found."

    lines = []

    if group_by_concept and hasattr(context, "expansion_stats"):
        concept_groups = context.expansion_stats.get("concept_groups", {})

        if concept_groups:
            for concept, field_names in concept_groups.items():
                lines.append(f"\n## Concept: {concept}")
                for fname in field_names:
                    field = next(
                        (f for f in context.all_fields if (f.qualified_name or f.name) == fname),
                        None,
                    )
                    if field:
                        lines.append(_format_single_field(field, context.field_scores))
        else:
            for field in context.all_fields:
                lines.append(_format_single_field(field, context.field_scores))
    else:
        sorted_fields = sorted(
            context.all_fields,
            key=lambda f: context.field_scores.get(f.qualified_name or f.name, 0.0),
            reverse=True,
        )
        for field in sorted_fields:
            lines.append(_format_single_field(field, context.field_scores))

    return "\n".join(lines)


def _format_single_field(field: Any, scores: Dict[str, float]) -> str:
    """Format a single field with all metadata."""
    fname = field.qualified_name or field.name
    score = scores.get(fname, 0.0)

    parts = [f"- **{fname}** ({field.type}) [relevance: {score:.2f}]"]

    if field.description:
        parts.append(f"  Description: {field.description}")

    if field.business_meaning:
        parts.append(f"  Business meaning: {field.business_meaning}")

    if field.allowed_values:
        vals = ", ".join(field.allowed_values[:6])
        if len(field.allowed_values) > 6:
            vals += f" (+{len(field.allowed_values) - 6} more)"
        parts.append(f"  Allowed values: {vals}")

    if field.value_encoding:
        encodings = [f"{k}={v}" for k, v in list(field.value_encoding.items())[:5]]
        if len(field.value_encoding) > 5:
            encodings.append(f"(+{len(field.value_encoding) - 5} more)")
        parts.append(f"  Value meanings: {', '.join(encodings)}")

    if field.search_guidance:
        parts.append(f"  Usage hint: {field.search_guidance}")

    return "\n".join(parts)


def format_value_encoding_reference(context: "RetrievalContext") -> str:
    """
    Extract all value encodings for LLM reference.

    Creates a quick reference for the LLM to map natural language to coded values.
    """
    encodings = []
    seen: set = set()

    for field in context.all_fields:
        if field.value_encoding:
            for canonical, meaning in field.value_encoding.items():
                key = (field.name, canonical)
                if key not in seen:
                    seen.add(key)
                    encodings.append(f'- {field.name}: "{meaning}" -> "{canonical}"')

    return "\n".join(encodings) if encodings else "(no coded values - use values as-is)"
