import { z } from 'zod'

// ==================== Knowledge Types ====================

export const KnowledgeType = {
  FAQ: 'faq',
  PERMISSION: 'permission',
  SCHEMA: 'schema',
  EXAMPLE: 'example',
  PLAYBOOK: 'playbook',
} as const

export type KnowledgeType = (typeof KnowledgeType)[keyof typeof KnowledgeType]

export const KnowledgeStatus = {
  DRAFT: 'draft',
  PUBLISHED: 'published',
  ARCHIVED: 'archived',
} as const

export type KnowledgeStatus = (typeof KnowledgeStatus)[keyof typeof KnowledgeStatus]

export const Visibility = {
  PUBLIC: 'public',
  INTERNAL: 'internal',
  RESTRICTED: 'restricted',
} as const

export type Visibility = (typeof Visibility)[keyof typeof Visibility]

export const ExampleFormat = {
  TEXT: 'text',
  JSON: 'json',
} as const

export type ExampleFormat = (typeof ExampleFormat)[keyof typeof ExampleFormat]

// ==================== Content Types ====================

export interface FAQContent {
  answer: string // Markdown supported
}

export interface PermissionContent {
  description: string
  permissions: string[]
  roles: string[]
  context?: string
}

export interface SchemaContent {
  name: string
  definition: string // YAML string (YAMLSchemaV1 format)
}

export interface ExampleContent {
  schema_id: number
  description: string
  content: string // JSON or text based on format
  format: ExampleFormat
}

export interface PlaybookContent {
  domain: string
  content: string // Markdown supported
}

export type KnowledgeContent =
  | FAQContent
  | PermissionContent
  | SchemaContent
  | ExampleContent
  | PlaybookContent

// ==================== Base Knowledge Item ====================

export interface BaseKnowledgeItem {
  id: number
  knowledge_type: KnowledgeType
  title: string
  tags: string[]
  status: KnowledgeStatus
  visibility: Visibility
  created_by?: string
  created_at: string
  updated_by?: string
  updated_at?: string
}

// ==================== Type-Specific Items ====================

export interface FAQItem extends BaseKnowledgeItem {
  knowledge_type: typeof KnowledgeType.FAQ
  content: FAQContent
}

export interface PermissionItem extends BaseKnowledgeItem {
  knowledge_type: typeof KnowledgeType.PERMISSION
  content: PermissionContent
}

export interface SchemaItem extends BaseKnowledgeItem {
  knowledge_type: typeof KnowledgeType.SCHEMA
  content: SchemaContent
}

export interface ExampleItem extends BaseKnowledgeItem {
  knowledge_type: typeof KnowledgeType.EXAMPLE
  content: ExampleContent
  // Populated field
  schema?: SchemaItem
}

export interface PlaybookItem extends BaseKnowledgeItem {
  knowledge_type: typeof KnowledgeType.PLAYBOOK
  content: PlaybookContent
}

export type KnowledgeItem =
  | FAQItem
  | PermissionItem
  | SchemaItem
  | ExampleItem
  | PlaybookItem

// ==================== Domain Management ====================

export interface Domain {
  id: string
  name: string
  description?: string
  isCustom: boolean // User-added vs predefined
}

export const DEFAULT_DOMAINS: Domain[] = [
  { id: 'purchasing', name: 'Purchasing', description: 'Purchase orders and procurement', isCustom: false },
  { id: 'sales', name: 'Sales', description: 'Sales orders and customer management', isCustom: false },
  { id: 'inventory', name: 'Inventory', description: 'Stock and warehouse management', isCustom: false },
  { id: 'finance', name: 'Finance', description: 'Financial operations and reporting', isCustom: false },
  { id: 'hr', name: 'Human Resources', description: 'Employee and HR management', isCustom: false },
  { id: 'analytics', name: 'Analytics', description: 'Data analytics and reporting', isCustom: false },
]

// ==================== Zod Schemas for Forms ====================

export const faqFormSchema = z.object({
  title: z.string().min(10, 'Question must be at least 10 characters'),
  answer: z.string().min(20, 'Answer must be at least 20 characters'),
  tags: z.array(z.string()),
  status: z.enum(['draft', 'published', 'archived']),
  visibility: z.enum(['public', 'internal', 'restricted']),
})

export type FAQFormData = z.infer<typeof faqFormSchema>

export const permissionFormSchema = z.object({
  title: z.string().min(3, 'Feature name must be at least 3 characters'),
  description: z.string().min(10, 'Description must be at least 10 characters'),
  permissions: z.array(z.string()).min(1, 'At least one permission is required'),
  roles: z.array(z.string()).min(1, 'At least one role is required'),
  context: z.string().optional(),
  tags: z.array(z.string()),
  status: z.enum(['draft', 'published', 'archived']),
  visibility: z.enum(['public', 'internal', 'restricted']),
})

