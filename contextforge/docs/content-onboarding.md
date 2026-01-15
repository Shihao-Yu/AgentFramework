# Context Onboarding

Extract structured knowledge from raw text using LLM-powered pipelines.

## Overview

The Context Onboarding system allows users to paste unstructured text (documentation, chat logs, emails, etc.) and automatically extract structured knowledge nodes for the knowledge base. All extracted content goes to a staging queue for human review before being published.

## Supported Node Types

| Type | Description | Use Case |
|------|-------------|----------|
| **FAQ** | Question & answer pairs | Support documentation, help articles |
| **Playbook** | Step-by-step procedures | SOPs, how-to guides, workflows |
| **Concept** | Glossary/terminology definitions | Business terms, technical concepts |
| **Feature Permission** | Who can do what | Authorization rules, access controls |
| **Entity** | Named entities with attributes | Vendors, products, departments |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                 │
│  OnboardingPage.tsx ──► useOnboarding.ts ──► POST /api/onboard  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer                                   │
│  routes/onboarding.py ──► OnboardingService                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Pipeline Layer                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              OnboardingPipeline (base)                   │   │
│  │  - get_system_prompt() ──► Langfuse / local JSON        │   │
│  │  - extract() ──► LLM structured output                  │   │
│  │  - to_node_content() ──► dict for storage               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│     ┌────────┬────────┬──────┴──────┬─────────────┬─────────┐   │
│     ▼        ▼        ▼             ▼             ▼         │   │
│   FAQ    Playbook  Concept   FeaturePermission  Entity      │   │
│ Pipeline  Pipeline  Pipeline     Pipeline      Pipeline     │   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Storage Layer                                 │
│  staging_nodes table (pending review)                           │
└─────────────────────────────────────────────────────────────────┘
```

## API

### POST /api/onboard

Extract knowledge from raw text and create staging nodes.

**Request:**
```json
{
  "items": [
    {
      "text": "How do I reset my password? Go to Settings > Security > Reset Password.",
      "node_types": ["FAQ"]
    },
    {
      "text": "Vendor Onboarding: 1. Submit application 2. Review by procurement 3. Approval",
      "node_types": ["PLAYBOOK", "FAQ"]
    }
  ],
  "tenant_id": "purchasing",
  "source_tag": "confluence-import"
}
```

**Response:**
```json
{
  "created": 3,
  "staging_ids": [101, 102, 103]
}
```

**Notes:**
- Each item can target multiple node types (e.g., extract as both FAQ and Playbook)
- All extracted content goes to staging with `status='pending'` and `action='new'`
- The `source_tag` is optional, useful for tracking import batches

## Backend Components

### File Structure

```
contextforge/app/
├── onboarding/
│   ├── __init__.py              # Module exports
│   ├── base.py                  # OnboardingPipeline base class
│   ├── models.py                # Pydantic extraction models
│   ├── faq_pipeline.py          # FAQ extraction
│   ├── playbook_pipeline.py     # Playbook extraction
│   ├── concept_pipeline.py      # Concept extraction
│   ├── feature_permission_pipeline.py
│   └── entity_pipeline.py       # Entity extraction
├── prompts/
│   ├── onboarding_faq_extraction.json
│   ├── onboarding_playbook_extraction.json
│   ├── onboarding_concept_extraction.json
│   ├── onboarding_feature_permission_extraction.json
│   └── onboarding_entity_extraction.json
├── routes/
│   └── onboarding.py            # API endpoint
├── services/
│   └── onboarding_service.py    # Orchestration service
└── schemas/
    └── onboarding.py            # Request/response schemas
```

### Base Pipeline

All pipelines inherit from `OnboardingPipeline[T]`:

```python
class OnboardingPipeline(ABC, Generic[T]):
    node_type: str           # "FAQ", "PLAYBOOK", etc.
    extraction_model: Type[T]  # Pydantic model for structured output
    prompt_name: str         # Langfuse prompt name

    async def extract(self, text: str) -> tuple[str, dict, list[str], float]:
        """Returns (title, content, tags, confidence)"""

    @abstractmethod
    def to_node_content(self, extraction: T) -> dict:
        """Convert extraction to node content dict"""

    @abstractmethod
    def get_title(self, extraction: T) -> str:
        """Extract title from extraction"""

    @abstractmethod
    def get_tags(self, extraction: T) -> list[str]:
        """Extract tags from extraction"""
