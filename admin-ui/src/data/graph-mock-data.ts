import type {
  KnowledgeNode,
  KnowledgeEdge,
  GraphNode,
  GraphEdge,
  NodeType,
  SchemaIndexContent,
  SchemaFieldContent,
  ExampleContent,
} from '@/types/graph'

// Only schema and example mock data retained for dataset/schema features
// All other mock data moved to example_data/ folder
// Tenants, FAQs, Playbooks, Entities, etc. should be fetched from API

export const mockSchemaNodes: KnowledgeNode[] = [
  {
    id: 8,
    tenant_id: 'purchasing',
    node_type: 'schema_index' as NodeType,
    title: 'po_headers',
    summary: 'Purchase order header table',
    dataset_name: 'po_headers',
    content: {
      source_type: 'postgres',
      database: 'purchasing_db',
      schema: 'public',
      table_name: 'po_headers',
      description: 'Main table storing purchase order header information',
      primary_key: ['id'],
      foreign_keys: [
        { column: 'vendor_id', references: 'vendors.id' },
        { column: 'created_by', references: 'users.id' },
      ],
      query_patterns: ['lookup by PO number', 'filter by status', 'filter by date range'],
      row_count_estimate: 150000,
      update_frequency: 'real-time',
    } as SchemaIndexContent,
    tags: ['postgres', 'transactional', 'po'],
    visibility: 'internal',
    status: 'published',
    created_at: '2024-06-06T10:00:00Z',
    created_by: 'admin',
  },
  {
    id: 9,
    tenant_id: 'purchasing',
    node_type: 'schema_field' as NodeType,
    title: 'po_headers.status',
    summary: 'PO status field',
    dataset_name: 'po_headers',
    field_path: 'po_headers.status',
    data_type: 'varchar(20)',
    content: {
      description: 'Current status of the purchase order',
      business_meaning: 'Indicates the lifecycle stage of the PO',
      allowed_values: ['draft', 'pending_approval', 'approved', 'rejected', 'closed', 'cancelled'],
      default_value: 'draft',
      nullable: false,
      indexed: true,
      search_patterns: ['filter by status', 'POs with status X', 'count by status'],
      business_rules: ['Can only transition forward except for cancellation', 'Closed is terminal state'],
    } as SchemaFieldContent,
    tags: ['status', 'enum', 'filterable'],
    visibility: 'internal',
    status: 'published',
    created_at: '2024-06-06T10:00:00Z',
    created_by: 'admin',
  },
  {
    id: 10,
    tenant_id: 'purchasing',
    node_type: 'example' as NodeType,
    title: 'List pending POs for vendor',
    summary: 'Example query to list pending POs',
    dataset_name: 'po_headers',
    content: {
      question: 'Show all pending POs for vendor ABC Corp',
      query: "SELECT * FROM po_headers WHERE vendor_id = (SELECT id FROM vendors WHERE name = 'ABC Corp') AND status = 'pending_approval' ORDER BY created_at DESC",
      query_type: 'sql',
      explanation: 'Joins with vendors table to filter by vendor name, filters for pending approval status, orders by creation date',
      verified: true,
    } as ExampleContent,
    tags: ['vendor', 'status', 'filter'],
    visibility: 'internal',
    status: 'published',
    created_at: '2024-06-07T10:00:00Z',
    created_by: 'admin',
  },
]

export const mockSchemaEdges: KnowledgeEdge[] = [
  { id: 8, source_id: 8, target_id: 9, edge_type: 'parent', weight: 1.0, is_auto_generated: false, created_at: '2024-06-06T10:00:00Z' },
  { id: 9, source_id: 10, target_id: 8, edge_type: 'example_of', weight: 1.0, is_auto_generated: false, created_at: '2024-06-07T10:00:00Z' },
]

export function toGraphNodes(nodes: KnowledgeNode[]): GraphNode[] {
  return nodes.map((node, index) => ({
    ...node,
    x: (index % 4) * 250 + 100,
    y: Math.floor(index / 4) * 150 + 100,
  }))
}

export function toGraphEdges(edges: KnowledgeEdge[]): GraphEdge[] {
  return edges.map(edge => ({
    source: edge.source_id,
    target: edge.target_id,
    edge_type: edge.edge_type,
    weight: edge.weight,
  }))
}
