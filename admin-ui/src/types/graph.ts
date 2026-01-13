import { z } from 'zod'

export const NodeType = {
  FAQ: 'faq',
  PLAYBOOK: 'playbook',
  PERMISSION_RULE: 'permission_rule',
  SCHEMA_INDEX: 'schema_index',
  SCHEMA_FIELD: 'schema_field',
  EXAMPLE: 'example',
  ENTITY: 'entity',
  CONCEPT: 'concept',
} as const

export type NodeType = (typeof NodeType)[keyof typeof NodeType]

export const NodeTypeLabels: Record<NodeType, string> = {
  [NodeType.FAQ]: 'FAQ',
  [NodeType.PLAYBOOK]: 'Playbook',
  [NodeType.PERMISSION_RULE]: 'Permission Rule',
  [NodeType.SCHEMA_INDEX]: 'Schema Index',
  [NodeType.SCHEMA_FIELD]: 'Schema Field',
  [NodeType.EXAMPLE]: 'Example',
  [NodeType.ENTITY]: 'Entity',
  [NodeType.CONCEPT]: 'Concept',
}

export const NodeTypeConfig: Record<NodeType, { icon: string; color: string; bgColor: string }> = {
  [NodeType.FAQ]: { icon: '❓', color: '#2ecc71', bgColor: '#d5f4e6' },
  [NodeType.PLAYBOOK]: { icon: '📖', color: '#e67e22', bgColor: '#fdebd0' },
  [NodeType.PERMISSION_RULE]: { icon: '🔐', color: '#e74c3c', bgColor: '#fadbd8' },
  [NodeType.SCHEMA_INDEX]: { icon: '🗄️', color: '#7f8c8d', bgColor: '#eaecee' },
  [NodeType.SCHEMA_FIELD]: { icon: '📊', color: '#bdc3c7', bgColor: '#f4f6f6' },
  [NodeType.EXAMPLE]: { icon: '📝', color: '#9b59b6', bgColor: '#e8daef' },
  [NodeType.ENTITY]: { icon: '📦', color: '#3498db', bgColor: '#d4e6f1' },
  [NodeType.CONCEPT]: { icon: '💡', color: '#f1c40f', bgColor: '#fef9e7' },
}

export const EdgeType = {
  RELATED: 'related',
  PARENT: 'parent',
  EXAMPLE_OF: 'example_of',
  SHARED_TAG: 'shared_tag',
  SIMILAR: 'similar',
} as const

export type EdgeType = (typeof EdgeType)[keyof typeof EdgeType]

export const EdgeTypeLabels: Record<EdgeType, string> = {
  [EdgeType.RELATED]: 'Related',
  [EdgeType.PARENT]: 'Parent',
  [EdgeType.EXAMPLE_OF]: 'Example Of',
  [EdgeType.SHARED_TAG]: 'Shared Tag',
  [EdgeType.SIMILAR]: 'Similar',
}

export const EdgeTypeConfig: Record<EdgeType, { color: string; strokeDasharray?: string; animated?: boolean }> = {
  [EdgeType.RELATED]: { color: '#3498db' },
  [EdgeType.PARENT]: { color: '#2ecc71', strokeDasharray: '5,5' },
  [EdgeType.EXAMPLE_OF]: { color: '#9b59b6' },
  [EdgeType.SHARED_TAG]: { color: '#f39c12', strokeDasharray: '3,3', animated: true },
  [EdgeType.SIMILAR]: { color: '#e74c3c', strokeDasharray: '2,2', animated: true },
}

export const NodeStatus = {
  DRAFT: 'draft',
  PUBLISHED: 'published',
  ARCHIVED: 'archived',
} as const

export type NodeStatus = (typeof NodeStatus)[keyof typeof NodeStatus]

export const Visibility = {
  PUBLIC: 'public',
  INTERNAL: 'internal',
  RESTRICTED: 'restricted',
} as const

export type Visibility = (typeof Visibility)[keyof typeof Visibility]

