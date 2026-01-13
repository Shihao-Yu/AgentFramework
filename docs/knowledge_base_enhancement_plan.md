# Knowledge Base System Enhancement Plan

## Overview

This document outlines the implementation plan for building a unified Knowledge Base system that evolves from the current FAQ-only design to a comprehensive, graph-ready knowledge management platform.

---

## 1. Summary of Changes

### Phase 1: Core Knowledge Base (Current Sprint)

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| **Unified Schema** | Generalize from FAQ to multi-type knowledge items | Critical |
| **Hybrid Search** | BM25 full-text + vector similarity with RRF | Critical |
| **Knowledge Variants** | Support multiple phrasings per item (1:N) | Critical |
| **Hit Tracking** | Track retrieval patterns | High |
| **Version History** | Track changes with time-based expiration | Medium |
| **Relationships** | Explicit links between knowledge items | Medium |
| **Enhanced Pipeline** | Variant-aware ticket processing | Critical |

### Phase 2: Graph Enhancement (Next Sprint)

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| **Graph Loading Service** | Load knowledge into NetworkX | High |
| **Tag-Based Edges** | Implicit relationships via shared tags | High |
| **Similarity Edges** | Auto-computed semantic relationships | Medium |
| **Graph-Enhanced Retrieval** | Multi-hop context retrieval | High |

### Phase 3: Advanced Features (Future)

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| **Real-Time Graph Updates** | Event-driven graph sync | Medium |
| **Graph Analytics** | Centrality, clustering, gap detection | Low |
| **Path Explanations** | "Why this result?" reasoning | Low |
| **Access Control** | Fine-grained permissions | Medium |

---

## 2. Database Schema

### 2.1 Core Tables

#### 2.1.1 `agent.knowledge_categories`

```sql
CREATE TABLE agent.knowledge_categories (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  slug VARCHAR(100) NOT NULL,
  description TEXT,
  parent_id INT REFERENCES agent.knowledge_categories(id),
  
  -- Category-level defaults
  default_visibility VARCHAR(20) DEFAULT 'internal',
  default_owner_team VARCHAR(100),
  
  -- Ordering
  sort_order INT DEFAULT 0,
  
  -- Audit
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ,
  is_deleted BOOLEAN DEFAULT FALSE,
  
  UNIQUE(slug, COALESCE(parent_id, 0))
);

CREATE INDEX idx_knowledge_categories_parent ON agent.knowledge_categories(parent_id);
CREATE INDEX idx_knowledge_categories_slug ON agent.knowledge_categories(slug);
```

#### 2.1.2 `agent.knowledge_items`

```sql
CREATE TABLE agent.knowledge_items (
  id SERIAL PRIMARY KEY,
  
  -- Type & Classification
  knowledge_type VARCHAR(30) NOT NULL,  -- 'faq', 'policy', 'procedure', 'business_rule', 'context', 'permission', 'reference', 'troubleshooting'
  category_id INT REFERENCES agent.knowledge_categories(id),
  
  -- Universal Content Fields
  title TEXT NOT NULL,
  summary TEXT,
  
  -- Type-Specific Content (JSONB for flexibility)
  content JSONB NOT NULL,
  /*
    FAQ:           {"question": "...", "answer": "..."}
    Policy:        {"body": "...", "effective_date": "...", "expiry_date": "..."}
    Procedure:     {"steps": [{"order": 1, "action": "...", "note": "..."}]}
    Business Rule: {"condition": "...", "action": "...", "exceptions": [...]}
    Context:       {"entity_type": "vendor", "entity_id": "...", "description": "..."}
    Permission:    {"role": "...", "resource": "...", "actions": ["read", "write"]}
    Reference:     {"term": "...", "definition": "...", "related_terms": [...]}
    Troubleshoot:  {"problem": "...", "diagnosis": "...", "solution": "..."}
  */
  
  -- Search & Retrieval
  embedding vector(1024),
  search_vector tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(summary, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(content->>'answer', content->>'body', content->>'definition', content->>'description', '')), 'C')
  ) STORED,
  
  -- Tagging (used for filtering and graph edges)
  tags TEXT[] DEFAULT '{}',
  
  -- Access Control
  visibility VARCHAR(20) DEFAULT 'internal',  -- 'public', 'internal', 'restricted', 'confidential'
  owner_id VARCHAR(100),
  team_id VARCHAR(100),
  
  -- Lifecycle
  status VARCHAR(20) DEFAULT 'draft',  -- 'draft', 'published', 'archived', 'deprecated'
  effective_from TIMESTAMPTZ,
  effective_until TIMESTAMPTZ,
  review_by TIMESTAMPTZ,
  
  -- Source Tracking
  source_type VARCHAR(30),  -- 'manual', 'ticket_pipeline', 'import', 'llm_generated'
  source_reference VARCHAR(100),
  
  -- Graph Sync (for real-time updates)
  graph_version INT DEFAULT 0,  -- Incremented on changes that affect graph
  graph_synced_at TIMESTAMPTZ,  -- Last sync to graph
  
  -- Audit
  created_by VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_by VARCHAR(100),
  updated_at TIMESTAMPTZ,
  is_deleted BOOLEAN DEFAULT FALSE,
  
  -- Metadata
  metadata_ JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_knowledge_items_type ON agent.knowledge_items(knowledge_type);
CREATE INDEX idx_knowledge_items_category ON agent.knowledge_items(category_id);
CREATE INDEX idx_knowledge_items_status ON agent.knowledge_items(status);
CREATE INDEX idx_knowledge_items_visibility ON agent.knowledge_items(visibility);
CREATE INDEX idx_knowledge_items_fts ON agent.knowledge_items USING gin(search_vector);
CREATE INDEX idx_knowledge_items_embedding ON agent.knowledge_items 
  USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_knowledge_items_tags ON agent.knowledge_items USING gin(tags);
CREATE INDEX idx_knowledge_items_graph_version ON agent.knowledge_items(graph_version) 
  WHERE is_deleted = FALSE;
```

#### 2.1.3 `agent.knowledge_variants`