export type PermissionFormData = z.infer<typeof permissionFormSchema>

export const schemaFormSchema = z.object({
  title: z.string().min(3, 'Title must be at least 3 characters'),
  name: z.string().min(1, 'Schema name is required').regex(/^[a-z0-9_-]+$/, 'Name must be lowercase alphanumeric with dashes/underscores'),
  definition: z.string().min(10, 'Schema definition is required'),
  tags: z.array(z.string()),
  status: z.enum(['draft', 'published', 'archived']),
  visibility: z.enum(['public', 'internal', 'restricted']),
})

export type SchemaFormData = z.infer<typeof schemaFormSchema>

export const exampleFormSchema = z.object({
  title: z.string().min(3, 'Title must be at least 3 characters'),
  schema_id: z.number().min(1, 'Schema is required'),
  description: z.string().min(10, 'Description must be at least 10 characters'),
  content: z.string().min(1, 'Content is required'),
  format: z.enum(['text', 'json']),
  tags: z.array(z.string()),
  status: z.enum(['draft', 'published', 'archived']),
  visibility: z.enum(['public', 'internal', 'restricted']),
})

export type ExampleFormData = z.infer<typeof exampleFormSchema>

export const playbookFormSchema = z.object({
  title: z.string().min(3, 'Title must be at least 3 characters'),
  domain: z.string().min(1, 'Domain is required'),
  content: z.string().min(20, 'Content must be at least 20 characters'),
  tags: z.array(z.string()),
  status: z.enum(['draft', 'published', 'archived']),
  visibility: z.enum(['public', 'internal', 'restricted']),
})

export type PlaybookFormData = z.infer<typeof playbookFormSchema>

// ==================== API Types ====================

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  limit: number
  total_pages: number
}

export interface KnowledgeFilters {
  search?: string
  knowledge_type?: KnowledgeType[]
  tags?: string[]
  status?: KnowledgeStatus[]
  visibility?: Visibility
  domain?: string // For playbooks
  schema_id?: number // For examples
}

// ==================== Metrics Types ====================

export interface TypeStats {
  type: KnowledgeType
  total: number
  published: number
  draft: number
  archived: number
}

export interface KnowledgeMetrics {
  total_items: number
  by_type: TypeStats[]
  by_status: Record<KnowledgeStatus, number>
  recent_activity: {
    date: string
    created: number
    updated: number
  }[]
}

export interface KnowledgeHitStats {
  id: number
  knowledge_type: KnowledgeType
  title: string
  tags: string[]
  total_hits: number
  unique_sessions: number
  days_with_hits: number
  last_hit_at: string
  avg_similarity: number
  primary_retrieval_method: string
}

export interface DailyHitStats {
  date: string
  total_hits: number
  unique_sessions: number
  by_type: Record<KnowledgeType, number>
}

// ==================== Legacy Types (for backward compatibility) ====================

export interface LegacyKnowledgeItem {
  id: number
  knowledge_type: string
  category_id?: number
  category?: KnowledgeCategory
  title: string
  summary?: string
  content: Record<string, unknown>
  tags: string[]
  visibility: string
  status: string
  owner_id?: string
  team_id?: string
  created_by?: string
  created_at: string
  updated_at?: string
  variants_count?: number
  relationships_count?: number
  hits_count?: number
}

export interface KnowledgeCategory {
  id: number
  name: string
  slug: string
  description?: string
  parent_id?: number
  default_visibility: string
  sort_order: number
}

export interface KnowledgeVariant {
  id: number
  knowledge_item_id: number
  variant_text: string
  source: string
  source_reference?: string
  created_by?: string
  created_at: string
}

export interface KnowledgeRelationship {
  id: number
  source_id: number
  target_id: number
  relationship_type: string
  weight: number
  is_bidirectional: boolean
  is_auto_generated: boolean
  created_by?: string
  created_at: string
}

export interface StagingKnowledgeItem {
  id: number
  node_type: string
  tenant_id: string
  title: string
  content: Record<string, unknown>
  tags: string[]
  status: 'pending' | 'approved' | 'rejected'
  action: 'new' | 'merge' | 'add_variant'
  merge_with_id?: number
  similarity?: number
  source?: string
  source_reference?: string
  confidence?: number
  created_at: string
  created_by?: string
  reviewed_by?: string
  reviewed_at?: string
  review_notes?: string
}
