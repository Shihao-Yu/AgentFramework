import { useState, useCallback } from 'react'
import type { SchemaItem, ExampleItem, SchemaFormData, ExampleFormData } from '@/types/knowledge'
import { createEmptySchemaTemplate } from '@/lib/schemas/yamlSchemaV1'

const initialSchemas: SchemaItem[] = [
  {
    id: 1,
    knowledge_type: 'schema',
    title: 'Purchase Orders Schema',
    content: {
      name: 'purchase-orders',
      definition: `version: "1.0"
tenant_id: purchasing

concepts:
  - name: purchaseorder
    description: "Core purchase order entity with header and line information"
    aliases:
      - po
      - purchase order
      - order
    value_synonyms:
      Pending:
        - pending
        - waiting
        - awaiting approval
      Approved:
        - approved
        - accepted
        - confirmed

  - name: requestor
    description: "Person who submitted or created the purchase order"
    aliases:
      - requester
      - submitter
    related_pronouns:
      - my
      - mine
      - i created

indices:
  - name: po_index
    description: "Purchase order documents with approval workflow"
    query_mode: PPL
    primary_key: PONumber
    fields:
      - path: PONumber
        es_type: keyword
        description: "Unique purchase order number"
        maps_to: purchaseorder
      - path: Status
        es_type: keyword
        description: "Order status"
        maps_to: purchaseorder
        allowed_values:
          - Pending
          - Approved
          - Rejected
          - Completed
      - path: OrderDate
        es_type: date
        description: "Date the order was created"
        maps_to: purchaseorder

examples:
  - question: "Show pending orders"
    query: 'source=po_index | where Status = "Pending"'
    concepts_used:
      - purchaseorder
    fields_used:
      - Status
    verified: true`,
    },
    tags: ['purchasing', 'orders'],
    status: 'published',
    visibility: 'internal',
    created_at: '2024-01-10T10:00:00Z',
    updated_at: '2024-01-20T14:30:00Z',
  },
  {
    id: 2,
    knowledge_type: 'schema',
    title: 'Users Schema',
    content: {
      name: 'users',
      definition: createEmptySchemaTemplate('users'),
    },
    tags: ['users', 'identity'],
    status: 'draft',
    visibility: 'internal',
    created_at: '2024-01-15T09:00:00Z',
    updated_at: '2024-01-15T09:00:00Z',
  },
]

const initialExamples: ExampleItem[] = [
  {
    id: 101,
    knowledge_type: 'example',
    title: 'Find pending purchase orders',
    content: {
      schema_id: 1,
      description: 'Query to find all purchase orders with pending status',
      content: 'source=po_index | where Status = "Pending" | fields PONumber, OrderDate, RequestorUser.DisplayName',
      format: 'text',
    },
    tags: ['query', 'status-filter'],
    status: 'published',
    visibility: 'internal',
    created_at: '2024-01-12T10:00:00Z',
    updated_at: '2024-01-12T10:00:00Z',
  },
  {
    id: 102,
    knowledge_type: 'example',
    title: 'Count orders by status',
    content: {
      schema_id: 1,
      description: 'Aggregation query to count orders grouped by their status',
      content: 'source=po_index | stats count() by Status',
      format: 'text',
    },
    tags: ['aggregation', 'stats'],
    status: 'published',
    visibility: 'internal',
    created_at: '2024-01-14T11:00:00Z',
    updated_at: '2024-01-14T11:00:00Z',
  },
  {
    id: 103,
    knowledge_type: 'example',
    title: 'API Request Example',
    content: {
      schema_id: 1,
      description: 'Example JSON payload for creating a purchase order via API',
      content: JSON.stringify({
        PONumber: 'PO-2024-001',
        Status: 'Pending',
        OrderDate: '2024-01-20',
        RequestorUser: {
          UserID: 'user123',
          DisplayName: 'John Doe'
        },
        Items: [
          { SKU: 'ITEM-001', Quantity: 10, UnitPrice: 25.00 }
        ]
      }, null, 2),
      format: 'json',
    },
    tags: ['api', 'json'],
    status: 'draft',
    visibility: 'internal',
    created_at: '2024-01-18T15:00:00Z',
    updated_at: '2024-01-18T15:00:00Z',
  },
]

export function useSchemas() {
  const [schemas, setSchemas] = useState<SchemaItem[]>(initialSchemas)
  const [examples, setExamples] = useState<ExampleItem[]>(initialExamples)

  // Schema CRUD
  const createSchema = useCallback(async (data: SchemaFormData) => {
    const newItem: SchemaItem = {
      id: Date.now(),
      knowledge_type: 'schema',
      title: data.title,
      content: {
        name: data.name,
        definition: data.definition,
      },
      tags: data.tags,
      status: data.status,
      visibility: data.visibility,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    setSchemas((prev) => [newItem, ...prev])
    return newItem
  }, [])

  const updateSchema = useCallback(async (id: number, data: SchemaFormData) => {
    setSchemas((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              title: data.title,
              content: {
                name: data.name,
                definition: data.definition,
              },
              tags: data.tags,
              status: data.status,
              visibility: data.visibility,
              updated_at: new Date().toISOString(),
            }
          : item
      )
    )
  }, [])

  const deleteSchema = useCallback(async (id: number) => {
    setSchemas((prev) => prev.filter((item) => item.id !== id))
    // Also delete associated examples
    setExamples((prev) => prev.filter((item) => item.content.schema_id !== id))
  }, [])

  // Example CRUD
  const createExample = useCallback(async (data: ExampleFormData) => {
    const newItem: ExampleItem = {
      id: Date.now(),
      knowledge_type: 'example',
      title: data.title,
      content: {
        schema_id: data.schema_id,
        description: data.description,
        content: data.content,
        format: data.format,
      },
      tags: data.tags,
      status: data.status,
      visibility: data.visibility,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    setExamples((prev) => [newItem, ...prev])
    return newItem
  }, [])

  const updateExample = useCallback(async (id: number, data: ExampleFormData) => {
    setExamples((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              title: data.title,
              content: {
                schema_id: data.schema_id,
                description: data.description,
                content: data.content,
                format: data.format,
              },
              tags: data.tags,
              status: data.status,
              visibility: data.visibility,
              updated_at: new Date().toISOString(),
            }
          : item
      )
    )
  }, [])

  const deleteExample = useCallback(async (id: number) => {
    setExamples((prev) => prev.filter((item) => item.id !== id))
  }, [])

  // Get examples for a specific schema
  const getExamplesForSchema = useCallback(
    (schemaId: number) => {
      return examples.filter((e) => e.content.schema_id === schemaId)
    },
    [examples]
  )

  return {
    schemas,
    examples,
    createSchema,
    updateSchema,
    deleteSchema,
    createExample,
    updateExample,
    deleteExample,
    getExamplesForSchema,
  }
}
