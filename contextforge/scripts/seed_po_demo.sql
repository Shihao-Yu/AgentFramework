-- Seed demo data for Purchase Order Knowledge Graph
-- Run with: docker exec -i faq-postgres psql -U postgres -d knowledge_base < scripts/seed_po_demo.sql
--
-- This creates a rich knowledge graph demonstrating:
-- - Entities: PurchaseOrder, PurchaseOrderLine, PurchaseOrderLineDelivery (Schedule)
-- - Concepts: purchase_order, po_approval_flow, po_line_approval_flow
-- - Features: PO features, PO Search, Schedule Search
-- - Schema: OpenSearch indices for PO, PO Line, Schedule
-- - Examples and FAQs

-- ============================================================================
-- ENTITIES (3 nodes)
-- ============================================================================

INSERT INTO agent.knowledge_nodes (tenant_id, node_type, title, summary, content, tags, visibility, status, created_by) VALUES

-- Entity: Purchase Order
('default', 'entity', 'Purchase Order', 
 'Core procurement document representing a formal order to a vendor',
 '{
   "entity_name": "PurchaseOrder",
   "entity_path": "PurchaseOrder",
   "description": "A formal document issued by a buyer to a seller indicating types, quantities, and agreed prices for products or services. It is the primary document in the procurement lifecycle.",
   "business_purpose": "Track and manage procurement requests from creation through approval to fulfillment",
   "key_attributes": [
     {"name": "po_number", "type": "string", "description": "Unique PO identifier (e.g., PO-2024-00001)"},
     {"name": "status", "type": "enum", "description": "Current lifecycle status"},
     {"name": "total_amount", "type": "decimal", "description": "Sum of all line item amounts"},
     {"name": "vendor_id", "type": "string", "description": "Reference to vendor master"},
     {"name": "requestor", "type": "string", "description": "User who created the PO"},
     {"name": "approval_status", "type": "enum", "description": "Approval workflow state"}
   ],
   "child_entities": ["PurchaseOrderLine"],
   "common_operations": [
     {"action": "create", "description": "Create new purchase order"},
     {"action": "submit", "description": "Submit for approval"},
     {"action": "approve", "description": "Approve the PO"},
     {"action": "close", "description": "Close completed PO"}
   ],
   "common_queries": ["Show pending POs", "Find PO by number", "List POs by vendor", "My POs awaiting approval"]
 }',
 ARRAY['purchase_order', 'procurement', 'ordering', 'approval'],
 'public', 'published', 'seed'),

-- Entity: Purchase Order Line
('default', 'entity', 'Purchase Order Line',
 'Individual line item within a purchase order representing a specific product or service',
 '{
   "entity_name": "PurchaseOrderLine",
   "entity_path": "PurchaseOrder.Line",
   "parent_entity": "PurchaseOrder",
   "description": "A single line item on a purchase order, specifying a particular product or service being ordered with its quantity, price, and delivery requirements.",
   "business_purpose": "Track individual items within an order for receiving and invoicing",
   "key_attributes": [
     {"name": "line_number", "type": "integer", "description": "Sequential line number within PO"},
     {"name": "item_code", "type": "string", "description": "Product or service code"},
     {"name": "description", "type": "string", "description": "Item description"},
     {"name": "quantity", "type": "decimal", "description": "Ordered quantity"},
     {"name": "unit_price", "type": "decimal", "description": "Price per unit"},
     {"name": "line_amount", "type": "decimal", "description": "Quantity x Unit Price"}
   ],
   "child_entities": ["PurchaseOrderLineDelivery"],
   "common_operations": [
     {"action": "add", "description": "Add line to PO"},
     {"action": "update", "description": "Modify quantity or price"},
     {"action": "delete", "description": "Remove line from PO"},
     {"action": "receive", "description": "Record goods receipt"}
   ],
   "common_queries": ["Line items for PO", "Items pending delivery", "Lines by item code"]
 }',
 ARRAY['purchase_order', 'line_item', 'procurement'],
 'public', 'published', 'seed'),

