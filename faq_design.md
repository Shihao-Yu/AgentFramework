can you please help me review this design? any potential issues?
 

````markdown
# FAQ/Ticketing FAQ System Architecture

## System Overview

A comprehensive knowledge base system that automatically extracts Q&A pairs from support tickets and manages them through a staging-to-production workflow with embedding-based similarity search.

## Architecture Diagram

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   ClickHouse    │────▶│ Pipeline Job     │────▶│ Staging Table       │
│  (Raw Tickets)  │     │ (ticketing_kb_   │     │ (staging_purchasing_│
│                 │     │  pipeline_job)   │     │  faq)               │
└─────────────────┘     └────────┬─────────┘     └──────────┬──────────┘
                                 │                         │
                                 │                         ▼
                                 │              ┌─────────────────────┐
                                 │              │  Review Workflow    │
                                 │              │  (approve/reject)   │
                                 │              └──────────┬──────────┘
                                 │                         │
                                 ▼                         ▼
                        ┌──────────────────┐     ┌─────────────────────┐
                        │ TicketToKBPipeline│     │  Production Table   │
                        │  (ticket similarity│     │  (purchasing_faq)   │
                        │   analysis + LLM) │     │                     │
                        └────────┬─────────┘     └──────────▲──────────┘
                                 │                        │
                                 │                        │
                                 ▼                        │
                        ┌──────────────────┐              │
                        │ pgvector Search  │◀─────────────┘
                        │ (similarity)     │
                        └────────┬─────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │ Agent Framework  │
                        │ KB Retriever     │
                        └──────────────────┘
```

## Directory Structure

```
purchasing.ai/
├── jobs/
│   └── ticketing_kb_pipeline_job.py      # Scheduled pipeline job
├── services/
│   ├── ticketing_kb_pipeline_service.py  # Core pipeline logic
│   ├── ticketing_faq_service.py          # Staging review workflow
│   └── faq_service.py                    # Production FAQ CRUD
├── models/
│   └── entities/
│       └── ticketing_faq.py              # SQLModel entities
├── apis/
│   └── routes/
│       └── ticketing_faq.py              # REST API endpoints
└── agents/
    └── adapters/
        └── knowledge.py                  # Agent KB retriever
```

## Data Flow Pipeline

### Phase 1: Ticket Ingestion

**File:** `jobs/ticketing_kb_pipeline_job.py`

**Class:** `TicketingKBPipelineJob`

Fetches resolved tickets from ClickHouse and processes them through the pipeline.

```python
async def run(
    self,
    lookback_days: int = 7,
    limit: Optional[int] = None
) -> PipelineStats:
```

**Data Source Query:**
```sql
SELECT id, body, closurenotes, category, subcategory1, subject, status
FROM ticketing.tickets
WHERE status IN ('Closed', 'Resolved')
  AND body IS NOT NULL AND body != ''
  AND length(body) >= 30
  AND length(closurenotes) >= 30
ORDER BY id DESC
LIMIT 1000
```

**Pre-Filter Conditions:**
- Status must be "Closed" or "Resolved"
- Body length >= 30 characters
- Closure notes length >= 30 characters
- Maximum 1000 tickets per run

### Phase 2: Ticket Analysis

**File:** `services/ticketing_kb_pipeline_service.py`

**Class:** `TicketToKBPipeline`

Core pipeline that transforms tickets into FAQ candidates.

```python
async def process_tickets(
    self,
    tickets: List[TicketData]
) -> PipelineStats:
```

**Processing Steps:**

1. **Duplicate Check** - Skip if ticket already in staging
   ```python
   if await self._check_already_staged(ticket.id):
       stats.skipped_duplicate += 1
       continue
   ```

2. **Pre-Filter Validation**
   ```python
   VALID_STATUSES = {"Closed", "Resolved"}
   MIN_BODY_LENGTH = 30
   MIN_CLOSURE_NOTES_LENGTH = 30
   ```

3. **Similarity Search** - Find similar existing FAQs
   ```python
   query_text = f"{ticket.subject}\n{ticket.body}\n{ticket.closurenotes}"
   similar_faqs = await self.similarity_service.find_similar_faqs(query_text)
   ```

4. **High Similarity Skip** - Skip if >95% similar
   ```python
   SIMILARITY_SKIP_THRESHOLD = 0.95
   if similar_faqs and similar_faqs[0].similarity >= 0.95:
       stats.skipped_identical += 1
       continue
   ```

5. **LLM Analysis** - Structured inference decides action
   ```python
   result = await self._analyze_ticket(ticket, similar_faqs)
   ```

6. **PII Sanitization** - Detect and reject PII
   ```python
   _PII_EMAIL_RE = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
   _PII_PHONE_RE = r"\b(?:\+?\d{1,3}[-.\s()]*)?(?:\d{3}[-.\s()]*){2}\d{4}\b"
   ```

7. **Staging Insert** - Valid results → `StagingPurchasingFAQ`

### Phase 3: Review & Approval

**File:** `services/ticketing_faq_service.py`

**Class:** `TicketingFAQService`

Manages staging FAQ lifecycle with human-in-the-loop review.

**Core Operations:**

| Method | Description |
|--------|-------------|
| `list_staging_faqs()` | Paginated list with status filter |
| `get_stats()` | Staging statistics by status |
| `update_faq()` | Edit pending FAQ, regenerate embedding |
| `review_faq()` | Approve/reject with auto-sync |
| `get_existing_faq_for_merge()` | Preview merge target |

**Status Workflow:**

```
PENDING ──────approve──────▶ APPROVED ──────sync──────▶ Production
       ◀──────reject───────        ◀──────reject───────
