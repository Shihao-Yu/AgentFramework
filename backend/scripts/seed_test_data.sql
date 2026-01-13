-- Seed test data for FAQ Knowledge Base
-- Run with: docker exec -i faq-postgres psql -U postgres -d faq_knowledge_base < scripts/seed_test_data.sql

-- Clear existing data (optional, comment out if you want to append)
TRUNCATE agent.knowledge_edges CASCADE;
TRUNCATE agent.knowledge_nodes CASCADE;
TRUNCATE agent.staging_nodes CASCADE;
DELETE FROM agent.tenants WHERE id NOT IN ('default', 'shared');

-- Insert tenants
INSERT INTO agent.tenants (id, name, description, is_active) VALUES
  ('purchasing', 'Purchasing', 'Purchase orders and procurement', true),
  ('finance', 'Finance', 'Financial operations and reporting', true)
ON CONFLICT (id) DO NOTHING;

-- Update shared tenant description
UPDATE agent.tenants SET description = 'Cross-tenant shared knowledge' WHERE id = 'shared';

-- Insert knowledge nodes
INSERT INTO agent.knowledge_nodes (id, tenant_id, node_type, title, summary, content, tags, visibility, status, dataset_name, field_path, data_type, created_by, created_at) VALUES

-- Entity: Purchase Order
(1, 'purchasing', 'entity', 'Purchase Order', 'Represents a purchase order in the procurement process',
'{"entity_name": "PurchaseOrder", "entity_path": "PurchaseOrder", "description": "A formal document issued by a buyer to a seller indicating types, quantities, and agreed prices for products or services.", "business_purpose": "Track and manage procurement requests", "key_attributes": [{"name": "po_number", "type": "string", "description": "Unique PO identifier"}, {"name": "status", "type": "enum", "description": "Current status of the PO"}, {"name": "total_amount", "type": "decimal", "description": "Total value of the PO"}], "child_entities": ["PurchaseOrderLine", "PurchaseOrderApproval"], "common_queries": ["Show all pending POs", "Find PO by number", "List POs by vendor"]}',
ARRAY['procurement', 'orders', 'purchasing'], 'internal', 'published', NULL, NULL, NULL, 'admin', '2024-06-01T10:00:00Z'),

-- Entity: Purchase Order Line
(2, 'purchasing', 'entity', 'Purchase Order Line', 'A line item within a purchase order',
'{"entity_name": "PurchaseOrderLine", "entity_path": "PurchaseOrder.Line", "parent_entity": "PurchaseOrder", "description": "Individual items or services being ordered within a PO", "business_purpose": "Track individual items in an order", "key_attributes": [{"name": "line_number", "type": "integer", "description": "Line sequence number"}, {"name": "quantity", "type": "decimal", "description": "Ordered quantity"}, {"name": "unit_price", "type": "decimal", "description": "Price per unit"}], "child_entities": ["PurchaseOrderLineDelivery"]}',
ARRAY['procurement', 'line-items'], 'internal', 'published', NULL, NULL, NULL, 'admin', '2024-06-01T10:00:00Z'),

-- Concept: Delivery Management
(3, 'purchasing', 'concept', 'Delivery Management', 'Everything related to managing deliveries for purchase orders',
'{"description": "Encompasses all processes, entities, and knowledge related to scheduling, tracking, and completing deliveries for purchase orders.", "aliases": ["shipping", "fulfillment", "logistics"], "scope": "Links delivery entities, schemas, FAQs, playbooks, and examples", "key_questions": ["How do I track a delivery?", "What is the delivery status?", "How to reschedule delivery?"]}',
ARRAY['delivery', 'shipping', 'logistics'], 'public', 'published', NULL, NULL, NULL, 'admin', '2024-06-02T10:00:00Z'),

-- FAQ: How do I create a purchase order?
(4, 'purchasing', 'faq', 'How do I create a purchase order?', 'Step-by-step guide to creating a new PO',
'{"question": "How do I create a purchase order?", "answer": "Navigate to Purchasing > Create PO, select vendor, add line items with quantities and prices, review totals, and submit for approval.", "variants": ["How to make a PO?", "Creating purchase orders", "New PO process"]}',
ARRAY['purchasing', 'po', 'how-to'], 'public', 'published', NULL, NULL, NULL, 'admin', '2024-06-03T10:00:00Z'),