export interface FAQContent {
  question: string
  answer: string
  variants?: string[]
}

export interface PlaybookStep {
  order: number
  action: string
  owner?: string
  details?: string
}

export interface PlaybookContent {
  description: string
  steps: PlaybookStep[]
  prerequisites?: string[]
  estimated_time?: string
  related_forms?: string[]
}

export interface PermissionRule {
  role: string
  action: string
  constraint?: Record<string, unknown> | null
}

export interface PermissionRuleContent {
  feature: string
  description: string
  rules: PermissionRule[]
  escalation_path?: string[]
}

export interface EntityAttribute {
  name: string
  type: string
  description: string
}

export interface EntityOperation {
  action: string
  description: string
}

export interface EntityContent {
  entity_name: string
  entity_path: string
  parent_entity?: string
  child_entities?: string[]
  description: string
  business_purpose?: string
  key_attributes?: EntityAttribute[]
  common_operations?: EntityOperation[]
  common_queries?: string[]
}

export interface ForeignKey {
  column: string
  references: string
}

export interface SchemaIndexContent {
  source_type: 'postgres' | 'opensearch' | 'rest_api' | 'clickhouse'
  database?: string
  schema?: string
  table_name?: string
  description: string
  primary_key?: string[]
  foreign_keys?: ForeignKey[]
  query_patterns?: string[]
  row_count_estimate?: number
  update_frequency?: string
}

export interface SchemaFieldContent {
  description: string
  business_meaning?: string
  allowed_values?: string[]
  default_value?: string
  nullable?: boolean
  indexed?: boolean
  search_patterns?: string[]
  business_rules?: string[]
}

export interface ExampleContent {
  question: string
  query: string
  query_type: string
  explanation?: string
  complexity?: 'low' | 'medium' | 'high'
  verified?: boolean
  verified_by?: string
  verified_at?: string
}

export interface ConceptContent {
  description: string
  aliases?: string[]
  scope?: string
  key_questions?: string[]
}

export type NodeContent =
  | FAQContent
  | PlaybookContent
  | PermissionRuleContent
  | EntityContent
  | SchemaIndexContent
  | SchemaFieldContent
  | ExampleContent
  | ConceptContent

export interface KnowledgeNode {
  id: number
  tenant_id: string
  node_type: NodeType
  title: string
  summary?: string
  content: NodeContent
  tags: string[]
  dataset_name?: string
  field_path?: string
  data_type?: string
  visibility: Visibility
  status: NodeStatus
  source?: string
  source_reference?: string
  version?: number
  graph_version?: number
  created_by?: string
  created_at: string
  updated_by?: string
  updated_at?: string
  is_deleted?: boolean
}

export interface KnowledgeEdge {
  id: number
  source_id: number
  target_id: number
  edge_type: EdgeType
  weight: number
  is_auto_generated: boolean
  metadata?: Record<string, unknown>
  created_by?: string
  created_at: string
}

export interface GraphNode extends KnowledgeNode {
  x?: number
  y?: number
}

export interface GraphEdge {
  source: number
  target: number
  edge_type: EdgeType
  weight: number
}

export interface NodeListResponse {
  items: KnowledgeNode[]
  total: number
  page: number
  pages: number
}

export interface NodeDetailResponse {
  node: KnowledgeNode
  edges: KnowledgeEdge[]
}

export interface CreateNodeRequest {
  tenant_id: string
  node_type: NodeType
  title: string
  summary?: string
  content: NodeContent
  tags?: string[]
  dataset_name?: string
  field_path?: string
  data_type?: string
  visibility?: Visibility
  status?: NodeStatus
}

export interface UpdateNodeRequest {
  title?: string
  summary?: string
  content?: Partial<NodeContent>
  tags?: string[]
  visibility?: Visibility
  status?: NodeStatus
}

export interface CreateEdgeRequest {
  source_id: number
  target_id: number
  edge_type: EdgeType
  weight?: number
}

export interface BulkCreateEdgesRequest {
  edges: CreateEdgeRequest[]
}