-- Entity: Purchase Order Line Delivery (Schedule)
('default', 'entity', 'Purchase Order Line Delivery',
 'Scheduled delivery for a purchase order line, also known as Schedule',
 '{
   "entity_name": "PurchaseOrderLineDelivery",
   "entity_path": "PurchaseOrder.Line.Delivery",
   "parent_entity": "PurchaseOrderLine",
   "description": "A scheduled delivery for a specific PO line item. Also commonly referred to as a Schedule. Tracks when and where goods should be delivered.",
   "business_purpose": "Track delivery schedules and fulfillment status for ordered items",
   "key_attributes": [
     {"name": "schedule_number", "type": "integer", "description": "Delivery schedule sequence"},
     {"name": "scheduled_date", "type": "date", "description": "Expected delivery date"},
     {"name": "quantity", "type": "decimal", "description": "Quantity for this delivery"},
     {"name": "delivery_address", "type": "string", "description": "Ship-to location"},
     {"name": "status", "type": "enum", "description": "Pending/Shipped/Delivered/Cancelled"},
     {"name": "received_quantity", "type": "decimal", "description": "Actually received quantity"}
   ],
   "child_entities": [],
   "common_operations": [
     {"action": "schedule", "description": "Create delivery schedule"},
     {"action": "reschedule", "description": "Change delivery date"},
     {"action": "receive", "description": "Record goods receipt"},
     {"action": "cancel", "description": "Cancel scheduled delivery"}
   ],
   "common_queries": ["Deliveries due this week", "Overdue schedules", "Schedules by status"]
 }',
 ARRAY['schedule', 'delivery', 'fulfillment', 'logistics'],
 'public', 'published', 'seed');


-- ============================================================================
-- CONCEPTS (3 nodes)
-- ============================================================================

INSERT INTO agent.knowledge_nodes (tenant_id, node_type, title, summary, content, tags, visibility, status, created_by) VALUES

-- Concept: Purchase Order
('default', 'concept', 'Purchase Order',
 'Core concept representing the purchase order domain',
 '{
   "description": "The purchase order concept encompasses all knowledge related to creating, managing, and processing purchase orders in the procurement system.",
   "aliases": ["PO", "order", "procurement order", "buy order"],
   "scope": "Includes PO headers, line items, approvals, and related workflows",
   "key_questions": [
     "How do I create a purchase order?",
     "What is the PO approval process?",
     "How do I track PO status?",
     "What are the PO number formats?"
   ]
 }',
 ARRAY['purchase_order', 'procurement', 'ordering'],
 'public', 'published', 'seed'),

-- Concept: PO Approval Flow
('default', 'concept', 'PO Approval Flow',
 'Concept covering purchase order approval workflows and authorization',
 '{
   "description": "The approval workflow for purchase orders, including authorization levels, approval routing, and escalation procedures.",
   "aliases": ["PO approval", "order approval", "authorization flow", "approval chain"],
   "scope": "Covers approval rules, thresholds, routing logic, and approval history",
   "key_questions": [
     "Who approves my PO?",
     "What are the approval limits?",
     "How long does approval take?",
     "How do I escalate a stuck approval?"
   ]
 }',
 ARRAY['approval', 'workflow', 'authorization', 'purchase_order'],
 'public', 'published', 'seed'),

-- Concept: PO Line Approval Flow
('default', 'concept', 'PO Line Approval Flow',
 'Concept for line-level approval workflows on purchase orders',
 '{
   "description": "Line-level approval workflow that allows individual PO lines to be approved separately based on item categories, amounts, or other criteria.",
   "aliases": ["line approval", "item approval", "category approval"],
   "scope": "Line-specific approval rules and routing",
   "key_questions": [
     "Can lines be approved separately?",
     "What triggers line-level approval?",
     "How are partial approvals handled?"
   ]
 }',
 ARRAY['approval', 'workflow', 'line_item', 'purchase_order'],
 'public', 'published', 'seed');


-- ============================================================================
-- PERMISSION RULES / FEATURES (3 nodes)
-- ============================================================================

INSERT INTO agent.knowledge_nodes (tenant_id, node_type, title, summary, content, tags, visibility, status, created_by) VALUES

-- Feature: Purchase Order (placeholder)
('default', 'permission_rule', 'Purchase Order Features',
 'Feature permissions for purchase order operations',
 '{
   "feature": "purchase_order",
   "description": "Core purchase order functionality including create, edit, submit, and manage POs",
   "rules": [
     {"role": "buyer", "action": "create", "constraint": null},
     {"role": "buyer", "action": "edit", "constraint": {"own_pos_only": true}},
     {"role": "buyer", "action": "submit", "constraint": null},
     {"role": "manager", "action": "edit", "constraint": null},
     {"role": "admin", "action": "*", "constraint": null}
   ],
   "escalation_path": ["manager", "procurement_lead", "admin"]
 }',
 ARRAY['feature', 'purchase_order', 'permissions'],
 'internal', 'published', 'seed'),