-- FAQ: How do I track a delivery?
(5, 'purchasing', 'faq', 'How do I track a delivery?', 'Guide to tracking delivery status',
'{"question": "How do I track a delivery?", "answer": "Go to the PO detail page, click on the line item, and view the Deliveries tab. Each delivery shows status, expected date, and tracking number if available.", "variants": ["Where can I see delivery status?", "Track my order", "Delivery tracking"]}',
ARRAY['delivery', 'tracking', 'how-to'], 'public', 'published', NULL, NULL, NULL, 'admin', '2024-06-03T11:00:00Z'),

-- Playbook: Vendor Onboarding Process
(6, 'purchasing', 'playbook', 'Vendor Onboarding Process', 'Complete guide to onboarding a new vendor',
'{"description": "Step-by-step process for registering and validating a new vendor in the system.", "steps": [{"order": 1, "action": "Submit vendor request form", "owner": "Requestor", "details": "Fill out the new vendor request form with company details"}, {"order": 2, "action": "Verify tax documentation", "owner": "Finance", "details": "Review W-9 and validate tax ID"}, {"order": 3, "action": "Run background check", "owner": "Compliance", "details": "Perform standard vendor due diligence"}, {"order": 4, "action": "Approve vendor setup", "owner": "Procurement Manager", "details": "Final approval for vendor activation"}, {"order": 5, "action": "Create vendor master record", "owner": "Master Data", "details": "Enter vendor into the system"}], "prerequisites": ["Vendor W-9 form", "Business license", "Insurance certificate"], "estimated_time": "3-5 business days"}',
ARRAY['vendor', 'onboarding', 'process'], 'internal', 'published', NULL, NULL, NULL, 'admin', '2024-06-04T10:00:00Z'),

-- Permission Rule: Approve Purchase Order
(7, 'purchasing', 'permission_rule', 'Approve Purchase Order', 'Permission rules for PO approval',
'{"feature": "approve_purchase_order", "description": "Permission rules for approving purchase orders based on amount thresholds", "rules": [{"role": "buyer", "action": "approve", "constraint": {"max_amount": 1000}}, {"role": "manager", "action": "approve", "constraint": {"max_amount": 10000}}, {"role": "director", "action": "approve", "constraint": {"max_amount": 50000}}, {"role": "vp", "action": "approve", "constraint": null}], "escalation_path": ["manager", "director", "vp"]}',
ARRAY['approval', 'authorization', 'po'], 'internal', 'published', NULL, NULL, NULL, 'admin', '2024-06-05T10:00:00Z'),

-- Schema Index: po_headers
(8, 'purchasing', 'schema_index', 'po_headers', 'Purchase order header table',
'{"source_type": "postgres", "database": "purchasing_db", "schema": "public", "table_name": "po_headers", "description": "Main table storing purchase order header information", "primary_key": ["id"], "foreign_keys": [{"column": "vendor_id", "references": "vendors.id"}, {"column": "created_by", "references": "users.id"}], "query_patterns": ["lookup by PO number", "filter by status", "filter by date range"], "row_count_estimate": 150000, "update_frequency": "real-time"}',
ARRAY['postgres', 'transactional', 'po'], 'internal', 'published', 'po_headers', NULL, NULL, 'admin', '2024-06-06T10:00:00Z'),

-- Schema Field: po_headers.status
(9, 'purchasing', 'schema_field', 'po_headers.status', 'PO status field',
'{"description": "Current status of the purchase order", "business_meaning": "Indicates the lifecycle stage of the PO", "allowed_values": ["draft", "pending_approval", "approved", "rejected", "closed", "cancelled"], "default_value": "draft", "nullable": false, "indexed": true, "search_patterns": ["filter by status", "POs with status X", "count by status"], "business_rules": ["Can only transition forward except for cancellation", "Closed is terminal state"]}',
ARRAY['status', 'enum', 'filterable'], 'internal', 'published', 'po_headers', 'po_headers.status', 'varchar(20)', 'admin', '2024-06-06T10:00:00Z'),