```

**Review Process:**
```python
async def review_faq(
    self,
    faq_id: int,
    status: str,  # approved/rejected
    reviewed_by: str
) -> Dict[str, Any]:
```

**Auto-Sync on Approval:**
- NEW entries → Insert to `PurchasingFAQ`
- MERGE entries → Update existing `PurchasingFAQ`
- Snapshot captured for merge audit trail

### Phase 4: Knowledge Retrieval

**File:** `agents/adapters/knowledge.py`

**Class:** `PurchasingKnowledgeRetriever`

Agent framework integration for RAG-based FAQ retrieval.

```python
@kb_spec(
    id="purchasing_kb",
    name="Purchasing Knowledge Base",
    source_type="postgresql"
)
class PurchasingKnowledgeRetriever(KnowledgeRetriever):
```

**Retrieval Query:**
```sql
SELECT id, question, answer, tags,
       1 - (embedding <=> :embedding) AS cosine_similarity
FROM agent.purchasing_faq
WHERE embedding IS NOT NULL
ORDER BY embedding <=> :embedding
LIMIT :top_k
```

## Database Schemas

### Staging Table: `agent.staging_purchasing_faq`

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `question` | TEXT | FAQ question (optional for MERGE) |
| `answer` | TEXT | FAQ answer |
| `tags` | VARCHAR | Comma-separated tags |
| `embedding` | VECTOR(1024) | pgvector embedding |
| `source_ticket_id` | VARCHAR | Original ticket ID |
| `confidence` | FLOAT | LLM confidence score |
| `status` | VARCHAR | PENDING/APPROVED/REJECTED |
| `action` | VARCHAR | NEW/MERGE |
| `merge_with_id` | INT | Target FAQ for merge |
| `similarity` | FLOAT | Similarity to merge target |
| `reviewed_by` | VARCHAR | Reviewer username |
| `reviewed_at` | TIMESTAMP | Review timestamp |
| `metadata_` | JSONB | Audit trail, snapshots |

**SQLModel Definition:**
```python
class StagingPurchasingFAQ(AuditMixin, table=True):
    __tablename__ = "staging_purchasing_faq"
    __table_args__ = {"schema": "agent"}

    id: Optional[int] = Field(default=None, primary_key=True)
    question: str = Field(sa_type=Text)
    answer: str = Field(sa_type=Text)
    tags: str
    embedding: List[float] = Field(sa_column=Column(AsyncpgVector(1024)))
    source_ticket_id: str
    confidence: float
    status: str = Field(default=StagingStatus.PENDING.value)
    action: str = Field(default=AnalysisAction.NEW.value)
    merge_with_id: Optional[int] = None
    similarity: Optional[float] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    metadata_: dict = Field(default={}, sa_column=Column("metadata", JSONB))