export interface BulkCreateEdgesResponse {
  created: number
  errors: Array<{ index: number; error: string }>
}

export interface GraphSearchRequest {
  query: string
  tenant_ids: string[]
  node_types?: NodeType[]
  depth?: number
  limit?: number
  include_implicit?: boolean
}

export interface GraphSearchResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  search_matches: number[]
  stats: {
    total_nodes: number
    by_type: Partial<Record<NodeType, number>>
  }
}

export interface GraphExpandResponse {
  center_node: GraphNode
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphStatsResponse {
  total_nodes: number
  by_type: Partial<Record<NodeType, number>>
  total_edges: number
  by_edge_type: Partial<Record<EdgeType, number>>
  orphan_nodes: number
  avg_connections: number
}

export interface GapSuggestion {
  id: number
  type: NodeType
  title: string
  suggestion: string
}

export interface GapAnalysisResponse {
  orphan_nodes: GapSuggestion[]
  weak_clusters: Array<{ nodes: number[]; suggestion: string }>
  missing_examples: Array<{ schema_index: number; suggestion: string }>
  unlinked_entities: GapSuggestion[]
}

export interface ConnectionSuggestion {
  target_id: number
  target_title: string
  target_type: NodeType
  edge_type: EdgeType
  confidence: number
  reason: string
}

export interface AutoSuggestResponse {
  suggestions: ConnectionSuggestion[]
}

export interface Tenant {
  id: string
  name: string
  description?: string
  settings?: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at?: string
}

export interface TenantAccess {
  tenant_id: string
  tenant_name: string
  role: 'viewer' | 'editor' | 'admin'
  node_count?: number
}

export interface TenantListResponse {
  tenants: TenantAccess[]
}

export interface ContextNode {
  id: number
  node_type: NodeType
  title: string
  content: NodeContent
  score: number
  distance?: number
  path?: number[]
  edge_type?: EdgeType
  match_source?: 'bm25' | 'vector' | 'hybrid'
}

export interface EntitySummary {
  id: number
  title: string
  entity_path: string
  related_schemas: string[]
}

export interface ContextRequest {
  query: string
  tenant_ids: string[]
  entry_types?: NodeType[]
  entry_limit?: number
  expand?: boolean
  expansion_types?: NodeType[]
  max_depth?: number
  context_limit?: number
  include_entities?: boolean
  include_schemas?: boolean
  include_examples?: boolean
}

export interface ContextResponse {
  entry_points: ContextNode[]
  context: ContextNode[]
  entities?: EntitySummary[]
  stats: {
    nodes_searched: number
    nodes_expanded: number
    max_depth_reached: number
  }
}

export const faqContentSchema = z.object({
  question: z.string().min(10, 'Question must be at least 10 characters'),
  answer: z.string().min(20, 'Answer must be at least 20 characters'),
  variants: z.array(z.string()).optional(),
})

export const playbookStepSchema = z.object({
  order: z.number().min(1),
  action: z.string().min(1, 'Action is required'),
  owner: z.string().optional(),
  details: z.string().optional(),
})

export const playbookContentSchema = z.object({
  description: z.string().min(10, 'Description must be at least 10 characters'),
  steps: z.array(playbookStepSchema).min(1, 'At least one step is required'),
  prerequisites: z.array(z.string()).optional(),
  estimated_time: z.string().optional(),
  related_forms: z.array(z.string()).optional(),
})

export const permissionRuleSchema = z.object({
  role: z.string().min(1, 'Role is required'),
  action: z.string().min(1, 'Action is required'),
  constraint: z.record(z.string(), z.unknown()).nullable().optional(),
})

export const permissionRuleContentSchema = z.object({
  feature: z.string().min(1, 'Feature is required'),
  description: z.string().min(10, 'Description must be at least 10 characters'),
  rules: z.array(permissionRuleSchema).min(1, 'At least one rule is required'),
  escalation_path: z.array(z.string()).optional(),
})

export const entityAttributeSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  type: z.string().min(1, 'Type is required'),
  description: z.string().min(1, 'Description is required'),
})