-- Example: List pending POs for vendor
(10, 'purchasing', 'example', 'List pending POs for vendor', 'Example query to list pending POs',
'{"question": "Show all pending POs for vendor ABC Corp", "query": "SELECT * FROM po_headers WHERE vendor_id = (SELECT id FROM vendors WHERE name = ''ABC Corp'') AND status = ''pending_approval'' ORDER BY created_at DESC", "query_type": "postgres", "explanation": "Joins with vendors table to filter by vendor name, filters for pending approval status, orders by creation date", "complexity": "medium", "verified": true, "verified_by": "admin", "verified_at": "2024-06-07T10:00:00Z"}',
ARRAY['vendor', 'status', 'filter'], 'internal', 'published', 'po_headers', NULL, NULL, 'admin', '2024-06-07T10:00:00Z'),

-- Concept: Approval Workflow (Finance tenant)
(11, 'finance', 'concept', 'Approval Workflow', 'Processes for approving transactions',
'{"description": "All processes and rules for approving financial transactions and documents", "aliases": ["authorization", "sign-off", "approval chain"], "scope": "Covers PO approvals, invoice approvals, payment approvals", "key_questions": ["Who can approve this?", "What are the approval limits?", "How do I escalate an approval?"]}',
ARRAY['workflow', 'approval', 'authorization'], 'public', 'published', NULL, NULL, NULL, 'admin', '2024-06-08T10:00:00Z'),

-- Entity: Vendor (Shared tenant)
(12, 'shared', 'entity', 'Vendor', 'A supplier or vendor organization',
'{"entity_name": "Vendor", "entity_path": "Vendor", "description": "External organization that supplies goods or services", "business_purpose": "Manage supplier relationships and transactions", "key_attributes": [{"name": "vendor_code", "type": "string", "description": "Unique vendor identifier"}, {"name": "name", "type": "string", "description": "Legal business name"}, {"name": "status", "type": "enum", "description": "Active/Inactive/Blocked"}], "common_operations": [{"action": "create", "description": "Register new vendor"}, {"action": "update", "description": "Modify vendor details"}, {"action": "block", "description": "Block vendor from transactions"}]}',
ARRAY['vendor', 'supplier', 'master-data'], 'public', 'published', NULL, NULL, NULL, 'admin', '2024-06-09T10:00:00Z');

-- Reset sequence to avoid conflicts
SELECT setval('agent.knowledge_nodes_id_seq', (SELECT MAX(id) FROM agent.knowledge_nodes));

-- Insert knowledge edges
INSERT INTO agent.knowledge_edges (id, source_id, target_id, edge_type, weight, is_auto_generated, created_at) VALUES
(1, 1, 2, 'parent', 1.0, false, '2024-06-01T10:00:00Z'),
(2, 1, 4, 'related', 0.9, false, '2024-06-01T10:00:00Z'),
(3, 1, 7, 'related', 0.8, false, '2024-06-01T10:00:00Z'),
(4, 1, 8, 'related', 0.95, false, '2024-06-01T10:00:00Z'),
(5, 3, 5, 'related', 0.85, false, '2024-06-02T10:00:00Z'),
(6, 3, 2, 'related', 0.7, false, '2024-06-02T10:00:00Z'),
(7, 6, 12, 'related', 0.9, false, '2024-06-04T10:00:00Z'),
(8, 8, 9, 'parent', 1.0, false, '2024-06-06T10:00:00Z'),
(9, 10, 8, 'example_of', 1.0, false, '2024-06-07T10:00:00Z'),
(10, 7, 11, 'related', 0.75, false, '2024-06-08T10:00:00Z'),
(11, 4, 5, 'shared_tag', 0.6, true, '2024-06-10T10:00:00Z'),
(12, 1, 12, 'related', 0.8, false, '2024-06-10T10:00:00Z');

-- Reset sequence
SELECT setval('agent.knowledge_edges_id_seq', (SELECT MAX(id) FROM agent.knowledge_edges));

-- Insert staging nodes (pending review items)
INSERT INTO agent.staging_nodes (id, tenant_id, node_type, title, content, tags, status, action, target_node_id, similarity, source, source_reference, confidence, created_at) VALUES

