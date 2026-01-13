# FAQ System Enhancement Plan

## Overview

This document outlines the implementation plan for enhancing the FAQ/Knowledge Base system with hybrid search, question variants, usage tracking, versioning, and an improved ticket-to-FAQ pipeline.

---

## 1. Summary of Changes

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| **Hybrid Search** | Add BM25 full-text search alongside vector similarity | Critical |
| **Question Variants** | Support multiple question phrasings per FAQ (1:N) | Critical |
| **Hit Tracking** | Track which FAQs are retrieved by the agent | High |
| **Version History** | Track FAQ changes with time-based expiration | Medium |
| **FAQ Relationships** | Link related FAQs (auto + manual) | Medium |
| **Enhanced Pipeline** | Variant-aware ticket processing with MERGE action | Critical |

---

## 2. Database Schema Changes

### 2.1 Modify Existing Table: `agent.purchasing_faq`

```sql
-- Add full-text search vector column
ALTER TABLE agent.purchasing_faq 
ADD COLUMN search_vector tsvector 
GENERATED ALWAYS AS (
  setweight(to_tsvector('english', coalesce(question, '')), 'A') ||
  setweight(to_tsvector('english', coalesce(answer, '')), 'B')
) STORED;

-- Create GIN index for full-text search
CREATE INDEX idx_purchasing_faq_fts ON agent.purchasing_faq USING gin(search_vector);

-- Ensure HNSW index exists for vector search (if not already)
CREATE INDEX IF NOT EXISTS idx_purchasing_faq_embedding_hnsw 
ON agent.purchasing_faq USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);
```

### 2.2 New Table: `agent.faq_question_variants`

```sql
CREATE TABLE agent.faq_question_variants (
  id SERIAL PRIMARY KEY,
  faq_id INT NOT NULL REFERENCES agent.purchasing_faq(id) ON DELETE CASCADE,
  variant_text TEXT NOT NULL,
  embedding vector(1024),
  source VARCHAR(30) DEFAULT 'manual',  -- 'manual', 'ticket_pipeline', 'llm_generated'
  source_ticket_id VARCHAR(50),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by VARCHAR(100)
);

-- Indexes
CREATE INDEX idx_faq_variants_faq_id ON agent.faq_question_variants(faq_id);
CREATE INDEX idx_faq_variants_embedding ON agent.faq_question_variants 
  USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_faq_variants_fts ON agent.faq_question_variants 
  USING gin(to_tsvector('english', variant_text));
```

### 2.3 New Table: `agent.faq_hits`

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

-- Indexes
CREATE INDEX idx_faq_hits_faq_id ON agent.faq_hits(faq_id);
CREATE INDEX idx_faq_hits_time ON agent.faq_hits(hit_at);
```

### 2.4 New Table: `agent.faq_versions`

```sql
CREATE TABLE agent.faq_versions (
  id SERIAL PRIMARY KEY,
  faq_id INT REFERENCES agent.purchasing_faq(id) ON DELETE CASCADE,
  version_number INT NOT NULL,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  tags TEXT[],
  change_type VARCHAR(20),  -- 'create', 'update', 'merge', 'rollback'
  change_reason TEXT,
  changed_by VARCHAR(100),
  changed_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(faq_id, version_number)
);

-- Indexes
CREATE INDEX idx_faq_versions_faq_id ON agent.faq_versions(faq_id);
CREATE INDEX idx_faq_versions_changed_at ON agent.faq_versions(changed_at);
```

**Version Trigger:**

```sql
CREATE OR REPLACE FUNCTION create_faq_version()
RETURNS TRIGGER AS $$
BEGIN
  -- Only version if question or answer actually changed
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

**Version Cleanup Cron (90 days):**

```sql
-- Run daily via cron/scheduler
DELETE FROM agent.faq_versions 
WHERE changed_at < NOW() - INTERVAL '90 days';
```

### 2.5 New Table: `agent.faq_relationships`

```sql
CREATE TABLE agent.faq_relationships (
  id SERIAL PRIMARY KEY,
  source_faq_id INT REFERENCES agent.purchasing_faq(id) ON DELETE CASCADE,
  target_faq_id INT REFERENCES agent.purchasing_faq(id) ON DELETE CASCADE,
  relationship_type VARCHAR(20) NOT NULL,  -- 'related', 'parent', 'child', 'see_also'
  is_auto_generated BOOLEAN DEFAULT FALSE,
  created_by VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(source_faq_id, target_faq_id),
  CHECK(source_faq_id != target_faq_id)
);

-- Indexes
CREATE INDEX idx_faq_relationships_source ON agent.faq_relationships(source_faq_id);
CREATE INDEX idx_faq_relationships_target ON agent.faq_relationships(target_faq_id);
```