-- Feature: PO Search
('default', 'permission_rule', 'PO Search Features',
 'Feature permissions for purchase order search functionality',
 '{
   "feature": "po_search",
   "description": "Search and filter purchase orders across the system",
   "rules": [
     {"role": "viewer", "action": "search", "constraint": {"own_department_only": true}},
     {"role": "buyer", "action": "search", "constraint": null},
     {"role": "manager", "action": "search", "constraint": null},
     {"role": "manager", "action": "export", "constraint": null},
     {"role": "admin", "action": "*", "constraint": null}
   ],
   "escalation_path": []
 }',
 ARRAY['feature', 'search', 'purchase_order'],
 'internal', 'published', 'seed'),

-- Feature: Schedule Search
('default', 'permission_rule', 'Schedule Search Features',
 'Feature permissions for delivery schedule search (Schedule = PO Line Delivery)',
 '{
   "feature": "schedule_search",
   "description": "Search and filter delivery schedules across purchase orders",
   "rules": [
     {"role": "viewer", "action": "search", "constraint": {"own_schedules_only": true}},
     {"role": "buyer", "action": "search", "constraint": null},
     {"role": "logistics", "action": "search", "constraint": null},
     {"role": "logistics", "action": "update_status", "constraint": null},
     {"role": "admin", "action": "*", "constraint": null}
   ],
   "escalation_path": []
 }',
 ARRAY['feature', 'search', 'schedule', 'delivery'],
 'internal', 'published', 'seed');


-- ============================================================================
-- SCHEMA INDEX - OpenSearch Indices (3 nodes)
-- ============================================================================

INSERT INTO agent.knowledge_nodes (tenant_id, node_type, title, summary, content, tags, visibility, status, dataset_name, created_by) VALUES

-- Schema Index: Purchase Order
('default', 'schema_index', 'purchase_orders',
 'OpenSearch index for purchase order documents',
 '{
   "source_type": "elasticsearch",
   "index_name": "purchase_orders",
   "description": "Denormalized purchase order documents for fast search and analytics. Contains header-level PO data with nested line summaries.",
   "primary_key": ["po_id"],
   "query_patterns": [
     "search by PO number",
     "filter by status",
     "filter by vendor",
     "filter by date range",
     "aggregate by status",
     "my pending approvals"
   ],
   "row_count_estimate": 500000,
   "update_frequency": "near-realtime"
 }',
 ARRAY['opensearch', 'search', 'purchase_order'],
 'internal', 'published', 'purchase_orders', 'seed'),

-- Schema Index: Purchase Order Lines
('default', 'schema_index', 'po_lines',
 'OpenSearch index for purchase order line items',
 '{
   "source_type": "elasticsearch",
   "index_name": "po_lines",
   "description": "Individual PO line items with item details, quantities, and pricing. Supports line-level search and analytics.",
   "primary_key": ["po_id", "line_number"],
   "query_patterns": [
     "search by item code",
     "filter by category",
     "lines pending receipt",
     "aggregate by commodity"
   ],
   "row_count_estimate": 2000000,
   "update_frequency": "near-realtime"
 }',
 ARRAY['opensearch', 'search', 'line_item'],
 'internal', 'published', 'po_lines', 'seed'),

-- Schema Index: Schedules (PO Line Deliveries)
('default', 'schema_index', 'schedules',
 'OpenSearch index for delivery schedules (PO Line Deliveries)',
 '{
   "source_type": "elasticsearch",
   "index_name": "schedules",
   "description": "Delivery schedule documents for tracking shipments and receipts. Schedule is a common term for PO Line Delivery.",
   "primary_key": ["schedule_id"],
   "query_patterns": [
     "deliveries due this week",
     "overdue schedules",
     "filter by delivery status",
     "schedules by ship-to location",
     "upcoming deliveries"
   ],
   "row_count_estimate": 3000000,
   "update_frequency": "near-realtime"
 }',
 ARRAY['opensearch', 'search', 'schedule', 'delivery'],
 'internal', 'published', 'schedules', 'seed');


