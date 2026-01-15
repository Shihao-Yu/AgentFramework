# Knowledge Base Admin UI - Documentation

## Overview

The Context Management UI is a React-based admin panel for managing a multi-type knowledge base system. It provides CRUD interfaces for 5 knowledge types, a staging queue for AI-generated content review, metrics dashboards, and system configuration.

**Tech Stack:**
- React 19 + TypeScript + Vite
- Tailwind CSS v4 (with dark/light theme support)
- Radix UI / shadcn components
- TanStack Table & Query
- Monaco Editor (YAML/JSON), MDEditor (Markdown)
- Zod for validation, react-hook-form

---

## Features Summary

### 1. FAQs (`/`)
Manage question-answer pairs with markdown support.

| Feature | Description |
|---------|-------------|
| Create/Edit/Delete | Full CRUD for FAQ entries |
| Markdown Editor | Rich text answers with preview |
| Status Management | Draft / Published / Archived |
| Visibility Control | Public / Internal / Restricted |
| Tagging | Multiple tags per item |
| Stats Dashboard | Total, Published, Draft counts |

### 2. Feature Permissions (`/permissions`)
Document what permissions users need to access each feature (feature-centric model).

| Feature | Description |
|---------|-------------|
| Feature Documentation | Describe what each feature does |
| Permission Mapping | List required permissions (e.g., `reports.read`) |
| Role Assignment | Which roles have access (e.g., Admin, Auditor) |
| Context Notes | Additional markdown context |
| Autocomplete | Suggests existing permissions/roles |

### 3. Schemas & Examples (`/schemas`)
Manage YAML schema definitions and usage examples.

| Feature | Description |
|---------|-------------|
| Monaco Editor | YAML editing with syntax highlighting |
| YAMLSchemaV1 Format | Structured schema format (concepts, indices, examples) |
| Linked Examples | Examples linked to parent schema |
| Text/JSON Examples | Support for both formats |
| Split View | Schema list left, editor right |

### 4. Playbooks (`/playbooks`)
Domain-specific guides and documentation.

| Feature | Description |
|---------|-------------|
| Domain Organization | Purchasing, Sales, Inventory, Finance, HR, Analytics |
| Custom Domains | Add custom domain categories |
| Markdown Content | Full markdown support |
| Filtering by Domain | Filter playbooks by domain |

### 5. Staging Queue (`/staging`)
Review and approve AI-generated knowledge items from support tickets.

| Feature | Description |
|---------|-------------|
| Action Types | New, Merge, Add Variant |
| Similarity Scores | Match percentage with existing items |
| Confidence Scores | AI confidence level |
| Edit & Approve | Modify before approving |
| Reject with Reason | Provide rejection feedback |
| Merge Preview | Compare with target item |

### 6. Metrics Dashboard (`/metrics`)
Analytics and usage tracking.

| Feature | Description |
|---------|-------------|
| Summary Stats | Total items, hits, sessions, unused items |
| Daily Trend Charts | Hits and sessions over time |
| Type Distribution | Pie chart by knowledge type |
| Top Performing Items | Most accessed content |
| Tag Cloud | Popular tags visualization |

### 7. Settings (`/settings`)
System configuration.

| Feature | Description |
|---------|-------------|
| Search Weights | BM25 / Vector weight configuration |
| Pipeline Thresholds | Similarity, confidence thresholds |
| Auto-approve Rules | Variant auto-approval settings |
| Data Retention | Version history, hit data retention |

---

## Data Types

### Base Knowledge Item
All knowledge types extend this base:

```typescript
interface BaseKnowledgeItem {
  id: number
  knowledge_type: 'faq' | 'permission' | 'schema' | 'example' | 'playbook'
  title: string
  tags: string[]
  status: 'draft' | 'published' | 'archived'
  visibility: 'public' | 'internal' | 'restricted'
  created_by?: string
  created_at: string      // ISO 8601
  updated_by?: string
  updated_at?: string     // ISO 8601
}
```