```

### Extraction Models

Each node type has a Pydantic model defining the expected LLM output:

```python
# FAQ
class FAQExtraction(BaseModel):
    question: str
    answer: str
    tags: list[str]
    confidence: float  # 0.0 to 1.0

# Playbook
class PlaybookExtraction(BaseModel):
    title: str
    description: str
    prerequisites: list[str]
    steps: list[PlaybookStep]
    tags: list[str]
    confidence: float

# Concept
class ConceptExtraction(BaseModel):
    term: str
    definition: str
    aliases: list[str]
    examples: list[str]
    tags: list[str]
    confidence: float

# Feature Permission
class FeaturePermissionExtraction(BaseModel):
    feature: str
    rules: list[PermissionRule]  # role, action, condition
    conditions: list[str]
    tags: list[str]
    confidence: float

# Entity
class EntityExtraction(BaseModel):
    name: str
    entity_type: str  # Vendor, Product, Department, etc.
    attributes: dict[str, str]
    tags: list[str]
    confidence: float
```

### Prompt Management

Prompts are managed via Langfuse with local JSON fallbacks:

1. **Langfuse (primary)**: Prompts can be edited in Langfuse dashboard
2. **Local JSON (fallback)**: Files in `app/prompts/` serve as defaults

Prompt JSON format:
```json
{
  "name": "onboarding_faq_extraction",
  "prompt": "You are a knowledge extraction assistant...",
  "config": {
    "model": "gpt-4o-mini",
    "temperature": 0.3
  }
}
```

The `LangfuseClient.get_prompt_template()` method tries Langfuse first, then falls back to local JSON.

## Frontend Components

### OnboardingPage.tsx

Main UI for Context Onboarding:
- Multiple content boxes with text input
- Node type selection (toggle badges)
- Source tag field for batch tracking
- Submit to extract and stage

### useOnboarding.ts

React hook for the onboarding API:
```typescript
const { onboard, isLoading, error } = useOnboarding()

const response = await onboard({
  items: [{ text: '...', node_types: ['FAQ'] }],
  tenant_id: 'default',
  source_tag: 'manual'
})
```

## Workflow

1. **User pastes content** in the Onboarding page
2. **Selects node type(s)** to extract (FAQ, Playbook, etc.)
3. **Clicks "Extract & Stage"**
4. **Backend processes each item:**
   - Runs appropriate pipeline for each node type
   - LLM extracts structured data using prompt + Pydantic schema
   - Creates staging node with `status='pending'`
5. **User reviews** in Staging Queue
6. **Approves or rejects** each item
7. **Approved items** become published knowledge nodes

## Adding New Node Types

1. **Create extraction model** in `app/onboarding/models.py`:
   ```python
   class NewTypeExtraction(BaseModel):
       # Define fields with Field() descriptions
       confidence: float = Field(ge=0, le=1)
   ```

2. **Create pipeline** in `app/onboarding/new_type_pipeline.py`:
   ```python
   class NewTypePipeline(OnboardingPipeline[NewTypeExtraction]):
       node_type = "NEW_TYPE"
       extraction_model = NewTypeExtraction
       prompt_name = "onboarding_new_type_extraction"

       def to_node_content(self, extraction): ...
       def get_title(self, extraction): ...
       def get_tags(self, extraction): ...
   ```

3. **Create prompt** in `app/prompts/onboarding_new_type_extraction.json`

4. **Register in service** in `app/services/onboarding_service.py`:
   ```python
   PIPELINE_MAP = {
       ...
       "NEW_TYPE": NewTypePipeline,
   }
   ```

5. **Export from module** in `app/onboarding/__init__.py`

6. **Add to frontend** in `OnboardingPage.tsx`:
   ```typescript
   const NODE_TYPES = [
     ...
     { value: 'NEW_TYPE', label: 'New Type' },
   ]
   ```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_SCHEMA` | PostgreSQL schema name | `agent` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse API key (optional) | - |
| `LANGFUSE_SECRET_KEY` | Langfuse secret (optional) | - |

## Testing

```bash
# Run onboarding tests
cd contextforge
source .venv/bin/activate
pytest tests/app/test_onboarding.py -v
```

Tests cover:
- Extraction model validation
- Pipeline attribute verification
- Prompt loading from Langfuse/fallback
- Content conversion methods
- API schema validation