```sql
CREATE TABLE agent.knowledge_variants (
  id SERIAL PRIMARY KEY,
  knowledge_item_id INT NOT NULL REFERENCES agent.knowledge_items(id) ON DELETE CASCADE,
  variant_text TEXT NOT NULL,
  embedding vector(1024),
  source VARCHAR(30) DEFAULT 'manual',  -- 'manual', 'ticket_pipeline', 'llm_generated'
  source_reference VARCHAR(100),
  
  -- Graph Sync
  graph_version INT DEFAULT 0,
  
  -- Audit
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by VARCHAR(100)
);

CREATE INDEX idx_knowledge_variants_item ON agent.knowledge_variants(knowledge_item_id);
CREATE INDEX idx_knowledge_variants_embedding ON agent.knowledge_variants 
  USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_knowledge_variants_fts ON agent.knowledge_variants 
  USING gin(to_tsvector('english', variant_text));
```

#### 2.1.4 `agent.knowledge_relationships`

```sql
CREATE TABLE agent.knowledge_relationships (
  id SERIAL PRIMARY KEY,
  source_id INT NOT NULL REFERENCES agent.knowledge_items(id) ON DELETE CASCADE,
  target_id INT NOT NULL REFERENCES agent.knowledge_items(id) ON DELETE CASCADE,
  relationship_type VARCHAR(30) NOT NULL,
  /*
    Relationship types:
    - 'related'      : Semantically similar
    - 'parent'       : Hierarchical parent
    - 'child'        : Hierarchical child
    - 'see_also'     : Cross-reference
    - 'supersedes'   : This item replaces target
    - 'depends_on'   : Prerequisite knowledge
    - 'implements'   : Policy -> Procedure relationship
    - 'governs'      : Rule that applies to target
  */
  
  -- Graph attributes
  weight FLOAT DEFAULT 1.0,
  is_bidirectional BOOLEAN DEFAULT FALSE,
  is_auto_generated BOOLEAN DEFAULT FALSE,
  
  -- Audit
  created_by VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(source_id, target_id, relationship_type),
  CHECK(source_id != target_id)
);

CREATE INDEX idx_knowledge_rel_source ON agent.knowledge_relationships(source_id);
CREATE INDEX idx_knowledge_rel_target ON agent.knowledge_relationships(target_id);
CREATE INDEX idx_knowledge_rel_type ON agent.knowledge_relationships(relationship_type);
-- Optimized for graph loading
CREATE INDEX idx_knowledge_rel_graph_load ON agent.knowledge_relationships(source_id, target_id, relationship_type, weight);
```

#### 2.1.5 `agent.knowledge_hits`

```sql
CREATE TABLE agent.knowledge_hits (
  id SERIAL PRIMARY KEY,
  knowledge_item_id INT REFERENCES agent.knowledge_items(id) ON DELETE CASCADE,
  variant_id INT REFERENCES agent.knowledge_variants(id) ON DELETE SET NULL,
  query_text TEXT,
  similarity_score FLOAT,
  retrieval_method VARCHAR(30),  -- 'hybrid_search', 'graph_traversal', 'direct'
  session_id VARCHAR(100),
  user_id VARCHAR(100),
  hit_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_knowledge_hits_item ON agent.knowledge_hits(knowledge_item_id);
CREATE INDEX idx_knowledge_hits_time ON agent.knowledge_hits(hit_at);
CREATE INDEX idx_knowledge_hits_method ON agent.knowledge_hits(retrieval_method);
```

#### 2.1.6 `agent.knowledge_versions`

```sql
CREATE TABLE agent.knowledge_versions (
  id SERIAL PRIMARY KEY,
  knowledge_item_id INT REFERENCES agent.knowledge_items(id) ON DELETE CASCADE,
  version_number INT NOT NULL,
  title TEXT NOT NULL,
  content JSONB NOT NULL,
  tags TEXT[],
  change_type VARCHAR(20),  -- 'create', 'update', 'merge', 'rollback'
  change_reason TEXT,
  changed_by VARCHAR(100),
  changed_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(knowledge_item_id, version_number)
);

CREATE INDEX idx_knowledge_versions_item ON agent.knowledge_versions(knowledge_item_id);
CREATE INDEX idx_knowledge_versions_time ON agent.knowledge_versions(changed_at);
```

#### 2.1.7 `agent.staging_knowledge_items`

```sql
CREATE TABLE agent.staging_knowledge_items (
  id SERIAL PRIMARY KEY,
  
  -- Same core fields as knowledge_items
  knowledge_type VARCHAR(30) NOT NULL,
  category_id INT REFERENCES agent.knowledge_categories(id),
  title TEXT NOT NULL,
  summary TEXT,
  content JSONB NOT NULL,
  embedding vector(1024),
  tags TEXT[] DEFAULT '{}',
  
  -- Pipeline-specific
  source_ticket_id VARCHAR(50),
  confidence FLOAT,
  status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
  action VARCHAR(20),  -- 'new', 'merge', 'add_variant'
  merge_with_id INT REFERENCES agent.knowledge_items(id),
  similarity FLOAT,
  
  -- Review
  reviewed_by VARCHAR(100),
  reviewed_at TIMESTAMPTZ,
  review_notes TEXT,
  
  -- Audit
  created_at TIMESTAMPTZ DEFAULT NOW(),
  metadata_ JSONB DEFAULT '{}'
);

CREATE INDEX idx_staging_knowledge_status ON agent.staging_knowledge_items(status);
CREATE INDEX idx_staging_knowledge_action ON agent.staging_knowledge_items(action);
```

### 2.2 Graph Event Tables (Phase 2+)

#### 2.2.1 `agent.knowledge_graph_events`

```sql
-- Event sourcing for real-time graph updates
CREATE TABLE agent.knowledge_graph_events (
  id BIGSERIAL PRIMARY KEY,
  event_type VARCHAR(30) NOT NULL,  -- 'node_created', 'node_updated', 'node_deleted', 'edge_created', 'edge_deleted'
  entity_type VARCHAR(30) NOT NULL,  -- 'knowledge_item', 'knowledge_variant', 'knowledge_relationship'
  entity_id INT NOT NULL,
  payload JSONB NOT NULL,  -- Event-specific data
  created_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ,  -- When graph service processed this event
  
  -- For ordered processing
  sequence_number BIGINT GENERATED ALWAYS AS IDENTITY
);

CREATE INDEX idx_graph_events_unprocessed ON agent.knowledge_graph_events(sequence_number) 
  WHERE processed_at IS NULL;
CREATE INDEX idx_graph_events_type ON agent.knowledge_graph_events(event_type);
```