### Content Types by Knowledge Type

#### FAQ
```typescript
interface FAQContent {
  question: string        // The question text
  answer: string          // Markdown-supported answer
}
```

#### Permission (Feature-Centric)
```typescript
interface PermissionContent {
  description: string     // What this feature does
  permissions: string[]   // Required permissions, e.g., ["reports.read", "reports.export"]
  roles: string[]         // Roles with access, e.g., ["Admin", "Auditor"]
  context?: string        // Additional notes (markdown)
}
```

#### Schema
```typescript
interface SchemaContent {
  name: string            // Identifier (lowercase, alphanumeric, dashes)
  definition: string      // YAML string in YAMLSchemaV1 format
}
```

#### Example
```typescript
interface ExampleContent {
  schema_id: number       // Parent schema ID
  description: string     // What this example demonstrates
  content: string         // The example content (query or JSON)
  format: 'text' | 'json' // Content format
}
```

#### Playbook
```typescript
interface PlaybookContent {
  domain: string          // Domain ID (e.g., 'purchasing', 'sales')
  content: string         // Markdown content
}
```

### Staging Queue Item
```typescript
interface StagingKnowledgeItem {
  id: number
  knowledge_type: string
  title: string
  content: Record<string, unknown>
  tags: string[]
  source_ticket_id?: string       // Origin ticket ID
  confidence: number              // AI confidence (0-1)
  status: 'pending' | 'approved' | 'rejected'
  action: 'new' | 'merge' | 'add_variant'
  merge_with_id?: number          // Target item for merge
  similarity: number              // Similarity score (0-1)
  created_at: string
  reviewed_by?: string
  reviewed_at?: string
  review_notes?: string
}
```

---

## API Integration Points

The UI currently uses mock data in hooks. Replace the hook implementations with actual API calls.

### Hook Files to Modify

| File | Purpose | API Endpoints Needed |
|------|---------|---------------------|
| `src/hooks/useFAQ.ts` | FAQ CRUD | `/api/knowledge/faq/*` |
| `src/hooks/usePermissions.ts` | Permissions CRUD | `/api/knowledge/permission/*` |
| `src/hooks/useSchemas.ts` | Schemas & Examples CRUD | `/api/knowledge/schema/*`, `/api/knowledge/example/*` |
| `src/hooks/usePlaybooks.ts` | Playbooks CRUD | `/api/knowledge/playbook/*` |
| `src/hooks/useStaging.ts` | Staging queue operations | `/api/staging/*` |
| `src/hooks/useMetrics.ts` | Analytics data | `/api/metrics/*` |

---

## Required API Endpoints

### Knowledge CRUD (All Types)

```
# List with filtering & pagination
GET /api/knowledge/:type
  Query Params:
    - page: number (default: 1)
    - limit: number (default: 20)
    - search?: string
    - status?: 'draft' | 'published' | 'archived'
    - visibility?: 'public' | 'internal' | 'restricted'
    - tags?: string[] (comma-separated)
    - domain?: string (playbooks only)
    - schema_id?: number (examples only)
  Response: PaginatedResponse<KnowledgeItem>

# Get single item
GET /api/knowledge/:type/:id
  Response: KnowledgeItem

# Create
POST /api/knowledge/:type
  Body: CreateKnowledgeRequest (varies by type)
  Response: KnowledgeItem

# Update
PUT /api/knowledge/:type/:id
  Body: UpdateKnowledgeRequest (varies by type)
  Response: KnowledgeItem

# Delete
DELETE /api/knowledge/:type/:id
  Response: { success: boolean }
```

### Type-Specific Request Bodies

#### FAQ Create/Update
```typescript
interface FAQRequest {
  title: string
  question: string
  answer: string              // Markdown
  tags: string[]
  status: 'draft' | 'published' | 'archived'
  visibility: 'public' | 'internal' | 'restricted'
}
```