-- ============================================================================
-- SCHEMA FIELDS - Purchase Orders Index (8 fields)
-- ============================================================================

INSERT INTO agent.knowledge_nodes (tenant_id, node_type, title, summary, content, tags, visibility, status, dataset_name, field_path, data_type, created_by) VALUES

('default', 'schema_field', 'purchase_orders.po_number',
 'Unique purchase order number',
 '{
   "description": "Unique identifier for the purchase order in format PO-YYYY-NNNNN",
   "business_meaning": "The PO number used for reference in all communications and documents",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["exact match", "prefix search"],
   "business_rules": ["Auto-generated on creation", "Cannot be modified"]
 }',
 ARRAY['purchase_order', 'identifier'],
 'internal', 'published', 'purchase_orders', 'purchase_orders.po_number', 'keyword', 'seed'),

('default', 'schema_field', 'purchase_orders.status',
 'Current status of the purchase order',
 '{
   "description": "Current lifecycle status of the purchase order",
   "business_meaning": "Indicates where the PO is in its lifecycle from draft to closed",
   "allowed_values": ["draft", "pending_approval", "approved", "partially_received", "received", "closed", "cancelled"],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["filter by status", "status count"],
   "business_rules": ["Status transitions are controlled", "Cancelled is terminal"]
 }',
 ARRAY['purchase_order', 'status', 'filterable'],
 'internal', 'published', 'purchase_orders', 'purchase_orders.status', 'keyword', 'seed'),

('default', 'schema_field', 'purchase_orders.vendor_name',
 'Name of the vendor/supplier',
 '{
   "description": "Display name of the vendor associated with this PO",
   "business_meaning": "The supplier who will fulfill this order",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["text search", "autocomplete"]
 }',
 ARRAY['purchase_order', 'vendor'],
 'internal', 'published', 'purchase_orders', 'purchase_orders.vendor_name', 'text', 'seed'),

('default', 'schema_field', 'purchase_orders.total_amount',
 'Total value of the purchase order',
 '{
   "description": "Sum of all line item amounts on the PO",
   "business_meaning": "Total spend for this purchase order",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["range filter", "aggregation"]
 }',
 ARRAY['purchase_order', 'amount', 'numeric'],
 'internal', 'published', 'purchase_orders', 'purchase_orders.total_amount', 'float', 'seed'),

('default', 'schema_field', 'purchase_orders.created_date',
 'Date the PO was created',
 '{
   "description": "Timestamp when the purchase order was created",
   "business_meaning": "Order creation date for tracking and reporting",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["date range filter", "created in last N days"]
 }',
 ARRAY['purchase_order', 'date'],
 'internal', 'published', 'purchase_orders', 'purchase_orders.created_date', 'date', 'seed'),

('default', 'schema_field', 'purchase_orders.requestor',
 'User who created the purchase order',
 '{
   "description": "Username or ID of the person who created the PO",
   "business_meaning": "The buyer or requestor responsible for this order",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["exact match", "my POs"]
 }',
 ARRAY['purchase_order', 'user'],
 'internal', 'published', 'purchase_orders', 'purchase_orders.requestor', 'keyword', 'seed'),

('default', 'schema_field', 'purchase_orders.approval_status',
 'Current approval workflow status',
 '{
   "description": "Status of the PO in the approval workflow",
   "business_meaning": "Shows if the PO is pending approval, approved, or rejected",
   "allowed_values": ["not_submitted", "pending", "approved", "rejected"],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["filter by approval status", "pending my approval"]
 }',
 ARRAY['purchase_order', 'approval', 'workflow'],
 'internal', 'published', 'purchase_orders', 'purchase_orders.approval_status', 'keyword', 'seed'),

('default', 'schema_field', 'purchase_orders.line_count',
 'Number of line items on the PO',
 '{
   "description": "Count of line items associated with this PO",
   "business_meaning": "How many different items are being ordered",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["range filter"]
 }',
 ARRAY['purchase_order', 'numeric'],
 'internal', 'published', 'purchase_orders', 'purchase_orders.line_count', 'integer', 'seed');


-- ============================================================================
-- SCHEMA FIELDS - PO Lines Index (6 fields)
-- ============================================================================

INSERT INTO agent.knowledge_nodes (tenant_id, node_type, title, summary, content, tags, visibility, status, dataset_name, field_path, data_type, created_by) VALUES