#### 2.2.2 `agent.knowledge_graph_state`

```sql
-- Track graph service state
CREATE TABLE agent.knowledge_graph_state (
  id INT PRIMARY KEY DEFAULT 1,  -- Singleton
  last_processed_event_id BIGINT,
  last_full_reload_at TIMESTAMPTZ,
  node_count INT,
  edge_count INT,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  CHECK (id = 1)  -- Ensure singleton
);

INSERT INTO agent.knowledge_graph_state (id, last_processed_event_id, node_count, edge_count)
VALUES (1, 0, 0, 0);
```

### 2.3 Triggers

#### 2.3.1 Version History Trigger

```sql
CREATE OR REPLACE FUNCTION create_knowledge_version()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.title IS DISTINCT FROM NEW.title 
     OR OLD.content IS DISTINCT FROM NEW.content 
     OR OLD.tags IS DISTINCT FROM NEW.tags THEN
    
    INSERT INTO agent.knowledge_versions (
      knowledge_item_id, version_number, title, content, tags, 
      change_type, changed_by, changed_at
    )
    VALUES (
      OLD.id,
      COALESCE((SELECT MAX(version_number) FROM agent.knowledge_versions WHERE knowledge_item_id = OLD.id), 0) + 1,
      OLD.title,
      OLD.content,
      OLD.tags,
      'update',
      NEW.updated_by,
      NOW()
    );
    
    -- Increment graph version for sync
    NEW.graph_version := OLD.graph_version + 1;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER knowledge_version_trigger
BEFORE UPDATE ON agent.knowledge_items
FOR EACH ROW EXECUTE FUNCTION create_knowledge_version();
```

#### 2.3.2 Graph Event Triggers (Phase 2)

```sql
-- Emit events for graph sync
CREATE OR REPLACE FUNCTION emit_knowledge_graph_event()
RETURNS TRIGGER AS $$
DECLARE
  event_type VARCHAR(30);
  payload JSONB;
BEGIN
  IF TG_OP = 'INSERT' THEN
    event_type := 'node_created';
    payload := jsonb_build_object(
      'id', NEW.id,
      'knowledge_type', NEW.knowledge_type,
      'title', NEW.title,
      'tags', NEW.tags,
      'category_id', NEW.category_id,
      'visibility', NEW.visibility,
      'status', NEW.status
    );
  ELSIF TG_OP = 'UPDATE' THEN
    IF OLD.is_deleted = FALSE AND NEW.is_deleted = TRUE THEN
      event_type := 'node_deleted';
      payload := jsonb_build_object('id', NEW.id);
    ELSE
      event_type := 'node_updated';
      payload := jsonb_build_object(
        'id', NEW.id,
        'knowledge_type', NEW.knowledge_type,
        'title', NEW.title,
        'tags', NEW.tags,
        'category_id', NEW.category_id,
        'visibility', NEW.visibility,
        'status', NEW.status,
        'changed_fields', (
          SELECT jsonb_object_agg(key, value)
          FROM jsonb_each(to_jsonb(NEW))
          WHERE to_jsonb(NEW) ->> key IS DISTINCT FROM to_jsonb(OLD) ->> key
        )
      );
    END IF;
  ELSIF TG_OP = 'DELETE' THEN
    event_type := 'node_deleted';
    payload := jsonb_build_object('id', OLD.id);
  END IF;
  
  INSERT INTO agent.knowledge_graph_events (event_type, entity_type, entity_id, payload)
  VALUES (event_type, 'knowledge_item', COALESCE(NEW.id, OLD.id), payload);
  
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER knowledge_graph_event_trigger
AFTER INSERT OR UPDATE OR DELETE ON agent.knowledge_items
FOR EACH ROW EXECUTE FUNCTION emit_knowledge_graph_event();

-- Similar triggers for relationships
CREATE OR REPLACE FUNCTION emit_relationship_graph_event()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO agent.knowledge_graph_events (event_type, entity_type, entity_id, payload)
    VALUES ('edge_created', 'knowledge_relationship', NEW.id, 
      jsonb_build_object(
        'source_id', NEW.source_id,
        'target_id', NEW.target_id,
        'relationship_type', NEW.relationship_type,
        'weight', NEW.weight,
        'is_bidirectional', NEW.is_bidirectional
      )
    );
  ELSIF TG_OP = 'DELETE' THEN
    INSERT INTO agent.knowledge_graph_events (event_type, entity_type, entity_id, payload)
    VALUES ('edge_deleted', 'knowledge_relationship', OLD.id,
      jsonb_build_object(
        'source_id', OLD.source_id,
        'target_id', OLD.target_id,
        'relationship_type', OLD.relationship_type
      )
    );
  END IF;
  
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER relationship_graph_event_trigger
AFTER INSERT OR DELETE ON agent.knowledge_relationships
FOR EACH ROW EXECUTE FUNCTION emit_relationship_graph_event();
```

### 2.4 Views

#### 2.4.1 Hit Statistics View

```sql
CREATE VIEW agent.knowledge_hit_stats AS
SELECT 
  k.id,
  k.knowledge_type,
  k.title,
  k.tags,
  COUNT(h.id) AS total_hits,
  COUNT(DISTINCT h.session_id) AS unique_sessions,
  COUNT(DISTINCT DATE(h.hit_at)) AS days_with_hits,
  MAX(h.hit_at) AS last_hit_at,
  ROUND(AVG(h.similarity_score)::numeric, 3) AS avg_similarity,
  MODE() WITHIN GROUP (ORDER BY h.retrieval_method) AS primary_retrieval_method
FROM agent.knowledge_items k
LEFT JOIN agent.knowledge_hits h ON k.id = h.knowledge_item_id
WHERE k.is_deleted = FALSE
GROUP BY k.id, k.knowledge_type, k.title, k.tags;
```

#### 2.4.2 Backward Compatibility View (FAQ)