#### Permission Create/Update
```typescript
interface PermissionRequest {
  title: string               // Feature name
  description: string
  permissions: string[]       // e.g., ["users.read", "users.write"]
  roles: string[]             // e.g., ["Admin", "Manager"]
  context?: string            // Markdown
  tags: string[]
  status: 'draft' | 'published' | 'archived'
  visibility: 'public' | 'internal' | 'restricted'
}
```

#### Schema Create/Update
```typescript
interface SchemaRequest {
  title: string
  name: string                // Identifier (lowercase, alphanumeric, dashes)
  definition: string          // YAML content
  tags: string[]
  status: 'draft' | 'published' | 'archived'
  visibility: 'public' | 'internal' | 'restricted'
}
```

#### Example Create/Update
```typescript
interface ExampleRequest {
  title: string
  schema_id: number           // Parent schema
  description: string
  content: string
  format: 'text' | 'json'
  tags: string[]
  status: 'draft' | 'published' | 'archived'
  visibility: 'public' | 'internal' | 'restricted'
}
```

#### Playbook Create/Update
```typescript
interface PlaybookRequest {
  title: string
  domain: string              // Domain ID
  content: string             // Markdown
  tags: string[]
  status: 'draft' | 'published' | 'archived'
  visibility: 'public' | 'internal' | 'restricted'
}
```

---

### Staging Queue API

```
# List pending items
GET /api/staging
  Query Params:
    - action?: 'new' | 'merge' | 'add_variant'
    - page?: number
    - limit?: number
  Response: PaginatedResponse<StagingKnowledgeItem>

# Get counts by action type
GET /api/staging/counts
  Response: {
    new: number
    merge: number
    add_variant: number
  }

# Get merge target (existing item to merge with)
GET /api/staging/:id/merge-target
  Response: KnowledgeItem | null

# Approve item
POST /api/staging/:id/approve
  Response: { success: boolean, created_item_id?: number }

# Approve with edits
POST /api/staging/:id/approve
  Body: {
    title?: string
    question?: string
    answer?: string
  }
  Response: { success: boolean, created_item_id?: number }

# Reject item
POST /api/staging/:id/reject
  Body: { reason?: string }
  Response: { success: boolean }
```

---

### Metrics API

```
# Summary statistics
GET /api/metrics/summary
  Query Params:
    - days?: number (default: 7)
  Response: {
    totalItems: number
    publishedItems: number
    draftItems: number
    totalHits: number
    totalSessions: number
    avgDailySessions: number
    neverAccessedCount: number
  }

# Top items by hits
GET /api/metrics/top-items
  Query Params:
    - limit?: number (default: 10)
    - days?: number (default: 7)
  Response: KnowledgeHitStats[]

# Type distribution
GET /api/metrics/type-distribution
  Response: Array<{ type: string, count: number }>

# Tag usage
GET /api/metrics/tags
  Query Params:
    - limit?: number (default: 20)
  Response: Array<{ tag: string, count: number }>

# Daily trend
GET /api/metrics/daily-trend
  Query Params:
    - days?: number (default: 7)
  Response: Array<{
    date: string          // ISO date
    hits: number
    sessions: number
  }>
```

---

### Autocomplete/Lookup APIs

```
# Existing permissions (for autocomplete)
GET /api/permissions/suggestions
  Response: string[]      // e.g., ["users.read", "users.write", "reports.export"]

# Existing roles (for autocomplete)
GET /api/roles/suggestions
  Response: string[]      // e.g., ["Admin", "Manager", "Viewer"]

# Domains list
GET /api/domains
  Response: Array<{
    id: string
    name: string
    description?: string
    isCustom: boolean
  }>

# Add custom domain
POST /api/domains
  Body: { name: string, description?: string }
  Response: Domain
```

---

### Settings API