('default', 'schema_field', 'po_lines.po_number',
 'Parent PO number',
 '{
   "description": "Reference to the parent purchase order",
   "business_meaning": "Links the line item to its purchase order",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["exact match", "join to PO"]
 }',
 ARRAY['line_item', 'purchase_order'],
 'internal', 'published', 'po_lines', 'po_lines.po_number', 'keyword', 'seed'),

('default', 'schema_field', 'po_lines.line_number',
 'Line sequence number',
 '{
   "description": "Sequential line number within the PO",
   "business_meaning": "Position of this item in the order",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["exact match"]
 }',
 ARRAY['line_item'],
 'internal', 'published', 'po_lines', 'po_lines.line_number', 'integer', 'seed'),

('default', 'schema_field', 'po_lines.item_code',
 'Product or service code',
 '{
   "description": "Identifier for the product or service being ordered",
   "business_meaning": "SKU or service code from the catalog",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["exact match", "prefix search"]
 }',
 ARRAY['line_item', 'product'],
 'internal', 'published', 'po_lines', 'po_lines.item_code', 'keyword', 'seed'),

('default', 'schema_field', 'po_lines.quantity',
 'Ordered quantity',
 '{
   "description": "Number of units ordered for this line",
   "business_meaning": "How many items are being ordered",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["range filter"]
 }',
 ARRAY['line_item', 'quantity'],
 'internal', 'published', 'po_lines', 'po_lines.quantity', 'float', 'seed'),

('default', 'schema_field', 'po_lines.unit_price',
 'Price per unit',
 '{
   "description": "Price for one unit of the item",
   "business_meaning": "Cost per item for calculating line totals",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["range filter"]
 }',
 ARRAY['line_item', 'price'],
 'internal', 'published', 'po_lines', 'po_lines.unit_price', 'float', 'seed'),

('default', 'schema_field', 'po_lines.category',
 'Item category',
 '{
   "description": "Classification category for the item",
   "business_meaning": "Used for spend analysis and approval routing",
   "allowed_values": ["office_supplies", "it_equipment", "services", "raw_materials", "mro", "capex"],
   "nullable": true,
   "indexed": true,
   "search_patterns": ["filter by category", "aggregate by category"]
 }',
 ARRAY['line_item', 'category'],
 'internal', 'published', 'po_lines', 'po_lines.category', 'keyword', 'seed');


-- ============================================================================
-- SCHEMA FIELDS - Schedules Index (7 fields)
-- ============================================================================

INSERT INTO agent.knowledge_nodes (tenant_id, node_type, title, summary, content, tags, visibility, status, dataset_name, field_path, data_type, created_by) VALUES

('default', 'schema_field', 'schedules.schedule_id',
 'Unique schedule identifier',
 '{
   "description": "Unique ID for the delivery schedule record",
   "business_meaning": "Reference number for tracking this specific delivery",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["exact match"]
 }',
 ARRAY['schedule', 'identifier'],
 'internal', 'published', 'schedules', 'schedules.schedule_id', 'keyword', 'seed'),

('default', 'schema_field', 'schedules.po_number',
 'Parent PO number',
 '{
   "description": "Reference to the parent purchase order",
   "business_meaning": "Links schedule to its purchase order",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["exact match"]
 }',
 ARRAY['schedule', 'purchase_order'],
 'internal', 'published', 'schedules', 'schedules.po_number', 'keyword', 'seed'),

('default', 'schema_field', 'schedules.scheduled_date',
 'Expected delivery date',
 '{
   "description": "Date when delivery is scheduled to arrive",
   "business_meaning": "The expected arrival date for this shipment",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["date range", "due this week", "overdue"]
 }',
 ARRAY['schedule', 'date', 'delivery'],
 'internal', 'published', 'schedules', 'schedules.scheduled_date', 'date', 'seed'),

('default', 'schema_field', 'schedules.delivery_status',
 'Current delivery status',
 '{
   "description": "Status of the scheduled delivery",
   "business_meaning": "Tracks where the delivery is in the fulfillment process",
   "allowed_values": ["pending", "shipped", "in_transit", "delivered", "partially_received", "cancelled"],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["filter by status", "pending deliveries"]
 }',
 ARRAY['schedule', 'status', 'delivery'],
 'internal', 'published', 'schedules', 'schedules.delivery_status', 'keyword', 'seed'),