export const entityOperationSchema = z.object({
  action: z.string().min(1, 'Action is required'),
  description: z.string().min(1, 'Description is required'),
})

export const entityContentSchema = z.object({
  entity_name: z.string().min(1, 'Entity name is required'),
  entity_path: z.string().min(1, 'Entity path is required'),
  parent_entity: z.string().optional(),
  child_entities: z.array(z.string()).optional(),
  description: z.string().min(10, 'Description must be at least 10 characters'),
  business_purpose: z.string().optional(),
  key_attributes: z.array(entityAttributeSchema).optional(),
  common_operations: z.array(entityOperationSchema).optional(),
  common_queries: z.array(z.string()).optional(),
})

export const schemaIndexContentSchema = z.object({
  source_type: z.enum(['postgres', 'opensearch', 'rest_api', 'clickhouse']),
  database: z.string().optional(),
  schema: z.string().optional(),
  table_name: z.string().optional(),
  description: z.string().min(10, 'Description must be at least 10 characters'),
  primary_key: z.array(z.string()).optional(),
  foreign_keys: z.array(z.object({
    column: z.string(),
    references: z.string(),
  })).optional(),
  query_patterns: z.array(z.string()).optional(),
  row_count_estimate: z.number().optional(),
  update_frequency: z.string().optional(),
})

export const schemaFieldContentSchema = z.object({
  description: z.string().min(5, 'Description must be at least 5 characters'),
  business_meaning: z.string().optional(),
  allowed_values: z.array(z.string()).optional(),
  default_value: z.string().optional(),
  nullable: z.boolean().optional(),
  indexed: z.boolean().optional(),
  search_patterns: z.array(z.string()).optional(),
  business_rules: z.array(z.string()).optional(),
})

export const exampleContentSchema = z.object({
  question: z.string().min(10, 'Question must be at least 10 characters'),
  query: z.string().min(5, 'Query is required'),
  query_type: z.string().min(1, 'Query type is required'),
  explanation: z.string().optional(),
  complexity: z.enum(['low', 'medium', 'high']).optional(),
  verified: z.boolean().optional(),
  verified_by: z.string().optional(),
  verified_at: z.string().optional(),
})

export const conceptContentSchema = z.object({
  description: z.string().min(10, 'Description must be at least 10 characters'),
  aliases: z.array(z.string()).optional(),
  scope: z.string().optional(),
  key_questions: z.array(z.string()).optional(),
})

export const baseNodeFormSchema = z.object({
  title: z.string().min(3, 'Title must be at least 3 characters'),
  summary: z.string().optional(),
  tags: z.array(z.string()),
  visibility: z.enum(['public', 'internal', 'restricted']),
  status: z.enum(['draft', 'published', 'archived']),
})

export const createEdgeFormSchema = z.object({
  source_id: z.number().min(1, 'Source node is required'),
  target_id: z.number().min(1, 'Target node is required'),
  edge_type: z.enum(['related', 'parent', 'example_of', 'shared_tag', 'similar']),
  weight: z.number().min(0).max(1).optional(),
})

export type FAQContentFormData = z.infer<typeof faqContentSchema>
export type PlaybookContentFormData = z.infer<typeof playbookContentSchema>
export type PermissionRuleContentFormData = z.infer<typeof permissionRuleContentSchema>
export type EntityContentFormData = z.infer<typeof entityContentSchema>
export type SchemaIndexContentFormData = z.infer<typeof schemaIndexContentSchema>
export type SchemaFieldContentFormData = z.infer<typeof schemaFieldContentSchema>
export type ExampleContentFormData = z.infer<typeof exampleContentSchema>
export type ConceptContentFormData = z.infer<typeof conceptContentSchema>
export type BaseNodeFormData = z.infer<typeof baseNodeFormSchema>
export type CreateEdgeFormData = z.infer<typeof createEdgeFormSchema>
