import { z } from 'zod'
import yaml from 'js-yaml'

/**
 * Zod schema that mirrors the YAMLSchemaV1 Pydantic model from agentic_search.
 * Used for client-side validation of schema definitions in the Monaco editor.
 */

// ==================== Enums ====================

export const QueryMode = z.enum(['PPL', 'DSL', 'SQL'])
export type QueryMode = z.infer<typeof QueryMode>

export const SchemaType = z.enum([
  'opensearch',
  'rest_api',
  'postgres',
  'mongodb',
  'graphql',
  'mixed',
])
export type SchemaType = z.infer<typeof SchemaType>

export const RelationshipType = z.enum([
  'HAS_ONE',
  'HAS_MANY',
  'BELONGS_TO',
  'MANY_TO_MANY',
  'CONTAINS',
  'REFERENCES',
])
export type RelationshipType = z.infer<typeof RelationshipType>

export const ParameterLocation = z.enum(['path', 'query', 'header', 'body'])
export type ParameterLocation = z.infer<typeof ParameterLocation>

export const HTTPMethod = z.enum(['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
export type HTTPMethod = z.infer<typeof HTTPMethod>

// ==================== Field Spec ====================

export const FieldSpecSchema: z.ZodType<unknown> = z.lazy(() =>
  z.object({
    // Required fields
    path: z.string().min(1, 'Field path is required'),
    es_type: z.string().min(1, 'ES type is required'),

    // Optional semantic info
    description: z.string().optional(),
    maps_to: z.string().optional(),
    business_meaning: z.string().optional(),

    // Value constraints
    allowed_values: z.array(z.string()).optional(),
    value_examples: z.array(z.string()).optional(),
    value_encoding: z.record(z.string(), z.string()).optional(),
    value_patterns: z.string().optional(),
    value_synonyms: z.record(z.string(), z.array(z.string())).optional(),

    // Search optimization
    search_guidance: z.string().optional(),
    common_filters: z.array(z.string()).optional(),
    aggregation_hints: z.string().optional(),

    // Relationships
    related_fields: z.array(z.string()).optional(),

    // Annotations
    aliases: z.array(z.string()).optional(),
    pii: z.boolean().optional(),
    searchable: z.boolean().optional(),
    aggregatable: z.boolean().optional(),
    is_required: z.boolean().optional(),
    is_indexed: z.boolean().optional(),

    // Nested fields (recursive)
    nested_fields: z.array(z.lazy(() => FieldSpecSchema)).optional(),

    // Metadata
    auto_imported: z.boolean().optional(),
    human_edited: z.boolean().optional(),
    last_updated: z.string().optional(),
    modified_by: z.string().optional(),
  })
)

export type FieldSpec = z.infer<typeof FieldSpecSchema>

// ==================== Index Spec ====================

export const IndexSpecSchema = z.object({
  name: z.string().min(1, 'Index name is required'),
  description: z.string().optional(),
  query_mode: QueryMode.optional(),
  fields: z.array(FieldSpecSchema).optional(),
  primary_key: z.string().optional(),
  timestamp_field: z.string().optional(),
  owner: z.string().optional(),
  data_freshness: z.string().optional(),
})

export type IndexSpec = z.infer<typeof IndexSpecSchema>

// ==================== Concept Relationship ====================

export const ConceptRelationshipSchema = z.object({
  target: z.string().min(1, 'Target concept is required'),
  type: RelationshipType,
  via_field: z.string().optional(),
  description: z.string().optional(),
  inverse_name: z.string().optional(),
})

export type ConceptRelationship = z.infer<typeof ConceptRelationshipSchema>

// ==================== Concept Spec ====================

export const ConceptSpecSchema = z.object({
  name: z.string().min(1, 'Concept name is required'),
  description: z.string().optional(),
  aliases: z.array(z.string()).optional(),
  related_to: z.array(z.string()).optional(),
  relationships: z.array(ConceptRelationshipSchema).optional(),
  synonyms: z.array(z.string()).optional(),
  value_synonyms: z.record(z.string(), z.array(z.string())).optional(),
  related_pronouns: z.array(z.string()).optional(),
  auto_suggested: z.boolean().optional(),
  confidence: z.number().min(0).max(1).optional(),
  source_patterns: z.array(z.string()).optional(),
})

export type ConceptSpec = z.infer<typeof ConceptSpecSchema>

// ==================== QA Example Spec ====================

export const QAExampleSpecSchema = z.object({
  question: z.string().min(1, 'Question is required'),
  query: z.string().min(1, 'Query is required'),
  query_type: z.string().optional(),
  explanation: z.string().optional(),
  concepts_used: z.array(z.string()).optional(),
  fields_used: z.array(z.string()).optional(),
  verified: z.boolean().optional(),
  source: z.string().optional(),
})

export type QAExampleSpec = z.infer<typeof QAExampleSpecSchema>

// ==================== Parameter Spec (for REST API) ====================

export const ParameterSpecSchema = z.object({
  name: z.string().min(1, 'Parameter name is required'),
  location: ParameterLocation,
  param_type: z.string().min(1, 'Parameter type is required'),
  description: z.string().optional(),
  maps_to: z.string().optional(),
  business_meaning: z.string().optional(),
  required: z.boolean().optional(),
  allowed_values: z.array(z.string()).optional(),
  value_synonyms: z.record(z.string(), z.array(z.string())).optional(),
})

export type ParameterSpec = z.infer<typeof ParameterSpecSchema>

// ==================== Endpoint Spec (for REST API) ====================

export const EndpointSpecSchema = z.object({
  path: z.string().min(1, 'Endpoint path is required'),
  method: HTTPMethod,
  operation_id: z.string().optional(),
  summary: z.string().optional(),
  description: z.string().optional(),
  maps_to: z.string().optional(),
  tags: z.array(z.string()).optional(),
  parameters: z.array(ParameterSpecSchema).optional(),
})

export type EndpointSpec = z.infer<typeof EndpointSpecSchema>

// ==================== Root Schema: YAMLSchemaV1 ====================

export const YAMLSchemaV1Schema = z.object({
  // Required metadata
  version: z.string().default('1.0'),
  tenant_id: z.string().min(1, 'Tenant ID is required'),

  // Optional metadata
  schema_type: SchemaType.optional(),
  last_synced: z.string().optional(),

  // Shared semantic layer
  concepts: z.array(ConceptSpecSchema).optional(),

  // OpenSearch data source
  indices: z.array(IndexSpecSchema).optional(),

  // REST API data source
  endpoints: z.array(EndpointSpecSchema).optional(),

  // Q&A examples
  examples: z.array(QAExampleSpecSchema).optional(),
})

export type YAMLSchemaV1 = z.infer<typeof YAMLSchemaV1Schema>

// ==================== Validation Utilities ====================

export interface ValidationResult {
  valid: boolean
  data?: YAMLSchemaV1
  errors: ValidationError[]
}

export interface ValidationError {
  path: string
  message: string
  line?: number
}

/**
 * Validates a YAML string against the YAMLSchemaV1 schema.
 * Returns validation result with errors mapped to line numbers where possible.
 */
export function validateYAMLSchema(yamlString: string): ValidationResult {
  // Step 1: Parse YAML
  let parsed: unknown
  try {
    parsed = yaml.load(yamlString)
  } catch (error) {
    const yamlError = error as yaml.YAMLException
    return {
      valid: false,
      errors: [
        {
          path: '',
          message: `YAML syntax error: ${yamlError.message}`,
          line: yamlError.mark?.line ? yamlError.mark.line + 1 : undefined,
        },
      ],
    }
  }

  // Handle empty YAML
  if (parsed === null || parsed === undefined) {
    return {
      valid: false,
      errors: [{ path: '', message: 'YAML document is empty' }],
    }
  }

  // Step 2: Validate against Zod schema
  const result = YAMLSchemaV1Schema.safeParse(parsed)

  if (result.success) {
    return {
      valid: true,
      data: result.data,
      errors: [],
    }
  }

  const errors: ValidationError[] = result.error.issues.map((issue) => ({
    path: issue.path.join('.'),
    message: issue.message,
    line: findLineNumber(yamlString, issue.path as (string | number)[]),
  }))

  return {
    valid: false,
    errors,
  }
}

/**
 * Attempts to find the line number for a given path in YAML.
 * This is a best-effort approach since YAML doesn't preserve line numbers.
 */
function findLineNumber(yamlString: string, path: (string | number)[]): number | undefined {
  if (path.length === 0) return undefined

  const lines = yamlString.split('\n')
  const searchKey = String(path[path.length - 1])

  // Simple heuristic: find the line containing the key
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    // Match key at start of line or after whitespace
    if (line.match(new RegExp(`^\\s*-?\\s*${searchKey}\\s*:`))) {
      return i + 1
    }
  }

  return undefined
}

/**
 * Formats validation errors for display in Monaco editor markers.
 */
export function errorsToMonacoMarkers(
  errors: ValidationError[]
): Array<{
  startLineNumber: number
  endLineNumber: number
  startColumn: number
  endColumn: number
  message: string
  severity: number // 8 = error, 4 = warning
}> {
  return errors.map((error) => ({
    startLineNumber: error.line || 1,
    endLineNumber: error.line || 1,
    startColumn: 1,
    endColumn: 1000,
    message: error.path ? `${error.path}: ${error.message}` : error.message,
    severity: 8, // Error
  }))
}

/**
 * Creates an empty YAMLSchemaV1 template for new schemas.
 */
export function createEmptySchemaTemplate(tenantId: string): string {
  return `# QueryForge Schema - Edit this file to define your data schema
#
# CONCEPTS: Business entities that fields map to
#   - name: concept name (lowercase)
#   - description: what this entity represents
#   - aliases: alternative names users might say
#
# INDICES: OpenSearch indices with field mappings
#   - name: index name or pattern
#   - fields: list of field specifications
#
# EXAMPLES: Q&A pairs for query generation hints

version: "1.0"
tenant_id: ${tenantId}

concepts:
  - name: example_concept
    description: "TODO: Describe this business entity"
    aliases:
      - alias1
      - alias2

indices:
  - name: example-index-*
    description: "TODO: Describe this index"
    query_mode: PPL
    fields:
      - path: id
        es_type: keyword
        description: "Unique identifier"
        maps_to: example_concept
      - path: name
        es_type: text
        description: "Name field"
        maps_to: example_concept

examples:
  - question: "Show all records"
    query: 'source=example-index-* | fields id, name'
    concepts_used:
      - example_concept
    fields_used:
      - id
      - name
    verified: false
`
}