```sql
-- Mimics old purchasing_faq table for backward compatibility
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

### 2.5 Functions

#### 2.5.1 Hybrid Search Function

```sql
CREATE OR REPLACE FUNCTION agent.search_knowledge_hybrid(
  query_text TEXT,
  query_embedding vector(1024),
  result_limit INT DEFAULT 10,
  filter_types TEXT[] DEFAULT NULL,
  filter_tags TEXT[] DEFAULT NULL,
  filter_categories INT[] DEFAULT NULL,
  filter_visibility VARCHAR(20) DEFAULT 'internal',
  bm25_weight FLOAT DEFAULT 0.4,
  vector_weight FLOAT DEFAULT 0.6
)
RETURNS TABLE(
  id INT,
  knowledge_type VARCHAR(30),
  title TEXT,
  summary TEXT,
  content JSONB,
  tags TEXT[],
  category_id INT,
  hybrid_score FLOAT,
  match_sources TEXT[]
) AS $$
WITH 
-- BM25 search on knowledge items
text_search AS (
  SELECT k.id, k.knowledge_type, k.title, k.summary, k.content, k.tags, k.category_id,
         ROW_NUMBER() OVER (ORDER BY ts_rank_cd(k.search_vector, query) DESC) AS rank,
         'item_bm25'::TEXT AS match_source
  FROM agent.knowledge_items k, plainto_tsquery('english', query_text) query
  WHERE k.search_vector @@ query 
    AND k.is_deleted = FALSE
    AND k.status = 'published'
    AND (filter_types IS NULL OR k.knowledge_type = ANY(filter_types))
    AND (filter_tags IS NULL OR k.tags && filter_tags)
    AND (filter_categories IS NULL OR k.category_id = ANY(filter_categories))
    AND k.visibility <= filter_visibility
    AND (k.effective_until IS NULL OR k.effective_until > NOW())
  LIMIT 30
),
-- BM25 search on variants
variant_text_search AS (
  SELECT k.id, k.knowledge_type, k.title, k.summary, k.content, k.tags, k.category_id,
         ROW_NUMBER() OVER (ORDER BY ts_rank_cd(to_tsvector('english', v.variant_text), query) DESC) AS rank,
         'variant_bm25'::TEXT AS match_source
  FROM agent.knowledge_variants v
  JOIN agent.knowledge_items k ON v.knowledge_item_id = k.id
  CROSS JOIN plainto_tsquery('english', query_text) query
  WHERE to_tsvector('english', v.variant_text) @@ query 
    AND k.is_deleted = FALSE
    AND k.status = 'published'
    AND (filter_types IS NULL OR k.knowledge_type = ANY(filter_types))
    AND (filter_tags IS NULL OR k.tags && filter_tags)
    AND (filter_categories IS NULL OR k.category_id = ANY(filter_categories))
    AND k.visibility <= filter_visibility
  LIMIT 30
),
-- Vector search on knowledge items
vector_search AS (
  SELECT k.id, k.knowledge_type, k.title, k.summary, k.content, k.tags, k.category_id,
         ROW_NUMBER() OVER (ORDER BY k.embedding <=> query_embedding) AS rank,
         'item_vector'::TEXT AS match_source
  FROM agent.knowledge_items k
  WHERE k.embedding IS NOT NULL 
    AND k.is_deleted = FALSE
    AND k.status = 'published'
    AND (filter_types IS NULL OR k.knowledge_type = ANY(filter_types))
    AND (filter_tags IS NULL OR k.tags && filter_tags)
    AND (filter_categories IS NULL OR k.category_id = ANY(filter_categories))
    AND k.visibility <= filter_visibility
    AND (k.effective_until IS NULL OR k.effective_until > NOW())
  ORDER BY k.embedding <=> query_embedding
  LIMIT 30
),
-- Vector search on variants
variant_vector_search AS (
  SELECT k.id, k.knowledge_type, k.title, k.summary, k.content, k.tags, k.category_id,
         ROW_NUMBER() OVER (ORDER BY v.embedding <=> query_embedding) AS rank,
         'variant_vector'::TEXT AS match_source
  FROM agent.knowledge_variants v
  JOIN agent.knowledge_items k ON v.knowledge_item_id = k.id
  WHERE v.embedding IS NOT NULL 
    AND k.is_deleted = FALSE
    AND k.status = 'published'
    AND (filter_types IS NULL OR k.knowledge_type = ANY(filter_types))
    AND (filter_tags IS NULL OR k.tags && filter_tags)
    AND (filter_categories IS NULL OR k.category_id = ANY(filter_categories))
    AND k.visibility <= filter_visibility
  ORDER BY v.embedding <=> query_embedding
  LIMIT 30
),
-- Combine all sources
all_results AS (
  SELECT * FROM text_search
  UNION ALL SELECT * FROM variant_text_search
  UNION ALL SELECT * FROM vector_search
  UNION ALL SELECT * FROM variant_vector_search
),
-- Apply RRF scoring
rrf_scores AS (
  SELECT 
    id,
    MAX(knowledge_type) AS knowledge_type,
    MAX(title) AS title,
    MAX(summary) AS summary,
    MAX(content) AS content,
    MAX(tags) AS tags,
    MAX(category_id) AS category_id,
    SUM(
      CASE 
        WHEN match_source LIKE '%bm25' THEN bm25_weight / (60 + rank)
        ELSE vector_weight / (60 + rank)
      END
    ) AS hybrid_score,
    ARRAY_AGG(DISTINCT match_source) AS match_sources
  FROM all_results
  GROUP BY id
)
SELECT id, knowledge_type, title, summary, content, tags, category_id, hybrid_score, match_sources
FROM rrf_scores
ORDER BY hybrid_score DESC
LIMIT result_limit;
$$ LANGUAGE SQL;
```

### 2.6 Maintenance Jobs

#### 2.6.1 Version Cleanup (Cron: Daily)

```sql
-- Delete versions older than 90 days
DELETE FROM agent.knowledge_versions 
WHERE changed_at < NOW() - INTERVAL '90 days';
```

#### 2.6.2 Graph Event Cleanup (Cron: Daily)

```sql
-- Delete processed events older than 7 days
DELETE FROM agent.knowledge_graph_events 
WHERE processed_at IS NOT NULL 
  AND processed_at < NOW() - INTERVAL '7 days';