```
# Get all settings
GET /api/settings
  Response: {
    search: {
      bm25_weight: number
      vector_weight: number
      default_limit: number
    }
    pipeline: {
      similarity_threshold: number
      confidence_threshold: number
      auto_approve_variants: 'no' | 'high-confidence' | 'all'
    }
    maintenance: {
      version_retention_days: number
      hit_retention_days: number
    }
  }

# Update settings
PUT /api/settings
  Body: Settings (partial update supported)
  Response: Settings
```

---

## Response Types

### Paginated Response
```typescript
interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  limit: number
  total_pages: number
}
```

### Knowledge Hit Stats
```typescript
interface KnowledgeHitStats {
  id: number
  knowledge_type: string
  title: string
  tags: string[]
  total_hits: number
  unique_sessions: number
  days_with_hits: number
  last_hit_at: string
  avg_similarity: number
  primary_retrieval_method: string
}
```

---

## Integration Example

### Converting useFAQ.ts to use API

```typescript
// src/hooks/useFAQ.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { FAQItem, FAQFormData, PaginatedResponse } from '@/types/knowledge'

const API_BASE = '/api/knowledge/faq'

async function fetchFAQs(): Promise<PaginatedResponse<FAQItem>> {
  const res = await fetch(API_BASE)
  if (!res.ok) throw new Error('Failed to fetch FAQs')
  return res.json()
}

async function createFAQ(data: FAQFormData): Promise<FAQItem> {
  const res = await fetch(API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: data.title,
      question: data.question,
      answer: data.answer,
      tags: data.tags,
      status: data.status,
      visibility: data.visibility,
    }),
  })
  if (!res.ok) throw new Error('Failed to create FAQ')
  return res.json()
}

async function updateFAQ(id: number, data: FAQFormData): Promise<FAQItem> {
  const res = await fetch(`${API_BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: data.title,
      question: data.question,
      answer: data.answer,
      tags: data.tags,
      status: data.status,
      visibility: data.visibility,
    }),
  })
  if (!res.ok) throw new Error('Failed to update FAQ')
  return res.json()
}

async function deleteFAQ(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete FAQ')
}

export function useFAQs() {
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['faqs'],
    queryFn: fetchFAQs,
  })

  const createMutation = useMutation({
    mutationFn: createFAQ,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['faqs'] }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: FAQFormData }) =>
      updateFAQ(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['faqs'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteFAQ,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['faqs'] }),
  })

  return {
    items: data?.data ?? [],
    isLoading,
    error,
    createItem: createMutation.mutateAsync,
    updateItem: (id: number, data: FAQFormData) =>
      updateMutation.mutateAsync({ id, data }),
    deleteItem: deleteMutation.mutateAsync,
  }
}
```

---

## Environment Configuration

Create a `.env` file:

```env
# API Base URL
VITE_API_URL=http://localhost:8000

# Optional: Auth header
VITE_API_KEY=your-api-key
```

Create an API client:

```typescript
// src/lib/api.ts
const API_URL = import.meta.env.VITE_API_URL ?? ''

export async function apiRequest<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(import.meta.env.VITE_API_KEY && {
        Authorization: `Bearer ${import.meta.env.VITE_API_KEY}`,
      }),
      ...options?.headers,
    },
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.message ?? `API Error: ${res.status}`)
  }

  return res.json()
}
```

---

## Authentication (Future)

The UI is prepared for authentication integration:

1. Add an auth context/provider
2. Protect routes with auth checks
3. Include auth tokens in API requests
4. Add user info to sidebar footer

---

## Next Steps for Backend Integration

1. **Implement API endpoints** matching the specifications above
2. **Update hooks** to use TanStack Query with real API calls
3. **Add error handling** with toast notifications
4. **Add loading states** using TanStack Query's `isLoading`
5. **Add optimistic updates** for better UX
6. **Set up environment variables** for API URL
7. **Add authentication** if required
