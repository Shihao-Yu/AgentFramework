# Knowledge Base System Design v2.0

> **Document Type**: Technical Design Document  
> **Status**: Proposed  
> **Author**: Engineering Team  
> **Last Updated**: January 2025

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Motivation](#2-background--motivation)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [System Vision](#4-system-vision)
5. [Architecture Overview](#5-architecture-overview)
6. [Data Model](#6-data-model)
7. [Search & Retrieval](#7-search--retrieval)
8. [Graph Layer](#8-graph-layer)
9. [Pipeline Design](#9-pipeline-design)
10. [API Design](#10-api-design)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [Operational Considerations](#12-operational-considerations)
13. [Success Metrics](#13-success-metrics)

---

## 1. Executive Summary

### What We're Building

A unified **Knowledge Base System** that evolves from FAQ-only storage to a comprehensive knowledge management platform supporting multiple knowledge types, graph-based relationships, and intelligent retrieval.

### Key Capabilities

| Capability | Description |
|------------|-------------|
| **Multi-Type Knowledge** | FAQ, policies, procedures, business rules, context, permissions |
| **Hybrid Search** | BM25 keyword + vector semantic search with RRF fusion |
| **Question Variants** | Multiple phrasings per knowledge item (1:N) |
| **Graph Relationships** | Explicit + implicit (tag-based, similarity-based) connections |
| **Graph-Enhanced Retrieval** | Multi-hop context traversal for comprehensive answers |
| **Real-Time Graph Sync** | Event-driven graph updates without full reload |
| **Usage Analytics** | Track retrieval patterns and knowledge effectiveness |
| **Version History** | Audit trail with time-based expiration |

### Expected Outcomes

- **+18-25% retrieval accuracy** via hybrid search
- **Richer agent responses** via graph context
- **Reduced duplicate content** via variant detection
- **Better knowledge management** via relationships and categories
- **Operational visibility** via usage analytics

---

## 2. Background & Motivation

### 2.1 Current State

The existing system is FAQ-centric:

```
┌─────────────────────────────────────┐
│         purchasing_faq              │
├─────────────────────────────────────┤
│ question (single)                   │
│ answer                              │
│ tags[]                              │
│ embedding (vector search only)      │
└─────────────────────────────────────┘
```

**Limitations:**
- Single knowledge type (FAQ only)
- Vector-only search (misses keyword matches)
- 1:1 question-answer mapping (no variants)
- No relationships between items
- No usage visibility

### 2.2 Why Generalize to Knowledge Base?

| Current Need | Future Need |
|--------------|-------------|
| "How do I create a PO?" (FAQ) | "What's our policy on sole-source purchases?" (Policy) |
| One-off Q&A | "Walk me through vendor onboarding" (Procedure) |
| Isolated answers | "Why does this order need VP approval?" (Business Rule + Context) |

**Key Insight**: Agent effectiveness improves dramatically when it can:
1. Find the right entry point (hybrid search)
2. Gather surrounding context (graph traversal)
3. Synthesize comprehensive answers (multiple knowledge types)

### 2.3 Why Graph?

Traditional search returns isolated results. Graph-enhanced retrieval provides **context**:

```
User: "Can I approve this $15K laptop order?"

Traditional Search:
  → FAQ: "How to approve large purchases" (single result)

Graph-Enhanced Search:
  → FAQ: "How to approve large purchases" (entry point)
  → Business Rule: "Orders >$10K need VP approval" (1 hop)
  → Policy: "IT Equipment Procurement Policy" (2 hops)
  → Context: "Dell is a preferred vendor" (1 hop)
  → Permission: "Your role: Buyer - max $5K" (1 hop)

Agent can now provide a complete, contextual answer.
```

---

## 3. Goals & Non-Goals

### 3.1 Goals

| Goal | Success Criteria |
|------|------------------|
| **Unified knowledge storage** | Single schema supports all knowledge types |
| **Improved search accuracy** | +18% NDCG via hybrid search |
| **Variant support** | Multiple phrasings per item |
| **Graph relationships** | Explicit + auto-generated connections |
| **Graph-enhanced retrieval** | Multi-hop context in search results |
| **Real-time graph updates** | <5s latency from DB change to graph |
| **Usage tracking** | Know which knowledge gets used |
| **Backward compatibility** | Existing FAQ integrations continue working |

### 3.2 Non-Goals (For Now)

| Non-Goal | Rationale |
|----------|-----------|
| Full RBAC/permissions | Start with visibility levels; add RBAC later |
| Multi-tenant isolation | Single tenant for now |
| Collaborative editing | Out of scope for v1 |
| External knowledge sources | Focus on internal knowledge first |
| Neo4j migration | NetworkX sufficient for current scale |

---

## 4. System Vision

### 4.1 Knowledge Types

| Type | Structure | Use Case |
|------|-----------|----------|
| **FAQ** | Question → Answer | "How do I...?" questions |
| **Policy** | Title → Body + Dates | Governance, compliance |
| **Procedure** | Title → Ordered Steps | Workflows, processes |
| **Business Rule** | Condition → Action | Decision logic |
| **Context** | Entity → Description | Vendor info, product details |
| **Permission** | Role → Allowed Actions | Access control documentation |
| **Reference** | Term → Definition | Glossary, terminology |
| **Troubleshooting** | Problem → Diagnosis → Solution | Issue resolution |

### 4.2 Content Examples

```json
// FAQ
{
  "knowledge_type": "faq",
  "title": "How do I create a purchase order?",
  "content": {
    "question": "How do I create a purchase order?",
    "answer": "Navigate to Purchasing > Create PO, select vendor, add line items..."
  },
  "tags": ["purchasing", "po", "how-to"]
}

// Business Rule
{
  "knowledge_type": "business_rule",
  "title": "Large Order Approval Requirement",
  "content": {
    "condition": "Purchase order amount exceeds $10,000",
    "action": "Requires VP-level approval before submission",
    "exceptions": ["Emergency purchases", "Pre-approved annual contracts"]
  },
  "tags": ["purchasing", "approval", "threshold"]
}

// Business Context
{
  "knowledge_type": "context",
  "title": "Vendor: Dell Technologies",
  "content": {
    "entity_type": "vendor",
    "entity_id": "VENDOR-DELL-001",
    "description": "Primary IT hardware supplier. Preferred vendor with negotiated pricing.",
    "contract_end": "2025-12-31",
    "discount": "15% on bulk orders",
    "contacts": ["dell-rep@company.com"]
  },
  "tags": ["vendor", "it-hardware", "preferred"]
}

// Procedure
{
  "knowledge_type": "procedure",
  "title": "Vendor Onboarding Process",
  "content": {
    "steps": [
      {"order": 1, "action": "Submit vendor request form", "owner": "Requestor"},
      {"order": 2, "action": "Verify tax documentation", "owner": "Finance"},
      {"order": 3, "action": "Run background check", "owner": "Compliance"},
      {"order": 4, "action": "Approve vendor setup", "owner": "Procurement Manager"},
      {"order": 5, "action": "Create vendor master record", "owner": "Master Data"}
    ]
  },
  "tags": ["vendor", "onboarding", "process"]
}
```

### 4.3 Relationship Types

| Type | Direction | Example |
|------|-----------|---------|
| `related` | Bidirectional | FAQ ↔ FAQ (similar topics) |
| `parent` / `child` | Hierarchical | Policy → Procedure |
| `see_also` | Directional | FAQ → Reference |
| `supersedes` | Directional | New Policy → Old Policy |
| `depends_on` | Directional | Procedure → Prerequisite |
| `implements` | Directional | Procedure → Policy |
| `governs` | Directional | Business Rule → Entity |

---

## 5. Architecture Overview

### 5.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                       │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────────┤
│  Support Tickets│  Manual Entry   │  Document Import│  LLM Generation           │
│  (ClickHouse)   │  (Admin UI)     │  (Future)       │  (Future)                 │
└────────┬────────┴────────┬────────┴────────┬────────┴───────────────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INGESTION PIPELINE                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  • Knowledge type detection                                              │    │
│  │  • Similarity search (items + variants)                                  │    │
│  │  • Action decision: SKIP / ADD_VARIANT / MERGE / NEW                    │    │
│  │  • Quality validation                                                    │    │
│  │  • Staging for review (MERGE/NEW) or direct insert (ADD_VARIANT)        │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           POSTGRESQL (Source of Truth)                          │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────────┐    │
│  │ knowledge_items   │  │ knowledge_variants│  │ knowledge_relationships   │    │
│  │ + search_vector   │  │ + embedding       │  │ (explicit connections)    │    │
│  │ + embedding       │  └───────────────────┘  └───────────────────────────┘    │
│  │ + graph_version   │                                                          │
│  └─────────┬─────────┘  ┌───────────────────┐  ┌───────────────────────────┐    │
│            │            │ knowledge_versions│  │ knowledge_hits            │    │
│            │            │ (90-day retention)│  │ (usage tracking)          │    │
│            │            └───────────────────┘  └───────────────────────────┘    │
│            │                                                                    │
│            │            ┌───────────────────────────────────────────────────┐   │
│            └───────────▶│ knowledge_graph_events (event sourcing)           │   │
│                         │ • node_created, node_updated, node_deleted        │   │
│                         │ • edge_created, edge_deleted                      │   │
│                         └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Event-driven sync
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           GRAPH LAYER (NetworkX)                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         In-Memory Graph                                 │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │  Nodes: Knowledge Items                                          │    │    │
│  │  │  • id, type, title, tags, category, visibility                  │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │  Edges (3 sources):                                              │    │    │
│  │  │  • Explicit: From knowledge_relationships table                  │    │    │
│  │  │  • Tag-based: Items sharing tags (implicit)                     │    │    │
│  │  │  • Similarity: Embedding similarity > threshold (implicit)       │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Graph Service:                                                         │    │
│  │  • Full load on startup                                                 │    │
│  │  • Real-time updates via event processor                               │    │
│  │  • Neighbor queries, path finding                                       │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           RETRIEVAL LAYER                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Hybrid Search (PostgreSQL):                                            │    │
│  │  • BM25 full-text search (40% weight)                                   │    │
│  │  • Vector similarity search (60% weight)                                │    │
│  │  • Reciprocal Rank Fusion (RRF) scoring                                │    │
│  │  • Searches both items AND variants                                     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                      +                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Graph Enhancement (NetworkX):                                          │    │
│  │  • Find entry points via hybrid search                                  │    │
│  │  • Expand via N-hop graph traversal                                     │    │
│  │  • Filter by node type, tags, visibility                               │    │
│  │  • Score and rank context items                                         │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                          │
│                                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Hit Recording:                                                         │    │
│  │  • Track which items retrieved                                          │    │
│  │  • Track query text, similarity score                                   │    │
│  │  • Track retrieval method (hybrid vs graph)                            │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CONSUMERS                                             │
├─────────────────────────────────────┬───────────────────────────────────────────┤
│  Agent Framework                    │  Admin UI                                 │
│  • Contextual knowledge retrieval   │  • Knowledge CRUD                         │
│  • Multi-type answers               │  • Variant management                     │
│                                     │  • Relationship management                │
│                                     │  • Category organization                  │
│                                     │  • Usage analytics                        │
└─────────────────────────────────────┴───────────────────────────────────────────┘
```

### 5.2 Data Flow Summary

| Flow | Path | Latency |
|------|------|---------|
| **New Knowledge (Manual)** | Admin UI → PostgreSQL → Graph Event → Graph Update | <5s |
| **New Knowledge (Pipeline)** | Ticket → Pipeline → Staging/Direct → PostgreSQL → Graph | Minutes |
| **Search Query** | Query → Hybrid Search → Graph Expansion → Results | <200ms |
| **Graph Update** | DB Trigger → Event Table → Event Processor → Graph | <5s |

---

## 6. Data Model

### 6.1 Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  ┌───────────────────────┐                                                      │
│  │ knowledge_categories  │                                                      │
│  ├───────────────────────┤                                                      │
│  │ id (PK)               │◀─────────────┐                                       │
│  │ name                  │              │ parent_id (self-ref)                  │
│  │ slug                  │──────────────┘                                       │
│  │ parent_id (FK)        │                                                      │
│  │ default_visibility    │                                                      │
│  └───────────┬───────────┘                                                      │
│              │ 1:N                                                              │
│              ▼                                                                  │
│  ┌───────────────────────┐       ┌─────────────────────────┐                    │
│  │ knowledge_items       │       │ knowledge_variants      │                    │
│  ├───────────────────────┤       ├─────────────────────────┤                    │
│  │ id (PK)               │──────<│ knowledge_item_id (FK)  │                    │
│  │ knowledge_type        │  1:N  │ id (PK)                 │                    │
│  │ category_id (FK)      │       │ variant_text            │                    │
│  │ title                 │       │ embedding               │                    │
│  │ summary               │       │ source                  │                    │
│  │ content (JSONB)       │       │ graph_version           │                    │
│  │ embedding             │       └─────────────────────────┘                    │
│  │ search_vector         │                                                      │
│  │ tags[]                │       ┌─────────────────────────┐                    │
│  │ visibility            │       │ knowledge_hits          │                    │
│  │ status                │       ├─────────────────────────┤                    │
│  │ graph_version         │──────<│ knowledge_item_id (FK)  │                    │
│  │ created_at            │  1:N  │ variant_id (FK)         │──── variants       │
│  │ updated_at            │       │ query_text              │                    │
│  └───────────┬───────────┘       │ similarity_score        │                    │
│              │                   │ retrieval_method        │                    │
│              │ 1:N               │ session_id              │                    │
│              ▼                   │ hit_at                  │                    │
│  ┌───────────────────────┐       └─────────────────────────┘                    │
│  │ knowledge_versions    │                                                      │
│  ├───────────────────────┤                                                      │
│  │ id (PK)               │                                                      │
│  │ knowledge_item_id(FK) │                                                      │
│  │ version_number        │                                                      │
│  │ title                 │                                                      │
│  │ content (JSONB)       │                                                      │
│  │ change_type           │                                                      │
│  │ changed_by            │                                                      │
│  │ changed_at            │                                                      │
│  └───────────────────────┘                                                      │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐      │
│  │ knowledge_relationships                                               │      │
│  ├───────────────────────────────────────────────────────────────────────┤      │
│  │ id (PK)                                                               │      │
│  │ source_id (FK) ──────────────────────────────────────────────────────│◀─┐   │
│  │ target_id (FK) ──────────────────────────────────────────────────────│◀─┤   │
│  │ relationship_type                                                     │  │   │
│  │ weight                                                                │  │   │
│  │ is_bidirectional                                                      │  │   │
│  │ is_auto_generated                                                     │  │   │
│  └───────────────────────────────────────────────────────────────────────┘  │   │
│                                                                             │   │
│                                          knowledge_items ───────────────────┘   │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐      │
│  │ knowledge_graph_events (Event Sourcing for Real-Time Sync)            │      │
│  ├───────────────────────────────────────────────────────────────────────┤      │
│  │ id (PK)                                                               │      │
│  │ event_type (node_created, node_updated, edge_created, etc.)          │      │
│  │ entity_type                                                           │      │
│  │ entity_id                                                             │      │
│  │ payload (JSONB)                                                       │      │
│  │ sequence_number                                                       │      │
│  │ processed_at                                                          │      │
│  └───────────────────────────────────────────────────────────────────────┘      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **JSONB for content** | Flexible structure per knowledge type without schema changes |
| **Generated tsvector** | Automatic FTS index maintenance |
| **Tags as TEXT[]** | Simple, GIN-indexable, sufficient for filtering and graph edges |
| **graph_version column** | Enables efficient incremental sync detection |
| **Event sourcing for graph** | Decouples DB from graph; enables replay and debugging |
| **Separate variants table** | Clean 1:N relationship; independent embedding per variant |

---

## 7. Search & Retrieval

### 7.1 Hybrid Search Strategy

```
Query: "approve large purchase order"
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│                    PARALLEL SEARCH                            │
├───────────────────────────┬───────────────────────────────────┤
│   BM25 (Full-Text)        │   Vector (Semantic)               │
│   Weight: 40%             │   Weight: 60%                     │
├───────────────────────────┼───────────────────────────────────┤
│   Searches:               │   Searches:                       │
│   • knowledge_items.      │   • knowledge_items.embedding     │
│     search_vector         │   • knowledge_variants.embedding  │
│   • knowledge_variants    │                                   │
│     (to_tsvector)         │                                   │
├───────────────────────────┼───────────────────────────────────┤
│   Returns: Ranked by      │   Returns: Ranked by              │
│   ts_rank_cd()            │   cosine distance                 │
└───────────────────────────┴───────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│            RECIPROCAL RANK FUSION (RRF)                       │
│                                                               │
│   RRF_score(doc) = Σ (weight / (k + rank))                   │
│                                                               │
│   • k = 60 (smoothing constant)                               │
│   • Combines ranks from all search sources                    │
│   • Deduplicates by knowledge_item_id                        │
└───────────────────────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│                    FILTERED RESULTS                           │
│                                                               │
│   Filters applied:                                            │
│   • knowledge_type (optional)                                 │
│   • tags (optional, AND/OR)                                   │
│   • category_id (optional)                                    │
│   • visibility (<= user's access level)                       │
│   • status = 'published'                                      │
│   • effective_until > NOW() (if set)                          │
└───────────────────────────────────────────────────────────────┘
```

### 7.2 Why Hybrid Search?

| Query Type | BM25 Strength | Vector Strength |
|------------|---------------|-----------------|
| "PO-2024-001" (exact code) | ✅ Perfect match | ❌ May miss |
| "how to buy stuff" (casual) | ❌ Poor vocabulary match | ✅ Semantic match |
| "purchase order approval process" | ✅ Good keyword match | ✅ Good semantic match |

**Result**: Hybrid search handles all query types effectively.

### 7.3 Expected Performance

| Metric | Vector Only | Hybrid (RRF) | Improvement |
|--------|-------------|--------------|-------------|
| NDCG@10 | 0.72 | 0.85 | +18% |
| Exact term recall | 40% | 95% | +138% |
| Query latency | 50ms | 120ms | Acceptable |

---

## 8. Graph Layer

### 8.1 Graph Structure

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           NETWORKX DIGRAPH                                      │
│                                                                                 │
│   NODES (Knowledge Items)                                                       │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  Node ID: knowledge_item.id                                             │   │
│   │  Attributes:                                                            │   │
│   │    • type: knowledge_type                                               │   │
│   │    • title: item title                                                  │   │
│   │    • summary: item summary                                              │   │
│   │    • tags: [tag1, tag2, ...]                                           │   │
│   │    • category_id: category reference                                    │   │
│   │    • visibility: access level                                           │   │
│   │    • embedding: vector (for similarity computation)                     │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│   EDGES (3 Sources)                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  1. EXPLICIT (from knowledge_relationships table)                       │   │
│   │     • type: relationship_type (related, parent, implements, etc.)       │   │
│   │     • weight: explicit weight * 1.0                                     │   │
│   │     • source: 'explicit'                                                │   │
│   │     • Highest trust/weight                                              │   │
│   ├─────────────────────────────────────────────────────────────────────────┤   │
│   │  2. TAG-BASED (implicit, computed on load)                              │   │
│   │     • type: 'shared_tag'                                                │   │
│   │     • weight: num_shared_tags * 0.5                                     │   │
│   │     • shared_tags: [tag1, tag2, ...]                                   │   │
│   │     • source: 'tag'                                                     │   │
│   │     • Created when items share tags                                     │   │
│   │     • Skip if >50 items share same tag (too common)                    │   │
│   ├─────────────────────────────────────────────────────────────────────────┤   │
│   │  3. SIMILARITY-BASED (implicit, computed on load)                       │   │
│   │     • type: 'similar'                                                   │   │
│   │     • weight: similarity_score * 0.3                                    │   │
│   │     • similarity: cosine similarity value                               │   │
│   │     • source: 'embedding'                                               │   │
│   │     • Created when embedding similarity > 0.75 threshold                │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Graph Operations

| Operation | Method | Use Case |
|-----------|--------|----------|
| **Load** | Full load from DB | Startup, periodic refresh |
| **Update** | Event-driven incremental | Real-time sync |
| **Neighbors** | BFS within N hops | Context expansion |
| **Path** | Shortest path | Explain connections |
| **Subgraph** | Filter by tags/types | Focused queries |

### 8.3 Real-Time Graph Updates

```
┌──────────────────┐    Trigger    ┌──────────────────┐
│ knowledge_items  │──────────────▶│ graph_events     │
│ (INSERT/UPDATE)  │               │ (node_created,   │
└──────────────────┘               │  node_updated)   │
                                   └────────┬─────────┘
                                            │
┌──────────────────┐    Trigger    ┌────────┴─────────┐
│ knowledge_       │──────────────▶│ graph_events     │
│ relationships    │               │ (edge_created,   │
│ (INSERT/DELETE)  │               │  edge_deleted)   │
└──────────────────┘               └────────┬─────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │ Event Processor  │
                                   │ (polling loop)   │
                                   │ • Poll every 1s  │
                                   │ • Batch process  │
                                   │ • Mark processed │
                                   └────────┬─────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │ NetworkX Graph   │
                                   │ • Add/update node│
                                   │ • Add/remove edge│
                                   │ • Rebuild tag    │
                                   │   edges for node │
                                   └──────────────────┘
```

**Latency**: DB change → Graph updated in <5 seconds

### 8.4 Graph-Enhanced Retrieval Flow

```
Query: "Can I approve a $15K laptop order from Dell?"
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│  STEP 1: HYBRID SEARCH (Entry Points)                         │
│                                                               │
│  Find top-3 knowledge items matching query                    │
│  Filter: type IN ['faq', 'troubleshooting']                  │
│                                                               │
│  Results:                                                     │
│  • [FAQ] "How to approve large purchase orders" (score: 0.85)│
│  • [FAQ] "Laptop procurement process" (score: 0.72)          │
└───────────────────────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│  STEP 2: GRAPH EXPANSION                                      │
│                                                               │
│  For each entry point, traverse graph up to 2 hops           │
│  Filter: type IN ['business_rule', 'policy', 'context',      │
│                   'permission', 'procedure']                  │
│  Filter: tags overlap with query-relevant tags                │
│                                                               │
│  From "How to approve large purchase orders":                 │
│  • Hop 1: [Rule] "PO >$10K needs VP approval" (explicit)     │
│  • Hop 1: [Permission] "Buyer role limits" (explicit)        │
│  • Hop 1: [Context] "Dell - preferred vendor" (tag: vendor)  │
│  • Hop 2: [Policy] "Procurement Policy" (via Rule)           │
└───────────────────────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│  STEP 3: SCORE & RANK CONTEXT                                 │
│                                                               │
│  Score = edge_weight / (distance + 1)                         │
│                                                               │
│  Ranked context:                                              │
│  1. [Rule] "PO >$10K needs VP approval" (score: 0.50)        │
│  2. [Permission] "Buyer role limits" (score: 0.50)           │
│  3. [Context] "Dell - preferred vendor" (score: 0.25)        │
│  4. [Policy] "Procurement Policy" (score: 0.17)              │
└───────────────────────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│  STEP 4: RETURN STRUCTURED RESULT                             │
│                                                               │
│  {                                                            │
│    "entry_points": [                                          │
│      {"id": 101, "type": "faq", "title": "How to..."}        │
│    ],                                                         │
│    "context": [                                               │
│      {"id": 205, "type": "business_rule", "title": "PO>10K"},│
│      {"id": 301, "type": "permission", "title": "Buyer..."},  │
│      {"id": 410, "type": "context", "title": "Dell..."},     │
│      {"id": 502, "type": "policy", "title": "Procurement..."}│
│    ],                                                         │
│    "graph_stats": {"nodes_explored": 5, "max_hops": 2}       │
│  }                                                            │
└───────────────────────────────────────────────────────────────┘
```

---

## 9. Pipeline Design

### 9.1 Ticket-to-Knowledge Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         TICKET INGESTION                                        │
│                                                                                 │
│  Source: ClickHouse (ticketing.tickets)                                        │
│  Filter: status IN ('Closed', 'Resolved'), body >= 30 chars                    │
└────────────────────────────────────────────┬────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: FIND SIMILAR KNOWLEDGE                                                 │
│                                                                                 │
│  • Search knowledge_items by embedding similarity                              │
│  • Search knowledge_variants by embedding similarity                           │
│  • Combine and deduplicate by knowledge_item_id                                │
│  • Return top match with similarity score                                       │
└────────────────────────────────────────────┬────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: DECISION LOGIC                                                         │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  IF similarity >= 0.95:                                                 │    │
│  │      → SKIP (exact duplicate)                                           │    │
│  │                                                                         │    │
│  │  ELIF similarity >= 0.85:                                               │    │
│  │      → Analyze if ticket adds new information to answer                 │    │
│  │      → IF new info: MERGE (update answer, add variant)                 │    │
│  │      → ELSE: ADD_VARIANT (just add question variant)                   │    │
│  │                                                                         │    │
│  │  ELIF similarity >= 0.70:                                               │    │
│  │      → LLM decides: MERGE or NEW                                       │    │
│  │                                                                         │    │
│  │  ELSE:                                                                  │    │
│  │      → NEW (create new knowledge item)                                  │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────┬────────────────────────────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
         ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
         │    ADD_VARIANT   │    │      MERGE       │    │       NEW        │
         │                  │    │                  │    │                  │
         │ Direct insert to │    │ Create staging   │    │ Create staging   │
         │ knowledge_       │    │ entry for review │    │ entry for review │
         │ variants table   │    │                  │    │                  │
         │                  │    │ Also add variant │    │ Detect knowledge │
         │ No review needed │    │ directly         │    │ type via LLM     │
         └──────────────────┘    └──────────────────┘    └──────────────────┘
                    │                        │                        │
                    │                        ▼                        ▼
                    │            ┌──────────────────────────────────────────┐
                    │            │           HUMAN REVIEW                   │
                    │            │                                          │
                    │            │  • Review suggested changes              │
                    │            │  • Approve / Reject / Edit               │
                    │            │  • On approve: sync to knowledge_items  │
                    │            └──────────────────────────────────────────┘
                    │                                     │
                    └─────────────────┬───────────────────┘
                                      │
                                      ▼
                           ┌──────────────────┐
                           │  GRAPH EVENTS    │
                           │                  │
                           │  Triggers fire   │
                           │  automatically   │
                           └──────────────────┘
```

### 9.2 Pipeline Stats

```python
@dataclass
class PipelineStats:
    processed: int = 0          # Total tickets processed
    staged_new: int = 0         # New items pending review
    staged_merge: int = 0       # Merges pending review
    variants_added: int = 0     # Variants added directly
    skipped_prefilter: int = 0  # Failed pre-filter
    skipped_duplicate: int = 0  # Exact duplicates
    skipped_unsuitable: int = 0 # LLM rejected
```

---

## 10. API Design

### 10.1 Endpoint Summary

#### Knowledge Items

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/knowledge` | List items (paginated, filtered) |
| `GET` | `/knowledge/{id}` | Get item with variants, relationships |
| `POST` | `/knowledge` | Create item |
| `PUT` | `/knowledge/{id}` | Update item |
| `DELETE` | `/knowledge/{id}` | Soft delete item |

#### Variants

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/knowledge/{id}/variants` | List variants |
| `POST` | `/knowledge/{id}/variants` | Add variant |
| `DELETE` | `/knowledge/variants/{id}` | Delete variant |

#### Relationships

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/knowledge/{id}/relationships` | Get relationships |
| `POST` | `/knowledge/{id}/relationships` | Add relationship |
| `DELETE` | `/knowledge/relationships/{id}` | Remove relationship |

#### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/knowledge/search` | Hybrid search |
| `POST` | `/knowledge/search/context` | Graph-enhanced search |

#### Graph

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/knowledge/graph/stats` | Graph statistics |
| `GET` | `/knowledge/{id}/graph/neighbors` | Get neighbors |
| `GET` | `/knowledge/graph/path` | Find path between items |
| `POST` | `/knowledge/graph/reload` | Force full reload |

#### Categories

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/knowledge/categories` | List categories (tree) |
| `POST` | `/knowledge/categories` | Create category |
| `PUT` | `/knowledge/categories/{id}` | Update category |
| `DELETE` | `/knowledge/categories/{id}` | Delete category |

#### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/knowledge/stats` | Overall hit statistics |
| `GET` | `/knowledge/{id}/stats` | Item-specific stats |
| `GET` | `/knowledge/{id}/versions` | Version history |
| `POST` | `/knowledge/{id}/rollback/{version}` | Rollback to version |

### 10.2 Key Request/Response Models

#### Search Request

```json
POST /knowledge/search/context
{
  "query": "approve large purchase order",
  "entry_types": ["faq", "troubleshooting"],
  "entry_limit": 3,
  "expand_graph": true,
  "context_types": ["business_rule", "policy", "permission", "context"],
  "max_hops": 2,
  "context_limit": 5,
  "filter_tags": ["purchasing"],
  "visibility": "internal"
}
```

#### Search Response

```json
{
  "entry_points": [
    {
      "id": 101,
      "knowledge_type": "faq",
      "title": "How to approve large purchase orders",
      "summary": "Process for approving POs above threshold...",
      "content": {"question": "...", "answer": "..."},
      "tags": ["purchasing", "approval"],
      "hybrid_score": 0.85,
      "match_sources": ["item_bm25", "item_vector"]
    }
  ],
  "context": [
    {
      "id": 205,
      "type": "business_rule",
      "title": "PO >$10K requires VP approval",
      "summary": "Orders exceeding $10,000 require...",
      "content": {"condition": "...", "action": "..."},
      "score": 0.50,
      "distance": 1,
      "edge_type": "governs",
      "from_entry": 101
    },
    {
      "id": 410,
      "type": "context",
      "title": "Dell Technologies - Preferred Vendor",
      "summary": "Primary IT hardware supplier...",
      "content": {"entity_type": "vendor", ...},
      "score": 0.25,
      "distance": 1,
      "edge_type": "shared_tag",
      "from_entry": 101
    }
  ],
  "graph_stats": {
    "nodes_explored": 5,
    "max_hops_used": 2
  }
}
```

---

## 11. Implementation Roadmap

### Phase 1: Core Knowledge Base (2 weeks)

| Week | Tasks |
|------|-------|
| **Week 1** | Schema creation, hybrid search function, backward compatibility view |
| **Week 2** | Pipeline updates, CRUD APIs, basic admin UI support |

**Deliverables:**
- All core tables created
- Hybrid search working
- Pipeline handles all knowledge types
- Existing FAQ integrations unchanged

### Phase 2: Graph Layer (1.5 weeks)

| Week | Tasks |
|------|-------|
| **Week 3** | Graph service, full load, neighbor queries |
| **Week 4 (half)** | Graph-enhanced retrieval, graph APIs |

**Deliverables:**
- NetworkX graph loads from DB
- Tag and similarity edges computed
- Graph-enhanced search available

### Phase 3: Real-Time Updates (1 week)

| Week | Tasks |
|------|-------|
| **Week 4 (half)** | Event triggers, event processor |
| **Week 5** | Testing, optimization, monitoring |

**Deliverables:**
- Graph updates within 5s of DB change
- Event processor running reliably
- Monitoring in place

### Phase 4: Advanced Features (Future)

| Feature | Effort |
|---------|--------|
| Graph analytics | 2 days |
| Path explanations | 1 day |
| Access control | 3 days |
| Admin UI enhancements | 3 days |

---

## 12. Operational Considerations

### 12.1 Maintenance Jobs

| Job | Schedule | Purpose |
|-----|----------|---------|
| Version cleanup | Daily | Delete versions > 90 days |
| Event cleanup | Daily | Delete processed events > 7 days |
| Graph full reload | Weekly | Ensure consistency |
| Hit aggregation | Weekly | Archive old hit data (optional) |

### 12.2 Monitoring

| Metric | Alert Threshold |
|--------|-----------------|
| Graph event processing lag | > 1000 unprocessed events |
| Search latency (p99) | > 500ms |
| Graph node count | Unexpected drop > 10% |
| Event processor errors | Any errors |

### 12.3 Configuration

```yaml
knowledge_graph:
  enabled: true
  tag_edges: true
  similarity_edges: true
  similarity_threshold: 0.75
  event_poll_interval: 1.0
  max_tag_cooccurrence: 50

knowledge_search:
  bm25_weight: 0.4
  vector_weight: 0.6
  default_limit: 10

knowledge_maintenance:
  version_retention_days: 90
  event_retention_days: 7
```

### 12.4 Scaling Considerations

| Scale | Approach |
|-------|----------|
| <100K items | Single NetworkX graph, full in-memory |
| 100K-1M items | Partition by category, load on demand |
| >1M items | Consider Neo4j or similar graph DB |

Current design targets <100K items, which is typical for enterprise knowledge bases.

---

## 13. Success Metrics

### 13.1 Search Quality

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| NDCG@10 | 0.72 | 0.85+ | Evaluation dataset |
| Exact term recall | 40% | 95% | Keyword queries |
| Context relevance | N/A | 80%+ | User feedback |

### 13.2 Operational

| Metric | Target | Measurement |
|--------|--------|-------------|
| Search latency (p99) | <300ms | APM |
| Graph update latency | <5s | Event timestamps |
| System uptime | 99.9% | Monitoring |

### 13.3 Business

| Metric | Target | Measurement |
|--------|--------|-------------|
| Agent answer quality | +20% | User ratings |
| Duplicate knowledge rate | <5% | Pipeline stats |
| Knowledge utilization | 80% | Hit tracking |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **BM25** | Best Match 25 - probabilistic ranking for full-text search |
| **RRF** | Reciprocal Rank Fusion - algorithm to combine ranked lists |
| **HNSW** | Hierarchical Navigable Small World - approximate nearest neighbor index |
| **pgvector** | PostgreSQL extension for vector similarity search |
| **NetworkX** | Python library for graph analysis |
| **Knowledge Item** | Single piece of knowledge (FAQ, policy, rule, etc.) |
| **Variant** | Alternative phrasing that maps to same knowledge item |
| **Explicit Relationship** | Human-defined or explicitly created connection |
| **Implicit Relationship** | Auto-computed connection (tag or similarity based) |

---

## Appendix B: References

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [PostgreSQL Full-Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [NetworkX Documentation](https://networkx.org/documentation/stable/)
- [Reciprocal Rank Fusion Paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)
- [Hybrid Search Best Practices](https://supabase.com/docs/guides/ai/hybrid-search)

---

## Appendix C: Migration Notes

### From `purchasing_faq` to `knowledge_items`

Since this is a new feature, no data migration is required. The backward compatibility view ensures existing integrations continue to work:

```sql
CREATE VIEW agent.purchasing_faq AS
SELECT 
  id,
  content->>'question' AS question,
  content->>'answer' AS answer,
  tags,
  embedding,
  metadata_,
  created_by,
  created_at,
  updated_by,
  updated_at,
  is_deleted
FROM agent.knowledge_items
WHERE knowledge_type = 'faq'
  AND is_deleted = FALSE;
```

Existing code reading from `purchasing_faq` will continue to work unchanged.