```

#### 2.6.3 Hit Data Aggregation (Cron: Weekly)

```sql
-- Archive old hit data to aggregated table (optional)
-- Keep detailed hits for 30 days, aggregate older data
```

---

## 3. Service Layer

### 3.1 Knowledge Graph Service

```python
import networkx as nx
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import numpy as np

@dataclass
class GraphConfig:
    include_tag_edges: bool = True
    include_similarity_edges: bool = True
    similarity_threshold: float = 0.75
    tag_edge_weight: float = 0.5
    similarity_edge_weight: float = 0.3
    explicit_edge_weight: float = 1.0
    max_tag_cooccurrence: int = 50  # Skip tags with too many items
    event_poll_interval: float = 1.0  # Seconds between event polls

@dataclass
class GraphStats:
    node_count: int = 0
    edge_count: int = 0
    explicit_edges: int = 0
    tag_edges: int = 0
    similarity_edges: int = 0
    last_full_load: Optional[datetime] = None
    last_event_processed: Optional[int] = None


class KnowledgeGraphService:
    """
    Manages in-memory NetworkX graph with real-time updates from PostgreSQL.
    """
    
    def __init__(self, session_maker, config: GraphConfig = None):
        self.session_maker = session_maker
        self.config = config or GraphConfig()
        self.graph: Optional[nx.DiGraph] = None
        self.stats = GraphStats()
        self._lock = asyncio.Lock()
        self._running = False
    
    # ==================== Full Load ====================
    
    async def load_graph(self) -> nx.DiGraph:
        """Full graph load from database"""
        async with self._lock:
            G = nx.DiGraph()
            
            async with self.session_maker() as session:
                # Load nodes
                items = await session.execute(text("""
                    SELECT id, knowledge_type, title, summary, tags, 
                           category_id, visibility, status, embedding
                    FROM agent.knowledge_items
                    WHERE is_deleted = FALSE AND status = 'published'
                """))
                
                for item in items:
                    G.add_node(item.id, **{
                        'type': item.knowledge_type,
                        'title': item.title,
                        'summary': item.summary,
                        'tags': item.tags or [],
                        'category_id': item.category_id,
                        'visibility': item.visibility,
                        'embedding': item.embedding
                    })
                
                # Load explicit relationships
                rels = await session.execute(text("""
                    SELECT source_id, target_id, relationship_type, weight, is_bidirectional
                    FROM agent.knowledge_relationships
                """))
                
                explicit_count = 0
                for rel in rels:
                    G.add_edge(rel.source_id, rel.target_id,
                        type=rel.relationship_type,
                        weight=rel.weight * self.config.explicit_edge_weight,
                        source='explicit'
                    )
                    explicit_count += 1
                    
                    if rel.is_bidirectional:
                        G.add_edge(rel.target_id, rel.source_id,
                            type=rel.relationship_type,
                            weight=rel.weight * self.config.explicit_edge_weight,
                            source='explicit'
                        )
                        explicit_count += 1
                
                # Get last processed event
                state = await session.execute(text("""
                    SELECT last_processed_event_id FROM agent.knowledge_graph_state WHERE id = 1
                """))
                last_event = state.scalar() or 0
            
            # Add implicit edges
            tag_count = 0
            sim_count = 0
            
            if self.config.include_tag_edges:
                tag_count = self._add_tag_edges(G)
            
            if self.config.include_similarity_edges:
                sim_count = self._add_similarity_edges(G)
            
            self.graph = G
            self.stats = GraphStats(
                node_count=G.number_of_nodes(),
                edge_count=G.number_of_edges(),
                explicit_edges=explicit_count,
                tag_edges=tag_count,
                similarity_edges=sim_count,
                last_full_load=datetime.now(),
                last_event_processed=last_event
            )
            
            return G
    
    def _add_tag_edges(self, G: nx.DiGraph) -> int:
        """Add edges between nodes sharing tags"""
        tag_index: Dict[str, List[int]] = {}
        
        for node_id in G.nodes:
            for tag in G.nodes[node_id].get('tags', []):
                tag_index.setdefault(tag, []).append(node_id)
        
        edge_count = 0
        for tag, nodes in tag_index.items():
            if len(nodes) < 2 or len(nodes) > self.config.max_tag_cooccurrence:
                continue
            
            for i, n1 in enumerate(nodes):
                for n2 in nodes[i+1:]:
                    for src, tgt in [(n1, n2), (n2, n1)]:
                        if G.has_edge(src, tgt) and G[src][tgt].get('source') == 'explicit':
                            continue  # Don't override explicit edges
                        
                        if G.has_edge(src, tgt):
                            G[src][tgt]['weight'] += self.config.tag_edge_weight
                            G[src][tgt].setdefault('shared_tags', []).append(tag)
                        else:
                            G.add_edge(src, tgt,
                                type='shared_tag',
                                weight=self.config.tag_edge_weight,
                                shared_tags=[tag],
                                source='tag'
                            )
                            edge_count += 1
        
        return edge_count
    
    def _add_similarity_edges(self, G: nx.DiGraph) -> int:
        """Add edges between semantically similar nodes"""
        nodes_with_emb = [
            (n, np.array(G.nodes[n]['embedding']))
            for n in G.nodes
            if G.nodes[n].get('embedding') is not None
        ]
        
        edge_count = 0
        for i, (n1, emb1) in enumerate(nodes_with_emb):
            for n2, emb2 in nodes_with_emb[i+1:]:
                sim = float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
                
                if sim >= self.config.similarity_threshold:
                    for src, tgt in [(n1, n2), (n2, n1)]:
                        if G.has_edge(src, tgt) and G[src][tgt].get('source') in ('explicit', 'tag'):
                            continue
                        
                        G.add_edge(src, tgt,
                            type='similar',
                            weight=sim * self.config.similarity_edge_weight,
                            similarity=sim,
                            source='embedding'
                        )
                        edge_count += 1
        
        return edge_count
    
    # ==================== Real-Time Updates ====================
    
    async def start_event_processor(self):
        """Start background event processing loop"""
        self._running = True
        while self._running:
            try:
                await self._process_pending_events()
            except Exception as e:
                logger.error(f"Error processing graph events: {e}")
            
            await asyncio.sleep(self.config.event_poll_interval)
    
    async def stop_event_processor(self):
        """Stop background event processing"""
        self._running = False
    
    async def _process_pending_events(self):
        """Process unprocessed graph events"""
        if self.graph is None:
            return
        
        async with self.session_maker() as session:
            # Get unprocessed events
            events = await session.execute(text("""
                SELECT id, event_type, entity_type, entity_id, payload
                FROM agent.knowledge_graph_events
                WHERE processed_at IS NULL
                ORDER BY sequence_number
                LIMIT 100
            """))
            
            event_list = events.fetchall()
            if not event_list:
                return
            
            async with self._lock:
                for event in event_list:
                    await self._apply_event(event)
                
                # Mark events as processed
                event_ids = [e.id for e in event_list]
                await session.execute(text("""
                    UPDATE agent.knowledge_graph_events
                    SET processed_at = NOW()
                    WHERE id = ANY(:ids)
                """), {"ids": event_ids})
                
                # Update state
                await session.execute(text("""
                    UPDATE agent.knowledge_graph_state
                    SET last_processed_event_id = :event_id,
                        node_count = :nodes,
                        edge_count = :edges,
                        updated_at = NOW()
                    WHERE id = 1
                """), {
                    "event_id": event_list[-1].id,
                    "nodes": self.graph.number_of_nodes(),
                    "edges": self.graph.number_of_edges()
                })
                
                await session.commit()
            
            self.stats.last_event_processed = event_list[-1].id
    
    async def _apply_event(self, event):
        """Apply a single event to the graph"""
        G = self.graph
        payload = event.payload
        
        if event.event_type == 'node_created':
            G.add_node(payload['id'], **{
                'type': payload['knowledge_type'],
                'title': payload['title'],
                'tags': payload.get('tags', []),
                'category_id': payload.get('category_id'),
                'visibility': payload.get('visibility'),
                'embedding': None  # Will be updated on next event
            })
            # Rebuild tag edges for this node
            self._rebuild_tag_edges_for_node(payload['id'])
        
        elif event.event_type == 'node_updated':
            if payload['id'] in G.nodes:
                G.nodes[payload['id']].update({
                    'type': payload['knowledge_type'],
                    'title': payload['title'],
                    'tags': payload.get('tags', []),
                    'category_id': payload.get('category_id'),
                    'visibility': payload.get('visibility')
                })
                # Rebuild tag edges
                self._remove_tag_edges_for_node(payload['id'])
                self._rebuild_tag_edges_for_node(payload['id'])
        
        elif event.event_type == 'node_deleted':
            if payload['id'] in G.nodes:
                G.remove_node(payload['id'])
        
        elif event.event_type == 'edge_created':
            G.add_edge(payload['source_id'], payload['target_id'],
                type=payload['relationship_type'],
                weight=payload.get('weight', 1.0) * self.config.explicit_edge_weight,
                source='explicit'
            )
            if payload.get('is_bidirectional'):
                G.add_edge(payload['target_id'], payload['source_id'],
                    type=payload['relationship_type'],
                    weight=payload.get('weight', 1.0) * self.config.explicit_edge_weight,
                    source='explicit'
                )
        
        elif event.event_type == 'edge_deleted':
            if G.has_edge(payload['source_id'], payload['target_id']):
                G.remove_edge(payload['source_id'], payload['target_id'])
    
    def _rebuild_tag_edges_for_node(self, node_id: int):
        """Rebuild tag-based edges for a specific node"""
        G = self.graph
        if node_id not in G.nodes:
            return
        
        node_tags = set(G.nodes[node_id].get('tags', []))
        
        for other_id in G.nodes:
            if other_id == node_id:
                continue
            
            other_tags = set(G.nodes[other_id].get('tags', []))
            shared = node_tags & other_tags
            
            if shared and len(shared) <= self.config.max_tag_cooccurrence:
                for src, tgt in [(node_id, other_id), (other_id, node_id)]:
                    if G.has_edge(src, tgt) and G[src][tgt].get('source') == 'explicit':
                        continue
                    
                    G.add_edge(src, tgt,
                        type='shared_tag',
                        weight=len(shared) * self.config.tag_edge_weight,
                        shared_tags=list(shared),
                        source='tag'
                    )
    
    def _remove_tag_edges_for_node(self, node_id: int):
        """Remove tag-based edges for a node"""
        G = self.graph
        edges_to_remove = [
            (u, v) for u, v, d in G.edges(data=True)
            if (u == node_id or v == node_id) and d.get('source') == 'tag'
        ]
        G.remove_edges_from(edges_to_remove)
    
    # ==================== Query Methods ====================
    
    def get_neighbors(self, node_id: int, max_hops: int = 2, 
                      edge_types: List[str] = None,
                      node_types: List[str] = None) -> Dict[int, Dict]:
        """Get neighboring nodes within max_hops"""
        if self.graph is None or node_id not in self.graph:
            return {}
        
        G = self.graph
        result = {}
        
        # BFS traversal
        visited = {node_id}
        current_level = {node_id}
        
        for hop in range(1, max_hops + 1):
            next_level = set()
            
            for n in current_level:
                for neighbor in G.neighbors(n):
                    if neighbor in visited:
                        continue
                    
                    edge_data = G[n][neighbor]
                    node_data = G.nodes[neighbor]
                    
                    # Filter by edge type
                    if edge_types and edge_data.get('type') not in edge_types:
                        continue
                    
                    # Filter by node type
                    if node_types and node_data.get('type') not in node_types:
                        continue
                    
                    visited.add(neighbor)
                    next_level.add(neighbor)
                    
                    result[neighbor] = {
                        'distance': hop,
                        'node': node_data,
                        'edge': edge_data
                    }
            
            current_level = next_level
        
        return result
    
    def find_path(self, source_id: int, target_id: int) -> Optional[List[Dict]]:
        """Find shortest path between two nodes"""
        if self.graph is None:
            return None
        
        try:
            path = nx.shortest_path(self.graph, source_id, target_id)
            
            result = []
            for i, node_id in enumerate(path):
                node_info = {
                    'id': node_id,
                    'node': self.graph.nodes[node_id]
                }
                
                if i > 0:
                    prev_id = path[i-1]
                    node_info['edge_from'] = self.graph[prev_id][node_id]
                
                result.append(node_info)
            
            return result
        except nx.NetworkXNoPath:
            return None
