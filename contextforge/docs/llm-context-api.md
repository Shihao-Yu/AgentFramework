# LLM Context API

The `/api/llm-context` endpoint provides LLM-optimized, hierarchical context for AI agents. Unlike the standard `/api/context` endpoint (designed for UI rendering), this endpoint returns pre-formatted text ready for prompt injection.

## Endpoint

```
POST /api/llm-context
```

## Use Cases

| Need | Configuration |
|------|---------------|
| FAQ + Playbook context | `include_knowledge: true` |
| Schema for query generation | `include_schema: true, dataset_names: ["orders"]` |
| Both combined | `include_knowledge: true, include_schema: true` |

---

## Example 1: Knowledge Context Only (FAQ/Playbook)

### Request
```json
{
  "query": "how do I approve purchase orders over 10k",
  "tenant_ids": ["purchasing", "shared"],
  "include_knowledge": true,
  "include_schema": false,
  "knowledge_types": ["faq", "playbook", "permission_rule"],
  "max_knowledge_items": 10,
  "expand_graph": true,
  "max_depth": 2
}
```

### Response
```json
{
  "context": "# Knowledge Context\n\n## Approval\n\n### FAQs\n**Q: What is the PO approval process?**\nA: Purchase orders follow a tiered approval process based on amount:\n- Under $5,000: Manager approval\n- $5,000-$10,000: Director approval\n- Over $10,000: VP approval\n\n### Permissions\n**PO Approval Limits**\nFeature: Purchase Order Approval\nDescription: Approval authority based on PO amount\nRoles: manager, director, vp\nPermissions: po.approve, po.approve_high_value\nConditions: POs over $10,000 require director approval\n\n### Playbooks\n**Escalating PO Approvals**\nDomain: Purchasing\nSummary: How to escalate stuck approvals\n## When to Escalate\n1. Approval pending > 48 hours\n2. Approver on leave\n...",
  
  "knowledge": {
    "groups": [
      {
        "topic": "Approval",
        "relevance_score": 0.94,
        "faqs": [
          {
            "id": 102,
            "question": "What is the PO approval process?",
            "answer": "Purchase orders follow a tiered approval process...",
            "tags": ["approval", "process", "po"],
            "score": 0.78
          }
        ],
        "playbooks": [
          {
            "id": 206,
            "title": "Escalating PO Approvals",
            "domain": "Purchasing",
            "summary": "How to escalate stuck approvals",
            "content": "## When to Escalate\n\n1. Approval pending > 48 hours...",
            "tags": ["escalation", "approval"],
            "score": 0.65
          }
        ],
        "permissions": [
          {
            "id": 301,
            "title": "PO Approval Limits",
            "feature": "Purchase Order Approval",
            "description": "Approval authority based on PO amount",
            "permissions": ["po.approve", "po.approve_high_value"],
            "roles": ["manager", "director", "vp"],
            "conditions": "POs over $10,000 require director approval",
            "tags": ["approval", "limits"],
            "score": 0.94
          }
        ],
        "concepts": []
      }
    ],
    "formatted": "## Approval\n\n### FAQs\n...",
    "total_faqs": 1,
    "total_playbooks": 1,
    "total_permissions": 1,
    "total_concepts": 0
  },
  
  "schema_context": null,
  
  "stats": {
    "faqs": 1,
    "playbooks": 1,
    "permissions": 1,
    "concepts": 0,
    "schema_fields": 0,
    "schema_concepts": 0,
    "examples": 0,
    "entry_points_found": 3,
    "nodes_expanded": 2,
    "max_depth_reached": 1
  }
}
```

---

## Example 2: Schema Context Only (Query Generation)

### Request
```json
{
  "query": "show me pending purchase orders with vendor details",
  "tenant_ids": ["purchasing"],
  "include_knowledge": false,
  "include_schema": true,
  "dataset_names": ["po_headers"],
  "max_schema_fields": 20,
  "max_examples": 3,
  "expand_graph": true
}
```