```

### Production Table: `agent.purchasing_faq`

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `question` | TEXT | FAQ question |
| `answer` | TEXT | FAQ answer |
| `tags` | TEXT[] | Array of tags |
| `embedding` | VECTOR(1024) | pgvector embedding |
| `metadata_` | JSONB | Source tracking, audit |

**SQLModel Definition:**
```python
class PurchasingFAQ(AuditMixin, table=True):
    __tablename__ = "purchasing_faq"
    __table_args__ = {"schema": "agent"}

    id: Optional[int] = Field(default=None, primary_key=True)
    question: str = Field(sa_type=Text)
    answer: str = Field(sa_type=Text)
    tags: List[str] = Field(default=[], sa_column=Column(ARRAY(SAText)))
    embedding: List[float] = Field(sa_column=Column(AsyncpgVector(1024)))
    metadata_: dict = Field(default={}, sa_column=Column("metadata", JSONB))
```

### Raw Tickets: `ticketing.tickets` (ClickHouse)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Ticket ID |
| `body` | TEXT | Ticket description |
| `closurenotes` | TEXT | Resolution notes |
| `category` | VARCHAR | Ticket category |
| `subcategory1` | VARCHAR | Subcategory |
| `subject` | VARCHAR | Ticket subject |
| `status` | VARCHAR | Ticket status |

## Key Processing Rules

### Pre-Filter Conditions

```python
VALID_STATUSES = {"Closed", "Resolved"}
MIN_BODY_LENGTH = 30  # characters
MIN_CLOSURE_NOTES_LENGTH = 30  # characters
```

### Similarity Threshold

```python
SIMILARITY_SKIP_THRESHOLD = 0.95  # Skip if >95% similar
```

### LLM Decision Categories

| Action | Description |
|--------|-------------|
| **SKIP** | Low quality, PII detected, insufficient content |
| **NEW** | Unique question-answer pair |
| **MERGE** | Similar existing FAQ with supplemental answer |

### PII Detection Patterns

```python
_PII_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PII_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s()]*)?(?:\d{3}[-.\s()]*){2}\d{4}\b")
_SKIP_REASON_PII = "Skipped: potential personal/user-identifying information detected"
```

## Service Dependencies

```
TicketingKBPipelineJob
    ├── get_ticketing_kb_pipeline_service() → TicketToKBPipeline
    │       ├── StructuredInferenceClient (LLM)
    │       ├── EmbeddingClient
    │       ├── TicketingSimilarityService
    │       └── async_sessionmaker (PostgreSQL)
    └── get_clickhouse_client() → Raw tickets

TicketingFAQService
    ├── async_sessionmaker (PostgreSQL)
    ├── EmbeddingClient
    └── PurchasingFAQ/StagingPurchasingFAQ entities

PurchasingKnowledgeRetriever
    ├── get_embedding_client()
    └── get_async_session_maker() → pgvector similarity search
```

## API Endpoints

### Pipeline Processing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/process` | Process tickets through pipeline |

**Request:**
```json
{
  "tickets": [
    {
      "id": "12345",
      "body": "...",
      "closurenotes": "...",
      "category": "...",
      "subcategory1": "...",
      "subject": "...",
      "status": "Closed"
    }
  ]
}
```

**Response:**
```json
{
  "processed": 100,
  "staged_new": 15,
  "staged_merge": 5,
  "skipped_prefilter": 20,
  "skipped_duplicate": 10,
  "skipped_identical": 30,
  "skipped_unsuitable": 20
}
```

### Staging Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/staging-faq` | List staging FAQs (paginated, filterable) |
| GET | `/staging-faq/stats` | Staging statistics |
| PUT | `/staging-faq/{id}` | Update staging FAQ |
| POST | `/staging-faq/{id}/review` | Approve/reject (JWT required) |
| GET | `/staging-faq/{id}/existing` | Preview merge target |

**Query Parameters for List:**
- `status` (optional): Filter by PENDING/APPROVED/REJECTED
- `limit` (default: 50): Maximum entries to return (1-1000)
- `offset` (default: 0): Number of entries to skip

**Update Request:**
```json
{
  "question": "Updated question?",
  "answer": "Updated answer.",
  "tags": "tag1,tag2,tag3"
}
```

**Review Request:**
```json
{
  "status": "approved",
  "reviewed_by": "user@example.com"  // Ignored, extracted from JWT
}
```

## Audit & Tracking

### Production FAQ Metadata