```

### 3.2 Graph-Enhanced Retriever

```python
class GraphEnhancedRetriever:
    """
    Combines hybrid search with graph traversal for context-rich retrieval.
    """
    
    def __init__(
        self, 
        session_maker,
        embedding_client,
        graph_service: KnowledgeGraphService
    ):
        self.session_maker = session_maker
        self.embedding_client = embedding_client
        self.graph_service = graph_service
    
    async def retrieve(
        self,
        query: str,
        # Entry point config
        entry_types: List[str] = None,
        entry_limit: int = 3,
        # Graph expansion config
        expand_graph: bool = True,
        context_types: List[str] = None,
        max_hops: int = 2,
        context_limit: int = 5,
        # Filtering
        filter_tags: List[str] = None,
        filter_categories: List[int] = None,
        visibility: str = 'internal',
        # Tracking
        session_id: str = None,
        user_id: str = None
    ) -> Dict:
        """
        1. Find entry points via hybrid search
        2. Expand via graph traversal
        3. Filter and rank results
        4. Record hits
        """
        
        # Generate embedding
        query_embedding = await self.embedding_client.embed(query)
        
        async with self.session_maker() as session:
            # Step 1: Hybrid search for entry points
            entry_points = await session.execute(
                text("SELECT * FROM agent.search_knowledge_hybrid(:q, :emb, :lim, :types, :tags, :cats, :vis)"),
                {
                    "q": query,
                    "emb": query_embedding,
                    "lim": entry_limit,
                    "types": entry_types,
                    "tags": filter_tags,
                    "cats": filter_categories,
                    "vis": visibility
                }
            )
            entry_list = entry_points.fetchall()
            
            if not entry_list:
                return {"entry_points": [], "context": [], "paths": []}
            
            # Step 2: Graph expansion
            context = []
            paths = []
            
            if expand_graph and self.graph_service.graph:
                seen_ids = {e.id for e in entry_list}
                
                for entry in entry_list:
                    neighbors = self.graph_service.get_neighbors(
                        entry.id,
                        max_hops=max_hops,
                        node_types=context_types
                    )
                    
                    for node_id, info in neighbors.items():
                        if node_id in seen_ids:
                            continue
                        
                        # Apply tag filter
                        if filter_tags:
                            node_tags = info['node'].get('tags', [])
                            if not any(t in node_tags for t in filter_tags):
                                continue
                        
                        seen_ids.add(node_id)
                        
                        # Calculate context score
                        edge_weight = info['edge'].get('weight', 0.5)
                        distance_penalty = 1 / (info['distance'] + 1)
                        context_score = edge_weight * distance_penalty
                        
                        context.append({
                            'id': node_id,
                            'type': info['node'].get('type'),
                            'title': info['node'].get('title'),
                            'score': context_score,
                            'distance': info['distance'],
                            'edge_type': info['edge'].get('type'),
                            'from_entry': entry.id
                        })
                
                # Sort by score and limit
                context.sort(key=lambda x: x['score'], reverse=True)
                context = context[:context_limit]
                
                # Get full content for context items
                if context:
                    context_ids = [c['id'] for c in context]
                    full_context = await session.execute(text("""
                        SELECT id, knowledge_type, title, summary, content, tags
                        FROM agent.knowledge_items
                        WHERE id = ANY(:ids)
                    """), {"ids": context_ids})
                    
                    context_map = {r.id: r for r in full_context}
                    for c in context:
                        if c['id'] in context_map:
                            row = context_map[c['id']]
                            c['summary'] = row.summary
                            c['content'] = row.content
                            c['tags'] = row.tags
            
            # Step 3: Record hits
            if session_id:
                for entry in entry_list:
                    await session.execute(
                        text("""
                            INSERT INTO agent.knowledge_hits 
                            (knowledge_item_id, query_text, similarity_score, retrieval_method, session_id, user_id)
                            VALUES (:item_id, :query, :score, :method, :session, :user)
                        """),
                        {
                            "item_id": entry.id,
                            "query": query,
                            "score": entry.hybrid_score,
                            "method": "graph_enhanced" if expand_graph else "hybrid_search",
                            "session": session_id,
                            "user": user_id
                        }
                    )
                await session.commit()
            
            return {
                "entry_points": [dict(e._mapping) for e in entry_list],
                "context": context,
                "graph_stats": {
                    "nodes_explored": len(context) + len(entry_list),
                    "max_hops_used": max_hops if context else 0
                }
            }
