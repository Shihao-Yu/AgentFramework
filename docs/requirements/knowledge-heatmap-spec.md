# Knowledge Node Heatmap - Requirements Specification

> **Status**: Implemented  
> **Created**: 2026-01-15  
> **Implemented**: 2026-01-15  
> **Purpose**: Visualize knowledge node usage frequency to identify hot spots (frequently asked) and cold spots (never accessed)

---

## 1. Overview

### 1.1 Problem Statement

ContextForge lacks visibility into which knowledge nodes are actually being used by agents and searches. Admins cannot currently answer:
- Which FAQs are most frequently retrieved?
- Which knowledge items are never accessed?
- Are certain topics trending up or down?
- Where should content investment be focused?

### 1.2 Solution

Implement a **Knowledge Heatmap** that:
1. Tracks every knowledge retrieval (hit)
2. Aggregates hit data by time period
3. Visualizes frequency as color intensity on the existing graph view
4. Provides filterable views by time, type, tenant, and tag

### 1.3 Success Criteria

- [ ] All search/retrieval paths record hits to `knowledge_hits` table
- [ ] Heatmap API returns per-node heat scores
- [ ] Graph view supports heat overlay with color gradient
- [ ] Users can toggle between type view and heat view
- [ ] Users can filter by 7d / 30d / 90d / all-time periods

---

## 2. Data Collection (Hit Tracking)

### 2.1 Current State

| Component | Status |
|-----------|--------|
| `knowledge_hits` table | ✅ Exists |
| `record_hit()` function | ✅ Exists in `SearchService` |
| Hit recording on search | ❌ Not wired |
| Hit recording on context retrieval | ❌ Not wired |
| Hit recording from SDK | ❌ Depends on API (not wired) |

### 2.2 Schema (Existing)

