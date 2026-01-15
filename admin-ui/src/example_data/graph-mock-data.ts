import type {
  KnowledgeNode,
  KnowledgeEdge,
  GraphNode,
  GraphEdge,
  Tenant,
  TenantAccess,
  NodeType,
  EdgeType,
  FAQContent,
  PlaybookContent,
  EntityContent,
  ConceptContent,
  SchemaIndexContent,
  SchemaFieldContent,
  ExampleContent,
  PermissionRuleContent,
} from '@/types/graph'

export const mockTenants: Tenant[] = [
  {
    id: 'purchasing',
    name: 'Purchasing',
    description: 'Purchase orders and procurement',
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'finance',
    name: 'Finance',
    description: 'Financial operations and reporting',
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'shared',
    name: 'Shared',
    description: 'Cross-tenant shared knowledge',
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
  },
]

export const mockTenantAccess: TenantAccess[] = [
  { tenant_id: 'purchasing', tenant_name: 'Purchasing', role: 'admin', node_count: 45 },
  { tenant_id: 'finance', tenant_name: 'Finance', role: 'editor', node_count: 23 },
  { tenant_id: 'shared', tenant_name: 'Shared', role: 'viewer', node_count: 12 },
]

export const mockNodes: KnowledgeNode[] = [
  {
    id: 1,
    tenant_id: 'purchasing',
    node_type: 'entity' as NodeType,
    title: 'Purchase Order',
    summary: 'Represents a purchase order in the procurement process',
    content: {
      entity_name: 'PurchaseOrder',
      entity_path: 'PurchaseOrder',
      description: 'A formal document issued by a buyer to a seller indicating types, quantities, and agreed prices for products or services.',
      business_purpose: 'Track and manage procurement requests',
      key_attributes: [
        { name: 'po_number', type: 'string', description: 'Unique PO identifier' },
        { name: 'status', type: 'enum', description: 'Current status of the PO' },
        { name: 'total_amount', type: 'decimal', description: 'Total value of the PO' },
      ],
      child_entities: ['PurchaseOrderLine', 'PurchaseOrderApproval'],
      common_queries: ['Show all pending POs', 'Find PO by number', 'List POs by vendor'],
    } as EntityContent,
    tags: ['procurement', 'orders', 'purchasing'],
    visibility: 'internal',
    status: 'published',
    created_at: '2024-06-01T10:00:00Z',
    created_by: 'admin',
  },
  {
    id: 2,
    tenant_id: 'purchasing',
    node_type: 'entity' as NodeType,
    title: 'Purchase Order Line',
    summary: 'A line item within a purchase order',
    content: {
      entity_name: 'PurchaseOrderLine',
      entity_path: 'PurchaseOrder.Line',
      parent_entity: 'PurchaseOrder',
      description: 'Individual items or services being ordered within a PO',
      business_purpose: 'Track individual items in an order',
      key_attributes: [
        { name: 'line_number', type: 'integer', description: 'Line sequence number' },
        { name: 'quantity', type: 'decimal', description: 'Ordered quantity' },
        { name: 'unit_price', type: 'decimal', description: 'Price per unit' },
      ],
      child_entities: ['PurchaseOrderLineDelivery'],
    } as EntityContent,
    tags: ['procurement', 'line-items'],
    visibility: 'internal',
    status: 'published',
    created_at: '2024-06-01T10:00:00Z',
    created_by: 'admin',
  },
  {
    id: 3,
    tenant_id: 'purchasing',
    node_type: 'concept' as NodeType,
    title: 'Delivery Management',
    summary: 'Everything related to managing deliveries for purchase orders',
    content: {
      description: 'Encompasses all processes, entities, and knowledge related to scheduling, tracking, and completing deliveries for purchase orders.',
      aliases: ['shipping', 'fulfillment', 'logistics'],
      scope: 'Links delivery entities, schemas, FAQs, playbooks, and examples',
      key_questions: [
        'How do I track a delivery?',
        'What is the delivery status?',
        'How to reschedule delivery?',
      ],
    } as ConceptContent,
    tags: ['delivery', 'shipping', 'logistics'],
    visibility: 'public',
    status: 'published',
    created_at: '2024-06-02T10:00:00Z',
    created_by: 'admin',
  },
  {
    id: 4,
    tenant_id: 'purchasing',
    node_type: 'faq' as NodeType,
    title: 'How do I create a purchase order?',
    summary: 'Step-by-step guide to creating a new PO',
    content: {
      question: 'How do I create a purchase order?',
      answer: 'Navigate to Purchasing > Create PO, select vendor, add line items with quantities and prices, review totals, and submit for approval.',
      variants: ['How to make a PO?', 'Creating purchase orders', 'New PO process'],
    } as FAQContent,
    tags: ['purchasing', 'po', 'how-to'],
    visibility: 'public',
    status: 'published',
    created_at: '2024-06-03T10:00:00Z',
    created_by: 'admin',
  },
  {
    id: 5,
    tenant_id: 'purchasing',
    node_type: 'faq' as NodeType,
    title: 'How do I track a delivery?',
    summary: 'Guide to tracking delivery status',
    content: {
      question: 'How do I track a delivery?',
      answer: 'Go to the PO detail page, click on the line item, and view the Deliveries tab. Each delivery shows status, expected date, and tracking number if available.',
      variants: ['Where can I see delivery status?', 'Track my order', 'Delivery tracking'],
    } as FAQContent,
    tags: ['delivery', 'tracking', 'how-to'],
    visibility: 'public',
    status: 'published',
    created_at: '2024-06-03T11:00:00Z',
    created_by: 'admin',
  },
  {
    id: 6,
    tenant_id: 'purchasing',
    node_type: 'playbook' as NodeType,
    title: 'Vendor Onboarding Process',
    summary: 'Complete guide to onboarding a new vendor',
    content: {
      description: 'Step-by-step process for registering and validating a new vendor in the system.',
      steps: [
        { order: 1, action: 'Submit vendor request form', owner: 'Requestor', details: 'Fill out the new vendor request form with company details' },
        { order: 2, action: 'Verify tax documentation', owner: 'Finance', details: 'Review W-9 and validate tax ID' },
        { order: 3, action: 'Run background check', owner: 'Compliance', details: 'Perform standard vendor due diligence' },
        { order: 4, action: 'Approve vendor setup', owner: 'Procurement Manager', details: 'Final approval for vendor activation' },
        { order: 5, action: 'Create vendor master record', owner: 'Master Data', details: 'Enter vendor into the system' },
      ],
      prerequisites: ['Vendor W-9 form', 'Business license', 'Insurance certificate'],
      estimated_time: '3-5 business days',
    } as PlaybookContent,
    tags: ['vendor', 'onboarding', 'process'],
    visibility: 'internal',
    status: 'published',
    created_at: '2024-06-04T10:00:00Z',
    created_by: 'admin',
  },
  {
    id: 7,
    tenant_id: 'purchasing',
    node_type: 'permission_rule' as NodeType,
    title: 'Approve Purchase Order',
    summary: 'Permission rules for PO approval',
    content: {
      feature: 'approve_purchase_order',
      description: 'Permission rules for approving purchase orders based on amount thresholds',
      rules: [
        { role: 'buyer', action: 'approve', constraint: { max_amount: 1000 } },
        { role: 'manager', action: 'approve', constraint: { max_amount: 10000 } },
        { role: 'director', action: 'approve', constraint: { max_amount: 50000 } },
        { role: 'vp', action: 'approve', constraint: null },
      ],
      escalation_path: ['manager', 'director', 'vp'],
    } as PermissionRuleContent,
    tags: ['approval', 'authorization', 'po'],
    visibility: 'internal',
    status: 'published',
    created_at: '2024-06-05T10:00:00Z',
    created_by: 'admin',
  },
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
      query_type: 'postgres',
      explanation: 'Joins with vendors table to filter by vendor name, filters for pending approval status, orders by creation date',
      complexity: 'medium',
      verified: true,
      verified_by: 'admin',
      verified_at: '2024-06-07T10:00:00Z',
    } as ExampleContent,
    tags: ['vendor', 'status', 'filter'],
    visibility: 'internal',
    status: 'published',
    created_at: '2024-06-07T10:00:00Z',
    created_by: 'admin',
  },
  {
    id: 11,
    tenant_id: 'finance',
    node_type: 'concept' as NodeType,
    title: 'Approval Workflow',
    summary: 'Processes for approving transactions',
    content: {
      description: 'All processes and rules for approving financial transactions and documents',
      aliases: ['authorization', 'sign-off', 'approval chain'],
      scope: 'Covers PO approvals, invoice approvals, payment approvals',
      key_questions: [
        'Who can approve this?',
        'What are the approval limits?',
        'How do I escalate an approval?',
      ],
    } as ConceptContent,
    tags: ['workflow', 'approval', 'authorization'],
    visibility: 'public',
    status: 'published',
    created_at: '2024-06-08T10:00:00Z',
    created_by: 'admin',
  },
  {
    id: 12,
    tenant_id: 'shared',
    node_type: 'entity' as NodeType,
    title: 'Vendor',
    summary: 'A supplier or vendor organization',
    content: {
      entity_name: 'Vendor',
      entity_path: 'Vendor',
      description: 'External organization that supplies goods or services',
      business_purpose: 'Manage supplier relationships and transactions',
      key_attributes: [
        { name: 'vendor_code', type: 'string', description: 'Unique vendor identifier' },
        { name: 'name', type: 'string', description: 'Legal business name' },
        { name: 'status', type: 'enum', description: 'Active/Inactive/Blocked' },
      ],
      common_operations: [
        { action: 'create', description: 'Register new vendor' },
        { action: 'update', description: 'Modify vendor details' },
        { action: 'block', description: 'Block vendor from transactions' },
      ],
    } as EntityContent,
    tags: ['vendor', 'supplier', 'master-data'],
    visibility: 'public',
    status: 'published',
    created_at: '2024-06-09T10:00:00Z',
    created_by: 'admin',
  },
]