```

---

## 4. Pipeline Changes

### 4.1 Updated Analysis Actions

```python
class AnalysisAction(str, Enum):
    SKIP = "skip"               # Exact duplicate
    ADD_VARIANT = "add_variant"  # Add title/question variant only
    MERGE = "merge"             # Update existing content
    NEW = "new"                 # Create new knowledge item
```

### 4.2 Decision Flow

```
Ticket Arrives
     │
     ▼
Find similar knowledge items + variants (all types)
     │
     ▼
┌────────────────────────────────────────────┐
│              Similarity Score              │
├──────────┬──────────┬──────────┬───────────┤
│  ≥0.95   │  ≥0.85   │  ≥0.70   │   <0.70   │
│  SKIP    │  Content │   LLM    │    NEW    │
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

### 4.3 Knowledge Type Detection

```python
async def detect_knowledge_type(self, ticket: TicketData) -> str:
    """Detect what type of knowledge this ticket represents"""
    
    prompt = f"""
    Analyze this support ticket and determine what type of knowledge it represents:
    
    Subject: {ticket.subject}
    Body: {ticket.body}
    Resolution: {ticket.closurenotes}
    
    Knowledge types:
    - faq: Question and answer pair
    - procedure: Step-by-step process
    - troubleshooting: Problem diagnosis and solution
    - business_rule: Condition-based rule or policy
    - reference: Definition or explanation of a term
    
    Return JSON: {{"type": "...", "confidence": 0.X}}
    """
    
    result = await self.llm.structured_inference(prompt)
    return result["type"]
```

---

## 5. API Endpoints

