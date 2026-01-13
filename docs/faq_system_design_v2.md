# FAQ System Design v2.0

> **Document Type**: Technical Design Document  
> **Status**: Proposed  
> **Author**: Engineering Team  
> **Last Updated**: January 2025

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Motivation](#2-background--motivation)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Current State Analysis](#4-current-state-analysis)
5. [Proposed Design](#5-proposed-design)
6. [Architecture Overview](#6-architecture-overview)
7. [Database Schema](#7-database-schema)
8. [Component Design](#8-component-design)
9. [API Specification](#9-api-specification)
10. [Implementation Plan](#10-implementation-plan)
11. [Risks & Mitigations](#11-risks--mitigations)
12. [Success Metrics](#12-success-metrics)

---

## 1. Executive Summary

This document proposes enhancements to the FAQ/Knowledge Base system to address key limitations in search capabilities, question handling, and the ticket-to-FAQ pipeline. The design introduces:

- **Hybrid Search**: Combining BM25 keyword search with vector similarity for better retrieval
- **Question Variants**: Supporting multiple question phrasings per FAQ (1:N relationship)
- **Enhanced Pipeline**: Smarter ticket processing that distinguishes between new FAQs, answer updates, and question variants
- **Usage Analytics**: Tracking FAQ retrieval patterns to measure effectiveness
- **Version History**: Maintaining audit trail of FAQ changes with automatic expiration
- **FAQ Relationships**: Linking related FAQs for better navigation and management

**Expected Outcome**: Improved FAQ retrieval accuracy (estimated +18% NDCG improvement), reduced duplicate FAQ creation, and better visibility into knowledge base effectiveness.

---

## 2. Background & Motivation

### 2.1 Current Challenges

| Challenge | Impact | Example |
|-----------|--------|---------|
| **Keyword search gap** | Users can't find FAQs with exact terms | Searching "PO-12345" or "error E500" returns poor results |
| **Single question format** | Can't capture how users naturally ask | "How do I reset password?" vs "forgot login" vs "can't access account" all mean the same thing |
| **Basic ticket matching** | Pipeline creates duplicates or misses merge opportunities | Similar tickets create separate FAQs instead of enhancing existing ones |
| **No usage visibility** | Can't measure FAQ effectiveness | Unknown which FAQs are actually helping users |
| **No change history** | Can't track FAQ evolution or rollback mistakes | Accidental edits are unrecoverable |

### 2.2 Industry Context

Modern FAQ and knowledge base systems (Zendesk, Intercom, Azure QnA Maker) have evolved to include:

- **Hybrid search** combining semantic understanding with keyword matching
- **Question clustering** with canonical questions and variants
- **Usage analytics** for continuous improvement
- **Version control** for content management

Our current system uses vector-only search and 1:1 question-answer pairs, which is below industry standards for 2025.

### 2.3 Why Now?

- Agent framework integration requires high-quality FAQ retrieval
- Support ticket volume is increasing, making automated FAQ generation more valuable
- Current pipeline creates ~15% duplicate/near-duplicate FAQs (estimated from similarity analysis)

---

## 3. Goals & Non-Goals

### 3.1 Goals

| Goal | Success Criteria |
|------|-----------------|
| Improve search accuracy | +15-20% improvement in retrieval relevance |
| Support question variations | Users find FAQs regardless of phrasing |
| Reduce duplicate FAQs | <5% duplicate creation rate |
| Enable usage tracking | Know which FAQs are retrieved and how often |
| Maintain change history | 90-day version retention with rollback capability |
| Enable related FAQ discovery | Admins can link and users can navigate related FAQs |

### 3.2 Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| Ticket clustering | Current single-ticket analysis is sufficient; revisit when volume justifies |
| Multi-dimensional quality scoring | Simple LLM-based analysis is adequate for now |
| Fuzzy/typo matching | BM25 handles most cases; add later if analytics show need |
| A/B testing framework | Premature; need baseline analytics first |
| Public-facing SEO optimization | FAQs are internal agent knowledge base only |

---

## 4. Current State Analysis

### 4.1 Current Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   ClickHouse    │────▶│ Pipeline Job     │────▶│ Staging Table       │
│  (Raw Tickets)  │     │ (ticketing_kb_   │     │ (staging_purchasing_│
│                 │     │  pipeline_job)   │     │  faq)               │
└─────────────────┘     └────────┬─────────┘     └──────────┬──────────┘
                                 │                         │
                                 ▼                         ▼
                        ┌──────────────────┐     ┌─────────────────────┐
                        │ LLM Analysis     │     │  Human Review       │
                        │ (NEW/MERGE/SKIP) │     │  (approve/reject)   │
                        └────────┬─────────┘     └──────────┬──────────┘
                                 │                         │
                                 ▼                         ▼
                        ┌──────────────────┐     ┌─────────────────────┐
                        │ pgvector Search  │◀────│  Production Table   │
                        │ (vector only)    │     │  (purchasing_faq)   │
                        └────────┬─────────┘     └─────────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │ Agent Framework  │
                        │ KB Retriever     │
                        └──────────────────┘
```

### 4.2 Current Limitations

| Component | Limitation |
|-----------|------------|
| **Search** | Vector-only (pgvector cosine similarity) - misses exact keyword matches |
| **Schema** | Single `question` field per FAQ - no variant support |
| **Pipeline** | Binary similarity (0.95 threshold) - misses nuanced cases |
| **Analytics** | None - no visibility into FAQ usage |
| **History** | Audit fields only (`updated_at`, `updated_by`) - no content versioning |

### 4.3 Current Data Model

```sql
-- Existing production table
CREATE TABLE agent.purchasing_faq (
  id SERIAL PRIMARY KEY,
  question TEXT NOT NULL,      -- Single question only
  answer TEXT NOT NULL,
  tags TEXT[],
  embedding vector(1024),      -- Vector search only
  metadata_ JSONB,
  -- Audit fields from AuditMixin
  created_by VARCHAR(100),
  created_at TIMESTAMPTZ,
  updated_by VARCHAR(100),
  updated_at TIMESTAMPTZ,
  is_deleted BOOLEAN DEFAULT FALSE
);
```

---

## 5. Proposed Design

### 5.1 Design Principles

1. **Additive Changes**: All enhancements add to existing functionality; no breaking changes
2. **Minimal Complexity**: Choose simpler solutions that achieve 80% of the benefit
3. **Progressive Enhancement**: Features can be rolled out independently
4. **Backward Compatibility**: Existing integrations continue to work

### 5.2 Key Enhancements

#### Enhancement 1: Hybrid Search (BM25 + Vector)

**Problem**: Vector search misses exact keyword matches (product codes, error numbers, specific terms).

**Solution**: Add PostgreSQL full-text search alongside vector similarity, combine with Reciprocal Rank Fusion (RRF).

**Approach**:
- Add generated `tsvector` column to `purchasing_faq`
- Create hybrid search function using RRF algorithm
- Weight: 40% BM25 + 60% Vector (tunable)

**Expected Improvement**: +18% NDCG@10 based on industry benchmarks.

---

#### Enhancement 2: Question Variants (1:N Mapping)

**Problem**: Users ask the same question in different ways; single question field can't capture variations.

**Solution**: Separate table for question variants linked to canonical FAQ.

**Approach**:
- Create `faq_question_variants` table with embeddings
- Search both canonical questions AND variants
- Pipeline automatically adds variants when matching existing FAQ

**Benefits**:
- Better recall for natural language queries
- Automatic learning from user queries via pipeline
- Admin can curate variants manually

---

#### Enhancement 3: Enhanced Ticket Pipeline

**Problem**: Current pipeline has only three actions (NEW/MERGE/SKIP); misses the case where a ticket represents a new phrasing of an existing question without adding new answer content.

**Solution**: Add `ADD_VARIANT` action for high-similarity matches that don't add new answer information.

**Decision Flow**:

| Similarity | Answer Adds Info? | Action | Staging Required? |
|------------|-------------------|--------|-------------------|
| ≥0.95 | N/A | SKIP | No |
| ≥0.85 | No | ADD_VARIANT | No (direct insert) |
| ≥0.85 | Yes | MERGE | Yes |
| ≥0.70 | LLM decides | MERGE or NEW | Yes |
| <0.70 | N/A | NEW | Yes |

**Key Insight**: Variants go directly to production (low risk); answer changes require human review (higher risk).

---

#### Enhancement 4: Hit Tracking

**Problem**: No visibility into which FAQs are actually being retrieved and used.

**Solution**: Record retrieval events when agent fetches FAQs.

**Tracked Data**:
- Which FAQ was hit
- Which variant matched (if any)
- What query triggered the hit
- Similarity score
- Session context

**Use Cases**:
- Identify high-value FAQs
- Find unused FAQs for review/cleanup
- Measure search quality over time

---

#### Enhancement 5: Version History

**Problem**: No way to track FAQ changes or rollback mistakes.

**Solution**: Automatic versioning on content changes with time-based expiration.

**Approach**:
- Trigger creates version record before update
- Keep versions for 90 days (simple time-based cleanup)
- Admin can view history and rollback

---

#### Enhancement 6: FAQ Relationships

**Problem**: FAQs exist in isolation; no way to navigate related content.

**Solution**: Relationship table supporting both auto-generated and manual links.

**Relationship Types**:
- `related` - semantically similar FAQs
- `parent` / `child` - hierarchical relationship
- `see_also` - manual cross-reference

**Auto-Generation**: When FAQ is created/updated, compute top 3 similar FAQs and create `related` relationships (marked as `is_auto_generated = true`).

---

## 6. Architecture Overview

### 6.1 Updated Architecture Diagram

```
┌─────────────────┐     ┌──────────────────────────────────────────────────────┐
│   ClickHouse    │────▶│              ENHANCED PIPELINE                       │
│  (Raw Tickets)  │     │  ┌─────────────────────────────────────────────┐     │
└─────────────────┘     │  │  1. Find Similar (canonical + variants)     │     │
                        │  │  2. Analyze Answer Difference (LLM)         │     │
                        │  │  3. Decision: SKIP/ADD_VARIANT/MERGE/NEW    │     │
                        │  └─────────────────────────────────────────────┘     │
                        └──────────────┬───────────────────┬───────────────────┘
                                       │                   │
                        ┌──────────────┴───────┐   ┌───────┴───────────────┐
                        │  Direct Insert       │   │  Staging Table        │
                        │  (ADD_VARIANT only)  │   │  (MERGE/NEW)          │
                        │         │            │   │         │             │
                        │         ▼            │   │         ▼             │
                        │  faq_question_       │   │  Human Review         │
                        │  variants            │   │  (approve/reject)     │
                        └──────────┬───────────┘   └───────────┬───────────┘
                                   │                           │
                                   └─────────────┬─────────────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           PRODUCTION DATA                                    │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────────────┐  │
│  │ purchasing_faq  │  │ faq_question_    │  │ faq_relationships           │  │
│  │ + search_vector │◀▶│ variants         │  │ (auto + manual)             │  │
│  │ + embedding     │  │ + embedding      │  └─────────────────────────────┘  │
│  └────────┬────────┘  └──────────────────┘                                   │
│           │                                                                  │
│  ┌────────┴────────┐  ┌──────────────────┐                                   │
│  │ faq_versions    │  │ faq_hits         │                                   │
│  │ (90-day TTL)    │  │ (usage tracking) │                                   │
│  └─────────────────┘  └──────────────────┘                                   │
└──────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                        ┌──────────────────────────────────────────┐
                        │           HYBRID SEARCH                  │
                        │  ┌─────────────┐    ┌─────────────────┐  │
                        │  │ BM25 (FTS)  │ +  │ Vector (pgvector)│  │
                        │  │ Weight: 40% │    │ Weight: 60%     │  │
                        │  └─────────────┘    └─────────────────┘  │
                        │              │                           │
                        │              ▼                           │
                        │     Reciprocal Rank Fusion (RRF)         │
                        │              │                           │
                        │              ▼                           │
                        │        Hit Recording                     │
                        └──────────────┬───────────────────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────────────────────┐
                        │           AGENT FRAMEWORK                │
                        │      PurchasingKnowledgeRetriever        │
                        └──────────────────────────────────────────┘
```

### 6.2 Data Flow Summary

| Flow | Path | Staging? |
|------|------|----------|
| New FAQ | Ticket → Pipeline → Staging → Review → `purchasing_faq` | Yes |
| Answer Update | Ticket → Pipeline → Staging → Review → `purchasing_faq` update | Yes |
| Question Variant | Ticket → Pipeline → `faq_question_variants` | No |
| Search | Query → Hybrid Search → Hit Recording → Results | N/A |
| Version | `purchasing_faq` update → Trigger → `faq_versions` | Automatic |

---

## 7. Database Schema

### 7.1 Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌───────────────────┐       ┌────────────────────────┐                     │
│  │ purchasing_faq    │       │ faq_question_variants  │                     │
│  ├───────────────────┤       ├────────────────────────┤                     │
│  │ id (PK)           │──────<│ faq_id (FK)            │                     │
│  │ question          │   1:N │ id (PK)                │                     │
│  │ answer            │       │ variant_text           │                     │
│  │ tags[]            │       │ embedding              │                     │
│  │ embedding         │       │ source                 │                     │
│  │ search_vector     │       │ source_ticket_id       │                     │
│  │ metadata_         │       │ created_at             │                     │
│  │ created_at        │       │ created_by             │                     │
│  │ updated_at        │       └────────────────────────┘                     │
│  │ is_deleted        │                                                      │
│  └─────────┬─────────┘                                                      │
│            │                                                                │
│            │ 1:N                                                            │
│            ▼                                                                │
│  ┌───────────────────┐       ┌────────────────────────┐                     │
│  │ faq_versions      │       │ faq_hits               │                     │
│  ├───────────────────┤       ├────────────────────────┤                     │
│  │ id (PK)           │       │ id (PK)                │                     │
│  │ faq_id (FK)       │       │ faq_id (FK)            │◀──── purchasing_faq │
│  │ version_number    │       │ variant_id (FK)        │◀──── variants       │
│  │ question          │       │ query_text             │                     │
│  │ answer            │       │ similarity_score       │                     │
│  │ tags[]            │       │ session_id             │                     │
│  │ change_type       │       │ hit_at                 │                     │
│  │ change_reason     │       └────────────────────────┘                     │
│  │ changed_by        │                                                      │
│  │ changed_at        │                                                      │
│  └───────────────────┘                                                      │
│                                                                             │
│  ┌───────────────────────────────────────────────────┐                      │
│  │ faq_relationships                                 │                      │
│  ├───────────────────────────────────────────────────┤                      │
│  │ id (PK)                                           │                      │
│  │ source_faq_id (FK) ───────────────────────────────│◀──── purchasing_faq  │
│  │ target_faq_id (FK) ───────────────────────────────│◀──── purchasing_faq  │
│  │ relationship_type                                 │                      │
│  │ is_auto_generated                                 │                      │
│  │ created_by                                        │                      │
│  │ created_at                                        │                      │
│  └───────────────────────────────────────────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Table Definitions

#### 7.2.1 Modified: `agent.purchasing_faq`

```sql
-- Add full-text search column (generated)
ALTER TABLE agent.purchasing_faq 
ADD COLUMN search_vector tsvector 
GENERATED ALWAYS AS (
  setweight(to_tsvector('english', coalesce(question, '')), 'A') ||
  setweight(to_tsvector('english', coalesce(answer, '')), 'B')
) STORED;

-- Index for full-text search
CREATE INDEX idx_purchasing_faq_fts 
ON agent.purchasing_faq USING gin(search_vector);
```

#### 7.2.2 New: `agent.faq_question_variants`

```sql
CREATE TABLE agent.faq_question_variants (
  id SERIAL PRIMARY KEY,
  faq_id INT NOT NULL REFERENCES agent.purchasing_faq(id) ON DELETE CASCADE,
  variant_text TEXT NOT NULL,
  embedding vector(1024),
  source VARCHAR(30) DEFAULT 'manual',
  source_ticket_id VARCHAR(50),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by VARCHAR(100)
);

CREATE INDEX idx_faq_variants_faq_id 
ON agent.faq_question_variants(faq_id);

CREATE INDEX idx_faq_variants_embedding 
ON agent.faq_question_variants 
USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_faq_variants_fts 
ON agent.faq_question_variants 
USING gin(to_tsvector('english', variant_text));
```

#### 7.2.3 New: `agent.faq_hits`

```sql
CREATE TABLE agent.faq_hits (
  id SERIAL PRIMARY KEY,
  faq_id INT REFERENCES agent.purchasing_faq(id) ON DELETE CASCADE,
  variant_id INT REFERENCES agent.faq_question_variants(id) ON DELETE SET NULL,
  query_text TEXT,
  similarity_score FLOAT,
  session_id VARCHAR(100),
  hit_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_faq_hits_faq_id ON agent.faq_hits(faq_id);
CREATE INDEX idx_faq_hits_time ON agent.faq_hits(hit_at);
```

#### 7.2.4 New: `agent.faq_versions`

```sql
CREATE TABLE agent.faq_versions (
  id SERIAL PRIMARY KEY,
  faq_id INT REFERENCES agent.purchasing_faq(id) ON DELETE CASCADE,
  version_number INT NOT NULL,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  tags TEXT[],
  change_type VARCHAR(20),
  change_reason TEXT,
  changed_by VARCHAR(100),
  changed_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(faq_id, version_number)
);

CREATE INDEX idx_faq_versions_faq_id ON agent.faq_versions(faq_id);
CREATE INDEX idx_faq_versions_changed_at ON agent.faq_versions(changed_at);

-- Auto-versioning trigger
CREATE OR REPLACE FUNCTION create_faq_version()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.question IS DISTINCT FROM NEW.question 
     OR OLD.answer IS DISTINCT FROM NEW.answer 
     OR OLD.tags IS DISTINCT FROM NEW.tags THEN
    
    INSERT INTO agent.faq_versions (
      faq_id, version_number, question, answer, tags, 
      change_type, changed_by, changed_at
    )
    VALUES (
      OLD.id,
      COALESCE((SELECT MAX(version_number) FROM agent.faq_versions WHERE faq_id = OLD.id), 0) + 1,
      OLD.question,
      OLD.answer,
      OLD.tags,
      'update',
      NEW.updated_by,
      NOW()
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER faq_version_trigger
BEFORE UPDATE ON agent.purchasing_faq
FOR EACH ROW EXECUTE FUNCTION create_faq_version();
```

#### 7.2.5 New: `agent.faq_relationships`

```sql
CREATE TABLE agent.faq_relationships (
  id SERIAL PRIMARY KEY,
  source_faq_id INT REFERENCES agent.purchasing_faq(id) ON DELETE CASCADE,
  target_faq_id INT REFERENCES agent.purchasing_faq(id) ON DELETE CASCADE,
  relationship_type VARCHAR(20) NOT NULL,
  is_auto_generated BOOLEAN DEFAULT FALSE,
  created_by VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(source_faq_id, target_faq_id),
  CHECK(source_faq_id != target_faq_id)
);

CREATE INDEX idx_faq_relationships_source ON agent.faq_relationships(source_faq_id);
CREATE INDEX idx_faq_relationships_target ON agent.faq_relationships(target_faq_id);
```

#### 7.2.6 New View: `agent.faq_hit_stats`

```sql
CREATE VIEW agent.faq_hit_stats AS
SELECT 
  f.id,
  f.question,
  COUNT(h.id) AS total_hits,
  COUNT(DISTINCT h.session_id) AS unique_sessions,
  COUNT(DISTINCT DATE(h.hit_at)) AS days_with_hits,
  MAX(h.hit_at) AS last_hit_at,
  ROUND(AVG(h.similarity_score)::numeric, 3) AS avg_similarity
FROM agent.purchasing_faq f
LEFT JOIN agent.faq_hits h ON f.id = h.faq_id
WHERE f.is_deleted = FALSE
GROUP BY f.id, f.question;
```

---

## 8. Component Design

### 8.1 Hybrid Search Function

```sql
CREATE OR REPLACE FUNCTION agent.search_faq_hybrid(
  query_text TEXT,
  query_embedding vector(1024),
  result_limit INT DEFAULT 10,
  bm25_weight FLOAT DEFAULT 0.4,
  vector_weight FLOAT DEFAULT 0.6
)
RETURNS TABLE(
  id INT,
  question TEXT,
  answer TEXT,
  tags TEXT[],
  hybrid_score FLOAT,
  match_type TEXT
) AS $$
WITH 
-- BM25 search on canonical questions
text_search AS (
  SELECT f.id, f.question, f.answer, f.tags,
         ROW_NUMBER() OVER (ORDER BY ts_rank_cd(f.search_vector, query) DESC) AS rank,
         'canonical_bm25'::TEXT AS match_type
  FROM agent.purchasing_faq f, plainto_tsquery('english', query_text) query
  WHERE f.search_vector @@ query AND f.is_deleted = FALSE
  LIMIT 20
),
-- BM25 search on variants
variant_text_search AS (
  SELECT f.id, f.question, f.answer, f.tags,
         ROW_NUMBER() OVER (ORDER BY ts_rank_cd(to_tsvector('english', v.variant_text), query) DESC) AS rank,
         'variant_bm25'::TEXT AS match_type
  FROM agent.faq_question_variants v
  JOIN agent.purchasing_faq f ON v.faq_id = f.id
  CROSS JOIN plainto_tsquery('english', query_text) query
  WHERE to_tsvector('english', v.variant_text) @@ query AND f.is_deleted = FALSE
  LIMIT 20
),
-- Vector search on canonical questions
vector_search AS (
  SELECT f.id, f.question, f.answer, f.tags,
         ROW_NUMBER() OVER (ORDER BY f.embedding <=> query_embedding) AS rank,
         'canonical_vector'::TEXT AS match_type
  FROM agent.purchasing_faq f
  WHERE f.embedding IS NOT NULL AND f.is_deleted = FALSE
  ORDER BY f.embedding <=> query_embedding
  LIMIT 20
),
-- Vector search on variants
variant_vector_search AS (
  SELECT f.id, f.question, f.answer, f.tags,
         ROW_NUMBER() OVER (ORDER BY v.embedding <=> query_embedding) AS rank,
         'variant_vector'::TEXT AS match_type
  FROM agent.faq_question_variants v
  JOIN agent.purchasing_faq f ON v.faq_id = f.id
  WHERE v.embedding IS NOT NULL AND f.is_deleted = FALSE
  ORDER BY v.embedding <=> query_embedding
  LIMIT 20
),
-- Combine all with RRF
all_results AS (
  SELECT * FROM text_search
  UNION ALL SELECT * FROM variant_text_search
  UNION ALL SELECT * FROM vector_search
  UNION ALL SELECT * FROM variant_vector_search
),
rrf_scores AS (
  SELECT 
    id,
    MAX(question) AS question,
    MAX(answer) AS answer,
    MAX(tags) AS tags,
    SUM(
      CASE 
        WHEN match_type LIKE '%bm25' THEN bm25_weight / (60 + rank)
        ELSE vector_weight / (60 + rank)
      END
    ) AS hybrid_score,
    STRING_AGG(DISTINCT match_type, ',') AS match_type
  FROM all_results
  GROUP BY id
)
SELECT id, question, answer, tags, hybrid_score, match_type
FROM rrf_scores
ORDER BY hybrid_score DESC
LIMIT result_limit;
$$ LANGUAGE SQL;
```

### 8.2 Pipeline Decision Logic

```python
class AnalysisAction(str, Enum):
    SKIP = "skip"              # Exact duplicate
    ADD_VARIANT = "add_variant" # Add question variant only
    MERGE = "merge"            # Update existing FAQ answer
    NEW = "new"                # Create new FAQ

class TicketToKBPipeline:
    SIMILARITY_SKIP = 0.95
    SIMILARITY_VARIANT = 0.85
    SIMILARITY_MERGE = 0.70
    
    async def analyze_ticket(self, ticket: TicketData) -> AnalysisResult:
        # 1. Find similar FAQs (canonical + variants)
        similar = await self._find_similar_with_variants(ticket)
        
        if not similar:
            return AnalysisResult(action=AnalysisAction.NEW)
        
        top = similar[0]
        
        # 2. Exact duplicate → SKIP
        if top.similarity >= self.SIMILARITY_SKIP:
            return AnalysisResult(action=AnalysisAction.SKIP)
        
        # 3. High similarity → check if answer adds value
        if top.similarity >= self.SIMILARITY_VARIANT:
            answer_diff = await self._analyze_answer_difference(ticket, top)
            
            if answer_diff.adds_new_info:
                return AnalysisResult(
                    action=AnalysisAction.MERGE,
                    matched_faq_id=top.faq_id,
                    suggested_answer=answer_diff.suggested_answer,
                    also_add_variant=True,
                    variant_text=self._extract_question(ticket)
                )
            else:
                return AnalysisResult(
                    action=AnalysisAction.ADD_VARIANT,
                    matched_faq_id=top.faq_id,
                    variant_text=self._extract_question(ticket)
                )
        
        # 4. Medium similarity → LLM decides
        if top.similarity >= self.SIMILARITY_MERGE:
            return await self._llm_decide_merge_or_new(ticket, top)
        
        # 5. Low similarity → NEW
        return AnalysisResult(action=AnalysisAction.NEW)
```

### 8.3 Knowledge Retriever Update

```python
class PurchasingKnowledgeRetriever(KnowledgeRetriever):
    
    async def retrieve(
        self, 
        query: str, 
        top_k: int = 5,
        session_id: Optional[str] = None
    ) -> List[FAQResult]:
        # Generate embedding
        embedding = await self.embedding_client.embed(query)
        
        # Hybrid search
        results = await self.session.execute(
            text("SELECT * FROM agent.search_faq_hybrid(:query, :embedding, :limit)"),
            {"query": query, "embedding": embedding, "limit": top_k}
        )
        
        faqs = results.fetchall()
        
        # Record hits
        if session_id:
            await self._record_hits(query, faqs, session_id)
        
        return [self._to_faq_result(row) for row in faqs]
    
    async def _record_hits(self, query: str, faqs: List, session_id: str):
        for faq in faqs:
            await self.session.execute(
                insert(FAQHit).values(
                    faq_id=faq.id,
                    query_text=query,
                    similarity_score=faq.hybrid_score,
                    session_id=session_id
                )
            )
```

---

## 9. API Specification

### 9.1 New Endpoints

#### Variants

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/faq/{id}/variants` | List variants for FAQ |
| `POST` | `/faq/{id}/variants` | Add variant |
| `DELETE` | `/faq/variants/{variant_id}` | Delete variant |

#### Relationships

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/faq/{id}/related` | Get related FAQs |
| `POST` | `/faq/{id}/related` | Add relationship |
| `DELETE` | `/faq/relationships/{id}` | Remove relationship |

#### Versions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/faq/{id}/versions` | Get version history |
| `POST` | `/faq/{id}/rollback/{version}` | Rollback to version |

#### Stats

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/faq/stats` | Get hit statistics |
| `GET` | `/faq/{id}/stats` | Get stats for specific FAQ |

### 9.2 Response Models

```python
class FAQDetailResponse(BaseModel):
    id: int
    question: str
    answer: str
    tags: List[str]
    variants: List[VariantResponse]
    related_faqs: List[RelatedFAQResponse]
    stats: FAQStatsResponse
    created_at: datetime
    updated_at: Optional[datetime]

class VariantResponse(BaseModel):
    id: int
    variant_text: str
    source: str
    created_at: datetime
    created_by: Optional[str]

class RelatedFAQResponse(BaseModel):
    id: int
    question: str
    relationship_type: str
    is_auto_generated: bool

class FAQStatsResponse(BaseModel):
    total_hits: int
    unique_sessions: int
    last_hit_at: Optional[datetime]
    avg_similarity: Optional[float]
```

---

## 10. Implementation Plan

### Phase 1: Hybrid Search (3 days)

| Task | Owner | Status |
|------|-------|--------|
| Add `search_vector` column | Backend | Pending |
| Create `search_faq_hybrid` function | Backend | Pending |
| Update `PurchasingKnowledgeRetriever` | Backend | Pending |
| Test search quality | QA | Pending |

### Phase 2: Question Variants (4 days)

| Task | Owner | Status |
|------|-------|--------|
| Create `faq_question_variants` table | Backend | Pending |
| Update pipeline similarity search | Backend | Pending |
| Add `ADD_VARIANT` action handling | Backend | Pending |
| Variant management API endpoints | Backend | Pending |
| Admin UI for variants | Frontend | Pending |

### Phase 3: Hit Tracking (2 days)

| Task | Owner | Status |
|------|-------|--------|
| Create `faq_hits` table | Backend | Pending |
| Update retriever to record hits | Backend | Pending |
| Create stats view | Backend | Pending |
| Stats API endpoint | Backend | Pending |

### Phase 4: Version History (2 days)

| Task | Owner | Status |
|------|-------|--------|
| Create `faq_versions` table | Backend | Pending |
| Create versioning trigger | Backend | Pending |
| Add cleanup cron job | DevOps | Pending |
| Version history API | Backend | Pending |
| Rollback functionality | Backend | Pending |

### Phase 5: FAQ Relationships (3 days)

| Task | Owner | Status |
|------|-------|--------|
| Create `faq_relationships` table | Backend | Pending |
| Auto-relationship generation | Backend | Pending |
| Relationship management API | Backend | Pending |
| Admin UI for relationships | Frontend | Pending |

**Total Estimated Effort: 14 days**

---

## 11. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Search quality regression | High | Low | A/B test before full rollout; keep vector-only fallback |
| Pipeline creates too many variants | Medium | Medium | Add rate limiting; monitor variant growth |
| Version table grows too large | Low | Low | 90-day cleanup ensures bounded growth |
| Performance degradation from hybrid search | Medium | Low | Proper indexing; monitor query latency |

---

## 12. Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Search NDCG@10 | ~0.72 (est.) | 0.85+ | Evaluation dataset |
| Duplicate FAQ rate | ~15% (est.) | <5% | Pipeline stats |
| Variant coverage | 0 | 3+ variants/FAQ avg | Database query |
| FAQ hit visibility | None | 100% | Hit tracking coverage |
| Version retention | None | 90 days | Cron job verification |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **BM25** | Best Match 25 - probabilistic ranking function for full-text search |
| **RRF** | Reciprocal Rank Fusion - algorithm to combine multiple ranked lists |
| **Canonical Question** | The primary/official phrasing of a FAQ question |
| **Variant** | Alternative phrasing of a question that maps to the same FAQ |
| **HNSW** | Hierarchical Navigable Small World - approximate nearest neighbor index |
| **pgvector** | PostgreSQL extension for vector similarity search |

---

## Appendix B: References

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [PostgreSQL Full-Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [Reciprocal Rank Fusion Paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)
- [Hybrid Search Best Practices](https://supabase.com/docs/guides/ai/hybrid-search)