(1, 'purchasing', 'faq', 'How do I cancel a purchase order?',
'{"question": "How do I cancel a purchase order?", "answer": "To cancel a purchase order, go to Purchasing > My POs, find the order, and click Cancel. Note: You can only cancel POs that have not been sent to the vendor. For POs already with the vendor, you need to request a formal cancellation through Procurement."}',
ARRAY['purchasing', 'po', 'cancel'], 'pending', 'new', NULL, 0.45, 'ticket', 'TKT-2024-2001', 0.87, '2024-12-22T10:00:00Z'),

(2, 'purchasing', 'faq', 'What happens if my PO is rejected?',
'{"question": "What happens if my PO is rejected?", "answer": "If your PO is rejected, you will receive an email notification with the rejection reason. You can edit the PO to address the concerns and resubmit it for approval. Common rejection reasons include: insufficient budget, missing justification, or wrong vendor selection."}',
ARRAY['purchasing', 'approval', 'rejection'], 'pending', 'new', NULL, 0.38, 'ticket', 'TKT-2024-2015', 0.92, '2024-12-22T14:30:00Z'),

(3, 'purchasing', 'faq', 'How do I create a purchase order?',
'{"question": "I need to buy office supplies, how do I do that?", "answer": "To purchase office supplies, create a purchase order in the system. Navigate to Purchasing > Create PO, select Office Supplies vendor, add items, and submit for approval."}',
ARRAY['purchasing', 'po', 'office-supplies'], 'pending', 'add_variant', 4, 0.89, 'ticket', 'TKT-2024-2022', 0.78, '2024-12-23T09:15:00Z'),

(4, 'purchasing', 'faq', 'How do I check if a vendor is approved?',
'{"question": "How do I check if a vendor is approved?", "answer": "To check vendor approval status, go to Vendors > Search, enter the vendor name. The status column will show Approved, Pending, or Not Found. Only approved vendors can be used on purchase orders."}',
ARRAY['vendor', 'approval', 'status'], 'pending', 'new', NULL, 0.52, 'ticket', 'TKT-2024-2030', 0.85, '2024-12-23T11:00:00Z'),

(5, 'purchasing', 'faq', 'PO approval thresholds update',
'{"question": "What are the current PO approval limits?", "answer": "Current approval thresholds: Manager up to $5,000, Director $5,001-$10,000, VP $10,001-$50,000, CFO over $50,000. These were updated in Q4 2024."}',
ARRAY['purchasing', 'approval', 'threshold'], 'pending', 'merge', 7, 0.94, 'ticket', 'TKT-2024-2045', 0.91, '2024-12-23T15:30:00Z');

-- Reset sequence
SELECT setval('agent.staging_nodes_id_seq', (SELECT MAX(id) FROM agent.staging_nodes));

-- Insert some sample hits for analytics
INSERT INTO agent.knowledge_hits (node_id, query_text, similarity_score, retrieval_method, session_id, hit_at)
SELECT 
  node_id,
  query_text,
  similarity_score,
  'hybrid_search',
  'session-' || floor(random() * 100)::text,
  NOW() - (random() * interval '30 days')
FROM (
  VALUES
    (4, 'how to create po', 0.92),
    (4, 'make purchase order', 0.88),
    (4, 'create new po', 0.95),
    (5, 'track delivery', 0.87),
    (5, 'where is my order', 0.82),
    (6, 'onboard new vendor', 0.91),
    (6, 'add vendor to system', 0.85),
    (7, 'po approval limits', 0.89),
    (7, 'who approves purchase orders', 0.84)
) AS hits(node_id, query_text, similarity_score);

-- Summary
DO $$
BEGIN
  RAISE NOTICE 'Seed data inserted successfully!';
  RAISE NOTICE 'Tenants: %', (SELECT COUNT(*) FROM agent.tenants);
  RAISE NOTICE 'Knowledge Nodes: %', (SELECT COUNT(*) FROM agent.knowledge_nodes);
  RAISE NOTICE 'Knowledge Edges: %', (SELECT COUNT(*) FROM agent.knowledge_edges);
  RAISE NOTICE 'Staging Nodes: %', (SELECT COUNT(*) FROM agent.staging_nodes);
  RAISE NOTICE 'Knowledge Hits: %', (SELECT COUNT(*) FROM agent.knowledge_hits);
END $$;