### 5.1 Knowledge Items

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/knowledge` | List knowledge items (paginated, filtered) |
| `GET` | `/knowledge/{id}` | Get knowledge item with variants and relationships |
| `POST` | `/knowledge` | Create knowledge item |
| `PUT` | `/knowledge/{id}` | Update knowledge item |
| `DELETE` | `/knowledge/{id}` | Soft delete knowledge item |

### 5.2 Variants

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/knowledge/{id}/variants` | List variants |
| `POST` | `/knowledge/{id}/variants` | Add variant |
| `DELETE` | `/knowledge/variants/{variant_id}` | Delete variant |

### 5.3 Relationships

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/knowledge/{id}/relationships` | Get relationships |
| `POST` | `/knowledge/{id}/relationships` | Add relationship |
| `DELETE` | `/knowledge/relationships/{rel_id}` | Remove relationship |

### 5.4 Graph

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/knowledge/graph/stats` | Get graph statistics |
| `GET` | `/knowledge/{id}/graph/neighbors` | Get graph neighbors |
| `GET` | `/knowledge/graph/path` | Find path between items |
| `POST` | `/knowledge/graph/reload` | Force full graph reload |

### 5.5 Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/knowledge/search` | Hybrid search |
| `POST` | `/knowledge/search/context` | Graph-enhanced contextual search |

### 5.6 Categories

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/knowledge/categories` | List categories (tree) |
| `POST` | `/knowledge/categories` | Create category |
| `PUT` | `/knowledge/categories/{id}` | Update category |
| `DELETE` | `/knowledge/categories/{id}` | Delete category |

---

## 6. Implementation Phases

### Phase 1: Core Knowledge Base (2 weeks)

| Task | Effort |
|------|--------|
| Create `knowledge_categories` table | 0.5 day |
| Create `knowledge_items` table | 1 day |
| Create `knowledge_variants` table | 0.5 day |
| Create `knowledge_relationships` table | 0.5 day |
| Create `knowledge_hits` table | 0.5 day |
| Create `knowledge_versions` table + trigger | 1 day |
| Create hybrid search function | 1 day |
| Create backward compatibility view | 0.5 day |
| Update pipeline for new schema | 2 days |
| Create CRUD API endpoints | 2 days |
| Testing | 2 days |

### Phase 2: Graph Enhancement (1.5 weeks)

| Task | Effort |
|------|--------|
| Create `knowledge_graph_events` table | 0.5 day |
| Create graph event triggers | 1 day |
| Implement `KnowledgeGraphService` | 2 days |
| Implement graph loading and caching | 1 day |
| Implement `GraphEnhancedRetriever` | 1 day |
| Add graph API endpoints | 1 day |
| Testing | 1 day |

### Phase 3: Real-Time Updates (1 week)

| Task | Effort |
|------|--------|
| Implement event processor loop | 1 day |
| Implement incremental graph updates | 2 days |
| Add graph state tracking | 0.5 day |
| Performance optimization | 1 day |
| Testing | 1 day |

### Phase 4: Advanced Features (Future)

| Task | Effort |
|------|--------|
| Graph analytics (centrality, clustering) | 2 days |
| Path explanations | 1 day |
| Access control integration | 2 days |
| Admin UI enhancements | 3 days |

**Total Phase 1-3: ~5 weeks**

---

## 7. Configuration

### 7.1 Environment Variables

```bash
# Graph configuration
KNOWLEDGE_GRAPH_ENABLED=true
KNOWLEDGE_GRAPH_TAG_EDGES=true
KNOWLEDGE_GRAPH_SIMILARITY_EDGES=true
KNOWLEDGE_GRAPH_SIMILARITY_THRESHOLD=0.75
KNOWLEDGE_GRAPH_EVENT_POLL_INTERVAL=1.0

# Search configuration
KNOWLEDGE_SEARCH_BM25_WEIGHT=0.4
KNOWLEDGE_SEARCH_VECTOR_WEIGHT=0.6
KNOWLEDGE_SEARCH_DEFAULT_LIMIT=10

# Maintenance
KNOWLEDGE_VERSION_RETENTION_DAYS=90
KNOWLEDGE_EVENT_RETENTION_DAYS=7
```

### 7.2 Graph Config Dataclass

```python
@dataclass
class GraphConfig:
    include_tag_edges: bool = True
    include_similarity_edges: bool = True
    similarity_threshold: float = 0.75
    tag_edge_weight: float = 0.5
    similarity_edge_weight: float = 0.3
    explicit_edge_weight: float = 1.0
    max_tag_cooccurrence: int = 50
    event_poll_interval: float = 1.0
```

---

## 8. Testing Checklist

### Search Quality
- [ ] BM25 returns relevant results for keyword queries
- [ ] Vector search returns semantic matches
- [ ] Hybrid search combines both effectively
- [ ] Variants are matched correctly
- [ ] Filters (type, tag, category, visibility) work correctly

### Graph Operations
- [ ] Full graph load completes successfully
- [ ] Tag-based edges are created correctly
- [ ] Similarity edges respect threshold
- [ ] Event processor updates graph in real-time
- [ ] Graph neighbors query returns correct results
- [ ] Path finding works across relationship types

### Pipeline
- [ ] Knowledge type detection works
- [ ] SKIP action for high similarity
- [ ] ADD_VARIANT for same question, no new content
- [ ] MERGE for same question with new content
- [ ] NEW for low similarity

### Data Integrity
- [ ] Versions are created on update
- [ ] Old versions are cleaned up
- [ ] Graph events are emitted correctly
- [ ] Processed events are cleaned up
- [ ] Backward compatibility view works

---

## 9. Rollback Plan

All changes are additive:

1. **Schema**: New tables don't affect existing functionality
2. **Graph**: Can disable graph features via config; falls back to hybrid search only
3. **Real-time updates**: Can disable event processor; graph still works with periodic full reload
4. **Backward compatibility**: `purchasing_faq` view ensures existing code continues to work

To rollback specific features:
```bash
# Disable graph entirely
KNOWLEDGE_GRAPH_ENABLED=false

# Disable real-time updates (use periodic full reload)
KNOWLEDGE_GRAPH_EVENT_POLL_INTERVAL=0

# Disable implicit edges
KNOWLEDGE_GRAPH_TAG_EDGES=false
KNOWLEDGE_GRAPH_SIMILARITY_EDGES=false
```