('default', 'schema_field', 'schedules.quantity',
 'Scheduled delivery quantity',
 '{
   "description": "Number of units scheduled for this delivery",
   "business_meaning": "How many items are expected in this shipment",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["range filter"]
 }',
 ARRAY['schedule', 'quantity'],
 'internal', 'published', 'schedules', 'schedules.quantity', 'float', 'seed'),

('default', 'schema_field', 'schedules.ship_to_location',
 'Delivery destination',
 '{
   "description": "Location code or address where items should be delivered",
   "business_meaning": "Where the goods will be shipped",
   "allowed_values": [],
   "nullable": false,
   "indexed": true,
   "search_patterns": ["exact match", "filter by location"]
 }',
 ARRAY['schedule', 'location', 'delivery'],
 'internal', 'published', 'schedules', 'schedules.ship_to_location', 'keyword', 'seed'),

('default', 'schema_field', 'schedules.received_quantity',
 'Actually received quantity',
 '{
   "description": "Number of units actually received for this schedule",
   "business_meaning": "Tracks fulfillment against scheduled quantity",
   "allowed_values": [],
   "nullable": true,
   "indexed": true,
   "search_patterns": ["range filter", "partial receipts"]
 }',
 ARRAY['schedule', 'quantity', 'receipt'],
 'internal', 'published', 'schedules', 'schedules.received_quantity', 'float', 'seed');


-- ============================================================================
-- EXAMPLES - Query Examples (5 nodes)
-- ============================================================================

INSERT INTO agent.knowledge_nodes (tenant_id, node_type, title, summary, content, tags, visibility, status, dataset_name, created_by) VALUES

('default', 'example', 'Find pending POs for approval',
 'Query to find purchase orders waiting for approval',
 '{
   "question": "Show me all purchase orders pending approval",
   "query": "{\"query\": {\"bool\": {\"must\": [{\"term\": {\"approval_status\": \"pending\"}}]}}}",
   "query_type": "elasticsearch",
   "explanation": "Filters purchase_orders index for documents where approval_status equals pending",
   "verified": true
 }',
 ARRAY['purchase_order', 'approval', 'search'],
 'internal', 'published', 'purchase_orders', 'seed'),

('default', 'example', 'POs by vendor with status',
 'Query to find POs for a specific vendor filtered by status',
 '{
   "question": "Find all approved POs from ACME Corp",
   "query": "{\"query\": {\"bool\": {\"must\": [{\"match\": {\"vendor_name\": \"ACME Corp\"}}, {\"term\": {\"status\": \"approved\"}}]}}}",
   "query_type": "elasticsearch",
   "explanation": "Combines text match on vendor_name with term filter on status",
   "verified": true
 }',
 ARRAY['purchase_order', 'vendor', 'search'],
 'internal', 'published', 'purchase_orders', 'seed'),

('default', 'example', 'Schedules due this week',
 'Query to find delivery schedules due in the current week',
 '{
   "question": "Show schedules due this week",
   "query": "{\"query\": {\"range\": {\"scheduled_date\": {\"gte\": \"now/w\", \"lte\": \"now+1w/w\"}}}}",
   "query_type": "elasticsearch",
   "explanation": "Uses date range query with relative date math to find schedules in current week",
   "verified": true
 }',
 ARRAY['schedule', 'delivery', 'date'],
 'internal', 'published', 'schedules', 'seed'),

('default', 'example', 'Overdue deliveries',
 'Query to find schedules that are past their scheduled date and not delivered',
 '{
   "question": "Find overdue schedules that have not been delivered",
   "query": "{\"query\": {\"bool\": {\"must\": [{\"range\": {\"scheduled_date\": {\"lt\": \"now\"}}}, {\"terms\": {\"delivery_status\": [\"pending\", \"shipped\", \"in_transit\"]}}]}}}",
   "query_type": "elasticsearch",
   "explanation": "Finds schedules where scheduled_date is in the past and status is not delivered or cancelled",
   "verified": true
 }',
 ARRAY['schedule', 'delivery', 'overdue'],
 'internal', 'published', 'schedules', 'seed'),