### 2.6 New View: `agent.faq_hit_stats`

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

## 3. Hybrid Search Implementation

### 3.1 Search Function

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
-- BM25 full-text search on canonical questions
text_search AS (
  SELECT f.id, f.question, f.answer, f.tags,
         ROW_NUMBER() OVER (ORDER BY ts_rank_cd(f.search_vector, query) DESC) AS rank,
         'canonical_bm25'::TEXT AS match_type
  FROM agent.purchasing_faq f, plainto_tsquery('english', query_text) query
  WHERE f.search_vector @@ query AND f.is_deleted = FALSE
  LIMIT 20
),
-- BM25 on variants
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
-- Combine all sources with RRF (k=60)
all_results AS (
  SELECT id, question, answer, tags, rank, match_type FROM text_search
  UNION ALL
  SELECT id, question, answer, tags, rank, match_type FROM variant_text_search
  UNION ALL
  SELECT id, question, answer, tags, rank, match_type FROM vector_search
  UNION ALL
  SELECT id, question, answer, tags, rank, match_type FROM variant_vector_search
),
-- Aggregate RRF scores per FAQ
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

---

## 4. Pipeline Logic Changes

### 4.1 New Action Types

```python
class AnalysisAction(str, Enum):
    SKIP = "skip"              # Exact duplicate, do nothing
    ADD_VARIANT = "add_variant" # Add question phrasing only (direct, no staging)
    MERGE = "merge"            # Update existing FAQ answer (staging for review)
    NEW = "new"                # Create new FAQ (staging for review)
```

### 4.2 Updated Similarity Thresholds

```python
SIMILARITY_SKIP_THRESHOLD = 0.95      # Exact duplicate
SIMILARITY_VARIANT_THRESHOLD = 0.85   # Same question, check if answer adds value
SIMILARITY_MERGE_THRESHOLD = 0.70     # Related, might merge
```

### 4.3 Decision Flow

```
Ticket Arrives
     │
     ▼
Find similar FAQs + Variants
     │
     ▼
┌────────────────────────────────────────────┐
│              Similarity Score              │
├──────────┬──────────┬──────────┬───────────┤
│  ≥0.95   │  ≥0.85   │  ≥0.70   │   <0.70   │
│  SKIP    │  Answer  │   LLM    │    NEW    │
│          │  check   │  decides │           │
│          │    │     │          │           │
│          │    ▼     │          │           │
│          │ New info?│          │           │
│          │ Y    N   │          │           │
│          │ │    │   │          │           │
│          │ ▼    ▼   │          │           │
│          │MERGE ADD │          │           │
│          │     VAR  │          │           │
└──────────┴──────────┴──────────┴───────────┘
```

### 4.4 Key Pipeline Methods

**Find Similar (includes variants):**
- Search both `purchasing_faq` and `faq_question_variants` tables
- Return best match per FAQ (deduplicate by faq_id)

**Analyze Answer Difference:**
- LLM compares ticket resolution with existing FAQ answer
- Returns: `adds_new_info`, `suggested_answer`, `confidence`

**Process Result:**
- `SKIP`: Increment stats, do nothing
- `ADD_VARIANT`: Insert into `faq_question_variants` directly (no review)
- `MERGE`: Create staging entry + add variant
- `NEW`: Create staging entry

### 4.5 Updated Stats

```python
@dataclass
class PipelineStats:
    processed: int = 0
    staged_new: int = 0          # New FAQs pending review
    staged_merge: int = 0        # Answer updates pending review
    variants_added: int = 0      # Question variants added (no review)
    skipped_prefilter: int = 0
    skipped_duplicate: int = 0
    skipped_unsuitable: int = 0
```

---

## 5. Service Layer Changes

### 5.1 PurchasingKnowledgeRetriever

- Update `retrieve()` to use `search_faq_hybrid()` function
- Add hit tracking after retrieval
- Return `matched_variant_id` when matched via variant

### 5.2 TicketToKBPipeline