```json
{
  "source_staging_id": 123,
  "source_ticket_id": "TKT-456",
  "promoted_at": "2024-01-11T02:42:05",
  "promoted_by": "reviewer@example.com"
}
```

### Merge Snapshot (in staging metadata)

```json
{
  "original_faq_before_merge": {
    "id": 100,
    "question": "Original question?",
    "answer": "Original answer.",
    "tags": ["tag1", "tag2"],
    "captured_at": "2024-01-11T02:42:05"
  },
  "promoted_to_faq_id": 100,
  "promoted_at": "2024-01-11T02:42:05"
}
```

### Audit Fields (from AuditMixin)

| Field | Type | Description |
|-------|------|-------------|
| `created_by` | VARCHAR | Creator username |
| `created_at` | TIMESTAMP | Creation timestamp |
| `updated_by` | VARCHAR | Last updater username |
| `updated_at` | TIMESTAMP | Last update timestamp |
| `is_deleted` | BOOLEAN | Soft delete flag |

## Key Design Patterns

### 1. Staging-Production Split

Human-in-the-loop review before production deployment ensures quality control.

### 2. Embedding-First Search

pgvector enables efficient cosine similarity matching for:
- Duplicate detection
- Merge suggestions
- Semantic search

### 3. Soft Deletes

`is_deleted` flag maintains audit trail and data integrity without physical deletion.

### 4. Audit Mixin

Automatic population of audit fields:
```python
class AuditMixin:
    created_by: Optional[str] = Field(default=None, nullable=False)
    created_at: Optional[datetime] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    is_deleted: bool = Field(default=False)
```

### 5. Safe Method Decorator

Exception handling with logging and default values:
```python
@safe_method(logger, default=[])
async def list_faqs(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
```

### 6. Async ORM

SQLModel async sessions for database concurrency:
```python
async with self.session_maker() as session:
    result = await session.execute(statement)
    faqs = result.scalars().all()
```

## Pipeline Statistics

The pipeline tracks comprehensive metrics:

| Statistic | Description |
|-----------|-------------|
| `processed` | Total tickets processed |
| `staged_new` | Tickets staged as new FAQ entries |
| `staged_merge` | Tickets staged for merge |
| `skipped_prefilter` | Failed pre-filter validation |
| `skipped_duplicate` | Already in staging |
| `skipped_identical` | High similarity to existing FAQ |
| `skipped_unsuitable` | LLM rejected as unsuitable |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_FAQ_SCHEMA` | `agent` | PostgreSQL schema for FAQ tables |
| `POSTGRES_FAQ_TABLE` | `purchasing_faq` | Production FAQ table name |
| `KB_TOP_K` | `5` | Number of similar FAQs to return |

### Constants

**File:** `models/constants/ticketing.py`

```python
STAGING_FAQ_TABLE_NAME = "staging_purchasing_faq"
FAQ_TABLE_NAME = "purchasing_faq"
TICKETING_DATABASE_NAME = "ticketing"
RAW_TICKETS_TABLE_NAME = "tickets"
MIN_BODY_LENGTH = 30
MIN_CLOSURE_NOTES_LENGTH = 30
SIMILARITY_SKIP_THRESHOLD = 0.95
TICKET_KB_ANALYSIS_PROMPT_NAME = "ticket_kb_analysis"
```

## Usage Examples

### Running Pipeline Job

```bash
# Via Python script
python purchasing.ai/jobs/ticketing_kb_pipeline_job.py [lookback_days] [limit]

# Via API
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"tickets": [...]}'
```

### Managing Staging FAQs

```python
# List pending FAQs
await service.list_staging_faqs(status="PENDING", limit=50)

# Get statistics
await service.get_stats()
# Returns: {"PENDING": 10, "APPROVED": 100, "REJECTED": 5}

# Review FAQ
await service.review_faq(faq_id=123, status="approved", reviewed_by="admin")
```

## Error Handling

### Safe Method Decorator

All service methods use `@safe_method` for:
- Automatic exception logging
- Default value returns
- Request isolation (one failure doesn't cascade)

### Validation

- LLM responses validated before staging insert
- Merge requires `merge_with_id`
- NEW requires `question`, `answer`, `tags`
- Only PENDING entries editable

---

*Generated: 2024-01-11*
*System: purchasing.ai FAQ/Ticketing KB Pipeline*
````