('default', 'example', 'Line items by category',
 'Query to aggregate PO line items by category',
 '{
   "question": "Show total spend by category",
   "query": "{\"size\": 0, \"aggs\": {\"by_category\": {\"terms\": {\"field\": \"category\"}, \"aggs\": {\"total_spend\": {\"sum\": {\"script\": {\"source\": \"doc[''quantity''].value * doc[''unit_price''].value\"}}}}}}}",
   "query_type": "elasticsearch",
   "explanation": "Aggregates line items by category and calculates total spend (qty * price) for each",
   "verified": true
 }',
 ARRAY['line_item', 'category', 'analytics'],
 'internal', 'published', 'po_lines', 'seed');


-- ============================================================================
-- FAQs (5 nodes)
-- ============================================================================

INSERT INTO agent.knowledge_nodes (tenant_id, node_type, title, summary, content, tags, visibility, status, created_by) VALUES

('default', 'faq', 'How do I create a purchase order?',
 'Step-by-step guide to creating a new PO',
 '{
   "question": "How do I create a purchase order?",
   "answer": "To create a purchase order:\n1. Navigate to Purchasing > Create PO\n2. Select a vendor from the dropdown\n3. Add line items with item code, quantity, and price\n4. Review the total amount\n5. Click Submit to send for approval\n\nNote: You can save as draft if you need to complete later.",
   "variants": ["How to make a PO", "Creating purchase orders", "New PO process", "Start a new order"]
 }',
 ARRAY['purchase_order', 'how-to', 'create'],
 'public', 'published', 'seed'),

('default', 'faq', 'What are the PO approval limits?',
 'Explanation of approval thresholds by role',
 '{
   "question": "What are the PO approval limits?",
   "answer": "PO approval limits are based on total PO value:\n- Buyer: Up to $1,000\n- Manager: Up to $10,000\n- Director: Up to $50,000\n- VP: Up to $100,000\n- CFO: Unlimited\n\nApprovals automatically route to the appropriate level based on amount.",
   "variants": ["Who approves my PO", "Approval thresholds", "How much can I approve"]
 }',
 ARRAY['approval', 'purchase_order', 'limits'],
 'public', 'published', 'seed'),

('default', 'faq', 'How do I track a delivery?',
 'Guide to tracking delivery schedule status',
 '{
   "question": "How do I track a delivery?",
   "answer": "To track a delivery:\n1. Open the purchase order\n2. Click on the line item\n3. View the Deliveries/Schedules tab\n4. Each schedule shows status, expected date, and tracking info\n\nYou can also search schedules directly in Schedule Search.",
   "variants": ["Track my order", "Delivery status", "Where is my shipment", "Check delivery"]
 }',
 ARRAY['schedule', 'delivery', 'tracking', 'how-to'],
 'public', 'published', 'seed'),

('default', 'faq', 'What is a Schedule?',
 'Definition of Schedule in the procurement context',
 '{
   "question": "What is a Schedule in procurement?",
   "answer": "A Schedule (also called PO Line Delivery) represents a planned delivery for a specific line item on a purchase order. It includes:\n- Scheduled delivery date\n- Quantity to be delivered\n- Ship-to location\n- Delivery status\n\nOne PO line can have multiple schedules for split deliveries.",
   "variants": ["What does schedule mean", "Schedule vs delivery", "PO schedule definition"]
 }',
 ARRAY['schedule', 'delivery', 'glossary', 'definition'],
 'public', 'published', 'seed'),

('default', 'faq', 'Why is my PO stuck in pending?',
 'Troubleshooting POs stuck in pending approval',
 '{
   "question": "Why is my PO stuck in pending approval?",
   "answer": "Common reasons for stuck POs:\n1. Approver is out of office - check backup approvers\n2. Missing information - verify all required fields are complete\n3. Budget exceeded - check department budget availability\n4. Vendor issue - vendor may be blocked or inactive\n\nYou can view approval history in the PO detail page.",
   "variants": ["PO not approved", "Approval taking too long", "PO stuck", "Why no approval"]
 }',
 ARRAY['approval', 'purchase_order', 'troubleshooting'],
 'public', 'published', 'seed');


-- ============================================================================
-- Now trigger edge generation for shared tags
-- This will create SHARED_TAG edges between nodes with common tags
-- ============================================================================

-- Note: In production, this happens automatically on node create/update
-- For seed data, we can manually trigger or let the sync service handle it

SELECT 'Seed data inserted successfully. Run /api/sync/generate/all to create edges.' as status;