- Update `find_similar_faqs()` to search variants
- Add `_analyze_answer_difference()` method
- Handle `ADD_VARIANT` action (direct insert, no staging)
- Update `MERGE` to also add variant when applicable

### 5.3 TicketingFAQService

- Add `list_variants()` method
- Add `add_variant()` method
- Add `delete_variant()` method
- Update `review_faq()` to handle variants on MERGE approval

### 5.4 New: FAQRelationshipService

- `get_related_faqs(faq_id)` - get related FAQs
- `add_relationship(source_id, target_id, type)` - admin adds relationship
- `remove_relationship(id)` - admin removes relationship
- `refresh_auto_relationships(faq_id)` - recompute auto-generated relationships

---

## 6. API Endpoint Changes

### 6.1 New Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/faq/{id}/variants` | List variants for a FAQ |
| POST | `/faq/{id}/variants` | Add variant to a FAQ |
| DELETE | `/faq/variants/{variant_id}` | Delete a variant |
| GET | `/faq/{id}/related` | Get related FAQs |
| POST | `/faq/{id}/related` | Add relationship |
| DELETE | `/faq/relationships/{rel_id}` | Remove relationship |
| GET | `/faq/{id}/versions` | Get version history |
| POST | `/faq/{id}/rollback/{version}` | Rollback to version |
| GET | `/faq/stats` | Get hit statistics |

### 6.2 Updated Response Models

```python
class FAQResponse(BaseModel):
    id: int
    question: str
    answer: str
    tags: List[str]
    variants: List[VariantResponse]  # NEW
    related_faqs: List[RelatedFAQResponse]  # NEW
    hit_count: int  # NEW
    
class VariantResponse(BaseModel):
    id: int
    variant_text: str
    source: str
    created_at: datetime

class RelatedFAQResponse(BaseModel):
    id: int
    question: str
    relationship_type: str
    is_auto_generated: bool
```

---

## 7. Implementation Phases

### Phase 1: Hybrid Search (3 days)
- [ ] Add `search_vector` column to `purchasing_faq`
- [ ] Create `search_faq_hybrid()` function
- [ ] Update `PurchasingKnowledgeRetriever` to use hybrid search
- [ ] Test search quality improvement

### Phase 2: Question Variants (4 days)
- [ ] Create `faq_question_variants` table
- [ ] Update pipeline to search variants
- [ ] Add `ADD_VARIANT` action handling
- [ ] Update `MERGE` to also add variants
- [ ] Add variant management API endpoints
- [ ] Add variant management UI support

### Phase 3: Hit Tracking (2 days)
- [ ] Create `faq_hits` table
- [ ] Update retriever to record hits
- [ ] Create `faq_hit_stats` view
- [ ] Add stats API endpoint

### Phase 4: Version History (2 days)
- [ ] Create `faq_versions` table
- [ ] Create version trigger
- [ ] Add version cleanup cron job (90 days)
- [ ] Add version history API endpoints
- [ ] Add rollback functionality

### Phase 5: FAQ Relationships (3 days)
- [ ] Create `faq_relationships` table
- [ ] Add auto-relationship generation
- [ ] Add relationship management API endpoints
- [ ] Add relationship management UI support

**Total Estimated Effort: 14 days**

---

## 8. Testing Checklist

### Search Quality
- [ ] Exact keyword matches return correct FAQs
- [ ] Semantic queries return relevant FAQs
- [ ] Variants are matched correctly
- [ ] RRF scoring produces sensible rankings

### Pipeline Logic
- [ ] High similarity (≥0.95) → SKIP
- [ ] Similar question, same answer (≥0.85) → ADD_VARIANT
- [ ] Similar question, new answer info (≥0.85) → MERGE + ADD_VARIANT
- [ ] Medium similarity (≥0.70) → LLM decides MERGE or NEW
- [ ] Low similarity (<0.70) → NEW

### Data Integrity
- [ ] Variants cascade delete with FAQ
- [ ] Versions are created on update
- [ ] Old versions are cleaned up after 90 days
- [ ] Relationships don't allow self-reference

---

## 9. Rollback Plan

If issues arise:

1. **Hybrid Search**: Revert retriever to vector-only search (column remains, just unused)
2. **Variants**: Pipeline falls back to canonical-only matching
3. **Hits**: Disable tracking in retriever (table remains for later)
4. **Versions**: Drop trigger (table remains as historical record)
5. **Relationships**: Disable auto-generation (manual relationships remain)

All changes are additive - no existing functionality is removed.