export const mockEdges: KnowledgeEdge[] = [
  { id: 1, source_id: 1, target_id: 2, edge_type: 'parent' as EdgeType, weight: 1.0, is_auto_generated: false, created_at: '2024-06-01T10:00:00Z' },
  { id: 2, source_id: 1, target_id: 4, edge_type: 'related' as EdgeType, weight: 0.9, is_auto_generated: false, created_at: '2024-06-01T10:00:00Z' },
  { id: 3, source_id: 1, target_id: 7, edge_type: 'related' as EdgeType, weight: 0.8, is_auto_generated: false, created_at: '2024-06-01T10:00:00Z' },
  { id: 4, source_id: 1, target_id: 8, edge_type: 'related' as EdgeType, weight: 0.95, is_auto_generated: false, created_at: '2024-06-01T10:00:00Z' },
  { id: 5, source_id: 3, target_id: 5, edge_type: 'related' as EdgeType, weight: 0.85, is_auto_generated: false, created_at: '2024-06-02T10:00:00Z' },
  { id: 6, source_id: 3, target_id: 2, edge_type: 'related' as EdgeType, weight: 0.7, is_auto_generated: false, created_at: '2024-06-02T10:00:00Z' },
  { id: 7, source_id: 6, target_id: 12, edge_type: 'related' as EdgeType, weight: 0.9, is_auto_generated: false, created_at: '2024-06-04T10:00:00Z' },
  { id: 8, source_id: 8, target_id: 9, edge_type: 'parent' as EdgeType, weight: 1.0, is_auto_generated: false, created_at: '2024-06-06T10:00:00Z' },
  { id: 9, source_id: 10, target_id: 8, edge_type: 'example_of' as EdgeType, weight: 1.0, is_auto_generated: false, created_at: '2024-06-07T10:00:00Z' },
  { id: 10, source_id: 7, target_id: 11, edge_type: 'related' as EdgeType, weight: 0.75, is_auto_generated: false, created_at: '2024-06-08T10:00:00Z' },
  { id: 11, source_id: 4, target_id: 5, edge_type: 'shared_tag' as EdgeType, weight: 0.6, is_auto_generated: true, created_at: '2024-06-10T10:00:00Z' },
  { id: 12, source_id: 1, target_id: 12, edge_type: 'related' as EdgeType, weight: 0.8, is_auto_generated: false, created_at: '2024-06-10T10:00:00Z' },
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

export function getNodesByTenant(tenantIds: string[]): KnowledgeNode[] {
  return mockNodes.filter(node => tenantIds.includes(node.tenant_id))
}

export function getEdgesForNodes(nodeIds: number[]): KnowledgeEdge[] {
  const nodeIdSet = new Set(nodeIds)
  return mockEdges.filter(
    edge => nodeIdSet.has(edge.source_id) && nodeIdSet.has(edge.target_id)
  )
}

export function searchNodes(query: string, tenantIds: string[], nodeTypes?: NodeType[]): KnowledgeNode[] {
  const queryLower = query.toLowerCase()
  return mockNodes.filter(node => {
    if (!tenantIds.includes(node.tenant_id)) return false
    if (nodeTypes && nodeTypes.length > 0 && !nodeTypes.includes(node.node_type)) return false
    
    return (
      node.title.toLowerCase().includes(queryLower) ||
      node.summary?.toLowerCase().includes(queryLower) ||
      node.tags.some(tag => tag.toLowerCase().includes(queryLower))
    )
  })
}