### Response
```json
{
  "context": "# Schema Context\n\n## Schema Fields\n\n### [PurchaseOrder] [MATCHED]\n\n- **po_headers.status** (varchar) *\n  Current status of the purchase order\n  Business meaning: Indicates the lifecycle stage of the PO\n  Values: draft, pending_approval, approved, rejected, closed, cancelled\n  Value meanings: draft=new, pending_approval=awaiting, approved=confirmed\n\n- **po_headers.vendor_id** (int)\n  Foreign key to vendors table\n  References: vendors.id\n\n- **po_headers.total_amount** (decimal)\n  Total PO amount including taxes\n\n### [Vendor]\n\n- **vendors.name** (varchar)\n  Legal name of the vendor company\n\n- **vendors.payment_terms** (varchar)\n  Standard payment terms\n  Values: NET30, NET60, COD\n\n## Examples\n\n**1. Show all pending POs for vendor ABC Corp** [verified]\n```sql\nSELECT * FROM po_headers \nWHERE vendor_id = (SELECT id FROM vendors WHERE name = 'ABC Corp') \nAND status = 'pending_approval'\n```\nExplanation: Joins with vendors table to filter by vendor name",
  
  "knowledge": null,
  
  "schema_context": {
    "dataset_name": "po_headers",
    "source_type": "postgres",
    "concept_groups": [
      {
        "concept": "PurchaseOrder",
        "relevance_score": 0.95,
        "is_matched": true,
        "fields": [
          {
            "path": "po_headers.status",
            "data_type": "varchar",
            "description": "Current status of the purchase order",
            "business_meaning": "Indicates the lifecycle stage of the PO",
            "allowed_values": ["draft", "pending_approval", "approved", "rejected", "closed", "cancelled"],
            "value_meanings": {
              "draft": "new",
              "pending_approval": "awaiting",
              "approved": "confirmed"
            },
            "is_nullable": false,
            "is_primary_key": false,
            "is_foreign_key": false,
            "references": null,
            "score": 1.0,
            "is_direct_match": true
          },
          {
            "path": "po_headers.vendor_id",
            "data_type": "int",
            "description": "Foreign key to vendors table",
            "business_meaning": null,
            "allowed_values": null,
            "value_meanings": null,
            "is_nullable": false,
            "is_primary_key": false,
            "is_foreign_key": true,
            "references": "vendors.id",
            "score": 0.8,
            "is_direct_match": false
          }
        ],
        "children": []
      },
      {
        "concept": "Vendor",
        "relevance_score": 0.72,
        "is_matched": false,
        "fields": [
          {
            "path": "vendors.name",
            "data_type": "varchar",
            "description": "Legal name of the vendor company",
            "score": 0.5,
            "is_direct_match": false
          }
        ],
        "children": []
      }
    ],
    "examples": [
      {
        "question": "Show all pending POs for vendor ABC Corp",
        "query": "SELECT * FROM po_headers WHERE vendor_id = (SELECT id FROM vendors WHERE name = 'ABC Corp') AND status = 'pending_approval'",
        "query_type": "sql",
        "explanation": "Joins with vendors table to filter by vendor name",
        "verified": true,
        "relevance_score": 0.85
      }
    ],
    "formatted": "## Schema Fields\n\n### [PurchaseOrder] [MATCHED]\n...",
    "total_fields": 5,
    "total_concepts": 2,
    "total_examples": 1
  },
  
  "stats": {
    "faqs": 0,
    "playbooks": 0,
    "permissions": 0,
    "concepts": 0,
    "schema_fields": 5,
    "schema_concepts": 2,
    "examples": 1,
    "entry_points_found": 3,
    "nodes_expanded": 4,
    "max_depth_reached": 2
  }
}
```

---

## Example 3: Combined Context

### Request
```json
{
  "query": "how do I check vendor payment status",
  "tenant_ids": ["purchasing", "payables"],
  "include_knowledge": true,
  "include_schema": true,
  "knowledge_types": ["faq", "playbook"],
  "dataset_names": ["vendors", "payments"],
  "max_knowledge_items": 5,
  "max_schema_fields": 15,
  "max_examples": 2
}
```

### Response
The `context` field will contain both sections:

```
# Knowledge Context

## Payments

### FAQs
**Q: How do I check if a vendor has been paid?**
A: Navigate to Vendor Portal > Payment History...

### Playbooks
**Vendor Payment Inquiry Process**
...

---

# Schema Context

## Schema Fields

### [Payment] [MATCHED]
- **payments.status** (varchar) *
  Payment status
  Values: pending, processed, failed, cancelled

### [Vendor]
- **vendors.payment_terms** (varchar)
  ...

## Examples

**1. Get payment status for vendor**
```sql
SELECT v.name, p.status, p.amount 
FROM vendors v 
JOIN payments p ON p.vendor_id = v.id
WHERE v.id = ?
```
```

---

## Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | required | Natural language query |
| `tenant_ids` | string[] | user's tenants | Tenants to search |
| `include_knowledge` | bool | true | Include FAQ/playbook/permissions |
| `include_schema` | bool | false | Include schema fields/examples |
| `knowledge_types` | NodeType[] | null | Filter: faq, playbook, permission_rule, concept |
| `tags` | string[] | null | Filter by tags (AND logic) |
| `dataset_names` | string[] | null | Filter schema to specific datasets |
| `search_method` | string | "hybrid" | hybrid, bm25, or vector |
| `expand_graph` | bool | true | Expand to related nodes |
| `max_depth` | int | 2 | Graph traversal depth (1-5) |
| `max_knowledge_items` | int | 20 | Max knowledge items (1-50) |
| `max_schema_fields` | int | 30 | Max schema fields (1-100) |
| `max_examples` | int | 5 | Max Q&A examples (0-20) |

---

## Agent Usage Pattern

```python
# Simple: Just inject context into prompt
response = requests.post("/api/llm-context", json={
    "query": user_question,
    "include_knowledge": True
})

prompt = f"""You are a helpful assistant.

Context:
{response.json()["context"]}

User question: {user_question}

Answer based on the context above."""

# Advanced: Access structured data
data = response.json()
if data["knowledge"]:
    for group in data["knowledge"]["groups"]:
        print(f"Topic: {group['topic']}")
        for faq in group["faqs"]:
            print(f"  FAQ: {faq['question']}")
```

---

## Comparison: /api/context vs /api/llm-context

| Aspect | /api/context | /api/llm-context |
|--------|--------------|------------------|
| **Consumer** | Admin UI | AI Agents |
| **Response** | Flat JSON nodes | Hierarchical + formatted string |
| **Ready for LLM** | No (needs transformation) | Yes (use `context` field directly) |
| **Groups by** | Nothing (flat list) | Topic/Concept |
| **Schema support** | Basic nodes | Concept-grouped with examples |