```sql
CREATE TABLE knowledge_hits (
    id BIGSERIAL PRIMARY KEY,
    node_id BIGINT REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    query_text TEXT,
    similarity_score FLOAT,
    retrieval_method VARCHAR(30),  -- 'bm25', 'vector', 'hybrid'
    match_source VARCHAR(50),
    session_id VARCHAR(100),
    user_id VARCHAR(100),
    hit_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 2.3 Entry Points to Instrument

| Entry Point | File | Action |
|-------------|------|--------|
| `POST /api/search` | `routes/search.py` | Record hit for each result in top-K |
| `GET /api/nodes/search` | `routes/nodes.py` | Record hit for each result |
| `GET /api/context` | `routes/context.py` | Record hit for entry points + context nodes |
| `POST /api/queryforge/` | `routes/queryforge.py` | Record hit for retrieved fields/examples |

### 2.4 What to Track

For each search/retrieval call, record a hit for **all top-K nodes returned** (no score threshold):

```python
async def record_hits_for_results(
    session: AsyncSession,
    results: List[SearchResult],
    query_text: str,
    retrieval_method: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """Record hits for all returned results (top-K, no threshold)."""
    # TODO: get ad_username from auth token
    user_id = user_id or "default"
    
    for result in results:
        await session.execute(
            text("""
                INSERT INTO knowledge_hits 
                (node_id, query_text, similarity_score, retrieval_method, session_id, user_id)
                VALUES (:node_id, :query_text, :score, :method, :session_id, :user_id)
            """),
            {
                "node_id": result.node.id,
                "query_text": query_text,
                "score": result.score,
                "method": retrieval_method,
                "session_id": session_id,
                "user_id": user_id,
            }
        )
    await session.commit()
```

### 2.5 Performance Consideration

For high-throughput scenarios, consider:
- **Batch inserts** instead of per-row
- **Async queue** (Redis/Kafka) for non-blocking writes
- **Sampling** at >1000 QPS (record 10% of hits)

For MVP, direct inserts are fine.

---

## 3. Data Aggregation

### 3.1 Aggregation Periods

| Period | Days | Use Case |
|--------|------|----------|
| `7d` | 7 | Recent trends |
| `30d` | 30 | Monthly view |
| `90d` | 90 | Quarterly view |
| `all` | ∞ | Historical total |

### 3.2 Metrics Per Node

| Metric | SQL | Description |
|--------|-----|-------------|
| `total_hits` | `COUNT(*)` | Raw hit count |
| `unique_sessions` | `COUNT(DISTINCT session_id)` | Breadth of usage |
| `unique_users` | `COUNT(DISTINCT user_id)` | Who's asking |
| `avg_similarity` | `AVG(similarity_score)` | Match quality |
| `last_hit_at` | `MAX(hit_at)` | Recency |
| `first_hit_at` | `MIN(hit_at)` | When discovered |

### 3.3 Heat Score Calculation

Normalize hits to 0-1 scale using **percentile rank** (handles skewed distributions):

```sql
WITH hit_counts AS (
    SELECT 
        node_id,
        COUNT(*) as total_hits,
        COUNT(DISTINCT session_id) as unique_sessions
    FROM knowledge_hits
    WHERE hit_at >= NOW() - INTERVAL ':days days'
    GROUP BY node_id
),
all_nodes AS (
    SELECT 
        n.id as node_id,
        COALESCE(h.total_hits, 0) as total_hits,
        COALESCE(h.unique_sessions, 0) as unique_sessions
    FROM knowledge_nodes n
    LEFT JOIN hit_counts h ON n.id = h.node_id
    WHERE n.is_deleted = FALSE AND n.status = 'published'
)
SELECT 
    node_id,
    total_hits,
    unique_sessions,
    PERCENT_RANK() OVER (ORDER BY total_hits) as heat_score_hits,
    PERCENT_RANK() OVER (ORDER BY unique_sessions) as heat_score_sessions
FROM all_nodes;
```

### 3.4 Aggregation by Dimension

| Dimension | Grouping | Use Case |
|-----------|----------|----------|
| Per-node | Individual nodes | Default heatmap |
| Per-tag | `GROUP BY unnest(tags)` | Tag cloud heat |
| Per-type | `GROUP BY node_type` | Type distribution |
| Per-tenant | `GROUP BY tenant_id` | Tenant comparison |

### 3.5 Materialized View (Optional - Phase 2)

For performance at scale, pre-compute daily rollups:

```sql
CREATE MATERIALIZED VIEW knowledge_hits_daily AS
SELECT 
    node_id,
    DATE(hit_at) as hit_date,
    COUNT(*) as total_hits,
    COUNT(DISTINCT session_id) as unique_sessions,
    COUNT(DISTINCT user_id) as unique_users,
    AVG(similarity_score) as avg_similarity
FROM knowledge_hits
GROUP BY node_id, DATE(hit_at);

-- Refresh daily via cron
REFRESH MATERIALIZED VIEW CONCURRENTLY knowledge_hits_daily;
```

---

## 4. API Design

### 4.1 New Endpoint: Heatmap Data

```
GET /api/metrics/heatmap
```

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `period` | enum | `7d` | Time period: `7d`, `30d`, `90d`, `all` |
| `metric` | enum | `hits` | Heat metric: `hits`, `sessions` |
| `tenant_ids` | string[] | user's tenants | Filter by tenant |
| `node_types` | string[] | all | Filter by node type |
| `tags` | string[] | all | Filter by tags |
| `include_zero` | bool | `true` | Include nodes with 0 hits |

**Response:**

```json
{
  "period": "7d",
  "metric": "hits",
  "generated_at": "2026-01-15T12:00:00Z",
  "stats": {
    "total_nodes": 150,
    "nodes_with_hits": 87,
    "total_hits": 2340,
    "max_hits": 156,
    "min_hits": 0
  },
  "nodes": [
    {
      "id": 42,
      "total_hits": 156,
      "unique_sessions": 45,
      "unique_users": 12,
      "avg_similarity": 0.87,
      "last_hit_at": "2026-01-15T11:30:00Z",
      "heat_score": 0.95
    },
    {
      "id": 17,
      "total_hits": 0,
      "unique_sessions": 0,
      "unique_users": 0,
      "avg_similarity": null,
      "last_hit_at": null,
      "heat_score": 0.0
    }
  ]
}
```

### 4.2 Endpoint: Heatmap by Tag

```
GET /api/metrics/heatmap/tags
```

**Response:**

```json
{
  "period": "7d",
  "tags": [
    {
      "tag": "purchasing",
      "node_count": 12,
      "total_hits": 450,
      "heat_score": 0.92
    },
    {
      "tag": "payables",
      "node_count": 8,
      "total_hits": 120,
      "heat_score": 0.45
    }
  ]
}
```

### 4.3 Endpoint: Heatmap by Type

```
GET /api/metrics/heatmap/types
```

**Response:**

```json
{
  "period": "7d",
  "types": [
    {
      "type": "faq",
      "node_count": 45,
      "total_hits": 1200,
      "heat_score": 0.88
    },
    {
      "type": "playbook",
      "node_count": 15,
      "total_hits": 340,
      "heat_score": 0.65
    }
  ]
}
```

---

## 5. Frontend Visualization

### 5.1 Graph Heatmap Mode

**Location**: Graph page (`/graph`)

**UI Changes:**

1. **View Mode Toggle** (top panel):
   ```
   [Type View] [Heat View]
   ```

2. **Period Selector** (visible in heat view):
   ```
   Period: [7d ▼]  Metric: [Hits ▼]
   ```

3. **Color Legend** (bottom panel):
   ```
   Cold ────────────────────── Hot
   🔵    🟢    🟡    🟠    🔴
   0     25%   50%   75%   100%
   ```

### 5.2 Node Visual Changes (Heat View)

| Heat Score | Color | Border | Effect |
|------------|-------|--------|--------|
| 0 (never) | `#e5e7eb` (gray-200) | Dashed | Faded opacity (0.5) |
| 0.01-0.25 | `#93c5fd` (blue-300) | Solid | Normal |
| 0.26-0.50 | `#86efac` (green-300) | Solid | Normal |
| 0.51-0.75 | `#fde047` (yellow-300) | Solid | Normal |
| 0.76-0.90 | `#fdba74` (orange-300) | Solid | Normal |
| 0.91-1.0 | `#fca5a5` (red-300) | Solid | Glow effect |

### 5.3 KnowledgeNode Component Changes

```typescript
// types/graph.ts - Add to KnowledgeNodeData
export interface KnowledgeNodeData extends Record<string, unknown> {
  id: number
  nodeType: NodeType
  title: string
  summary?: string
  tags: string[]
  isSearchMatch?: boolean
  // NEW: Heatmap data
  heatScore?: number      // 0-1, undefined = not in heat mode
  totalHits?: number
  uniqueSessions?: number
}

// Helper to get heat color
export function getHeatColor(score: number | undefined): string {
  if (score === undefined) return 'inherit'  // Type view mode
  if (score === 0) return '#e5e7eb'          // Gray - never accessed
  if (score <= 0.25) return '#93c5fd'        // Blue - cold
  if (score <= 0.50) return '#86efac'        // Green - warm
  if (score <= 0.75) return '#fde047'        // Yellow - hot
  if (score <= 0.90) return '#fdba74'        // Orange - very hot
  return '#fca5a5'                            // Red - extremely hot
}
```

### 5.4 GraphCanvasCore Changes

```typescript
// GraphCanvasCore.tsx
export interface GraphCanvasProps {
  graphNodes: GraphNode[]
  graphEdges: GraphEdge[]
  searchMatches?: number[]
  heatmapData?: Map<number, HeatmapNodeData>  // NEW
  viewMode?: 'type' | 'heat'                   // NEW
  onNodeSelect?: (nodeId: number | null) => void
  // ...
}

function transformToReactFlowNodes(
  graphNodes: GraphNode[],
  searchMatches: number[] = [],
  heatmapData?: Map<number, HeatmapNodeData>,
  viewMode: 'type' | 'heat' = 'type'
): Node<KnowledgeNodeData>[] {
  return graphNodes.map((node) => ({
    // ...existing
    data: {
      // ...existing
      heatScore: viewMode === 'heat' ? heatmapData?.get(node.id)?.heat_score : undefined,
      totalHits: heatmapData?.get(node.id)?.total_hits,
      uniqueSessions: heatmapData?.get(node.id)?.unique_sessions,
    },
  }))
}
```

### 5.5 Hook: useHeatmap

```typescript
// hooks/useHeatmap.ts
interface HeatmapNodeData {
  id: number
  total_hits: number
  unique_sessions: number
  heat_score: number
}

interface UseHeatmapOptions {
  period?: '7d' | '30d' | '90d' | 'all'
  metric?: 'hits' | 'sessions'
  enabled?: boolean
}

export function useHeatmap(options: UseHeatmapOptions = {}) {
  const { period = '7d', metric = 'hits', enabled = true } = options
  
  const query = useQuery({
    queryKey: ['heatmap', period, metric],
    queryFn: () => apiRequest<HeatmapResponse>('/api/metrics/heatmap', {
      params: { period, metric }
    }),
    enabled,
    staleTime: 5 * 60 * 1000,  // 5 minutes
  })
  
  const heatmapMap = useMemo(() => {
    if (!query.data?.nodes) return new Map()
    return new Map(query.data.nodes.map(n => [n.id, n]))
  }, [query.data])
  
  return {
    heatmapData: heatmapMap,
    stats: query.data?.stats,
    isLoading: query.isLoading,
    error: query.error,
  }
}
```

### 5.6 Node Tooltip Enhancement

When hovering a node in heat view, show stats:

```
┌─────────────────────────┐
│ How to approve a PO?    │
│ ────────────────────── │
│ 🔥 156 hits (top 5%)    │
│ 👥 45 unique sessions   │
│ 📅 Last: 2 hours ago    │
└─────────────────────────┘
```

---

## 6. Implementation Plan

### Phase 1: Data Collection (Backend)

| Task | File | Estimate |
|------|------|----------|
| Wire `record_hit()` in search route | `routes/search.py` | 1h |
| Wire `record_hit()` in nodes route | `routes/nodes.py` | 1h |
| Wire `record_hit()` in context route | `routes/context.py` | 1h |
| Add batch insert helper | `services/metrics_service.py` | 1h |
| Add tests for hit recording | `tests/` | 2h |

**Total: ~6 hours**

### Phase 2: Heatmap API (Backend)

| Task | File | Estimate |
|------|------|----------|
| Add `get_heatmap()` to MetricsService | `services/metrics_service.py` | 2h |
| Add `/metrics/heatmap` endpoint | `routes/metrics.py` | 1h |
| Add `/metrics/heatmap/tags` endpoint | `routes/metrics.py` | 1h |
| Add `/metrics/heatmap/types` endpoint | `routes/metrics.py` | 1h |
| Add response schemas | `schemas/metrics.py` | 1h |
| Add tests | `tests/` | 2h |

**Total: ~8 hours**

### Phase 3: Frontend Visualization

| Task | File | Estimate |
|------|------|----------|
| Add `useHeatmap` hook | `hooks/useHeatmap.ts` | 1h |
| Update `KnowledgeNodeData` type | `types/graph.ts` | 0.5h |
| Add heat color helper | `lib/graph-utils.ts` | 0.5h |
| Update `KnowledgeNode` component | `components/graph/nodes/KnowledgeNode.tsx` | 2h |
| Add view mode toggle | `components/graph/GraphCanvasCore.tsx` | 1h |
| Add period selector | `components/graph/GraphCanvasCore.tsx` | 1h |
| Add color legend | `components/graph/HeatLegend.tsx` | 1h |
| Add tooltip stats | `components/graph/nodes/KnowledgeNode.tsx` | 1h |
| Integration testing | Manual | 2h |

**Total: ~10 hours**

### Phase 4: Polish & Edge Cases

| Task | Estimate |
|------|----------|
| Handle empty state (no hits yet) | 1h |
| Handle loading state transitions | 1h |
| MiniMap heat colors | 1h |
| Accessibility (color blind friendly palette option) | 2h |
| Documentation | 2h |

**Total: ~7 hours**

---

## 7. Decisions (Confirmed)

| Question | Decision |
|----------|----------|
| **Tracking granularity** | Track **all top-K results** returned (no score threshold) |
| **username source** | Use `username` (alias: `ad_username`) from auth token. POC: hardcode `"default"` with `# TODO: get username from auth` |
| **session_id** | Not tracked for now (always `null`) |
| **Never-accessed visibility** | Yes — faded (opacity 0.5) with dashed border |
| **Cache staleness** | 5-minute cache acceptable for MVP |
| **Edge heat (hot paths)** | Defer to Phase 2 |

---

## 8. Future Enhancements

- **Trend indicators**: Show ↑↓ arrows for week-over-week change
- **Hot paths**: Visualize frequently co-retrieved node pairs
- **Anomaly detection**: Alert when a node suddenly gets 10x normal traffic
- **Export**: CSV/JSON export of heat data for BI tools
- **Comparison view**: Side-by-side 7d vs 30d heat
- **Drill-down**: Click node to see query breakdown (what queries led to this node)

---

## 9. Appendix

### A. Color Palette (Tailwind)

```typescript
const HEAT_COLORS = {
  never: { bg: '#f3f4f6', border: '#d1d5db', opacity: 0.5 },   // gray-100/300
  cold:  { bg: '#dbeafe', border: '#93c5fd' },                  // blue-100/300
  cool:  { bg: '#dcfce7', border: '#86efac' },                  // green-100/300
  warm:  { bg: '#fef9c3', border: '#fde047' },                  // yellow-100/300
  hot:   { bg: '#ffedd5', border: '#fdba74' },                  // orange-100/300
  fire:  { bg: '#fee2e2', border: '#fca5a5' },                  // red-100/300
}
```

### B. SQL: Full Heatmap Query

```sql
WITH period_hits AS (
    SELECT 
        node_id,
        COUNT(*) as total_hits,
        COUNT(DISTINCT session_id) as unique_sessions,
        COUNT(DISTINCT user_id) as unique_users,
        AVG(similarity_score) as avg_similarity,
        MAX(hit_at) as last_hit_at
    FROM agent.knowledge_hits
    WHERE hit_at >= NOW() - INTERVAL '7 days'
    GROUP BY node_id
),
all_published_nodes AS (
    SELECT id as node_id
    FROM agent.knowledge_nodes
    WHERE is_deleted = FALSE 
      AND status = 'published'
      AND tenant_id = ANY(:tenant_ids)
),
combined AS (
    SELECT 
        n.node_id,
        COALESCE(h.total_hits, 0) as total_hits,
        COALESCE(h.unique_sessions, 0) as unique_sessions,
        COALESCE(h.unique_users, 0) as unique_users,
        h.avg_similarity,
        h.last_hit_at
    FROM all_published_nodes n
    LEFT JOIN period_hits h ON n.node_id = h.node_id
)
SELECT 
    *,
    PERCENT_RANK() OVER (ORDER BY total_hits) as heat_score
FROM combined
ORDER BY total_hits DESC;
```
