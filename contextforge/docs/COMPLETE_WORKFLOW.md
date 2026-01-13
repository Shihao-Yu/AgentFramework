# ContextForge Complete Workflow Guide

This guide provides a comprehensive end-to-end workflow for using ContextForge, from initial setup through production operations and continuous improvement.

## Workflow Overview

The ContextForge lifecycle consists of five interconnected phases:

1. **Initial Setup & Onboarding** - Database setup and first dataset registration
2. **First Query Generation** - Generate queries from natural language questions
3. **Example Collection & Learning** - Build knowledge base with verified examples
4. **Continuous Improvement** - Refine and enhance query generation quality
5. **Production Operations** - Multi-tenant, multi-dataset production deployment

Each phase builds upon the previous one, creating a continuous improvement cycle that enhances query generation quality over time.

---

## Phase 1: Initial Setup & Onboarding

### Step 1.1: Database Setup

Initialize PostgreSQL with vector extension support:

```bash
# Create database
createdb contextforge

# Enable vector extension
psql -d contextforge -c "CREATE EXTENSION vector;"

# Run migrations
alembic upgrade head
```

### Step 1.2: Service Initialization

Initialize the QueryForge service with required dependencies:

```python
from app.services.queryforge_service import QueryForgeService
from app.db.session import get_db_session
from app.clients.embedding_client import EmbeddingClient
from app.clients.llm_client import LLMClient

# Initialize clients
embedding_client = EmbeddingClient()
llm_client = LLMClient()

# Create service instance
service = QueryForgeService(
    session=db_session,
    embedding_client=embedding_client,
    llm_client=llm_client,
)
```

### Step 1.3: Onboard First Dataset

Register your first dataset with schema information:

```python
# Define your database schema
DDL = """
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER,
    status VARCHAR(50),
    total_amount DECIMAL(10,2),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
"""

# Onboard the dataset
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders",
    source_type="postgres",
    raw_schema=DDL,
    description="E-commerce orders database containing customer order information",
)

print(f"Dataset onboarded: {result['dataset_id']}")
print(f"Schema nodes created: {len(result['schema_nodes'])}")
```

**What happens during onboarding:**
- Schema is parsed and stored as KnowledgeNodes
- Table and column metadata is extracted
- Embeddings are generated for semantic search
- Dataset is ready for query generation

---

## Phase 2: First Query Generation

### Step 2.1: Generate Query from Natural Language

Use the service to convert questions into queries:

```python
# Generate a SQL query
result = await service.generate_query(
    tenant_id="acme",
    dataset_name="orders",
    question="Show all pending orders",
)

print(f"Generated Query: {result['query']}")
# Output: SELECT * FROM orders WHERE status = 'pending'

print(f"Confidence: {result['confidence']}")
print(f"Similar Examples Used: {len(result['similar_examples'])}")
```

### Step 2.2: Verify Results

Execute and verify the generated query:

```python
# Execute the query against your database
import psycopg2

conn = psycopg2.connect("dbname=your_db")
cursor = conn.cursor()
cursor.execute(result['query'])
rows = cursor.fetchall()

# Verify correctness
print(f"Returned {len(rows)} rows")
# Review results to ensure query is correct
```

### Step 2.3: Handle Generation Issues

If the query is incorrect or needs improvement:

```python
# Note the issue for later improvement
issues = {
    "question": "Show all pending orders",
    "generated_query": result['query'],
    "issue": "Should filter by created_at in last 30 days",
    "correct_query": "SELECT * FROM orders WHERE status = 'pending' AND created_at > NOW() - INTERVAL '30 days'"
}
# This will be added as an example in Phase 3
```

---

## Phase 3: Example Collection & Learning

### Step 3.1: Add Verified Examples

Build your knowledge base with verified question-query pairs:

```python
# Add a verified example
await service.add_example(
    tenant_id="acme",
    dataset_name="orders",
    question="Show pending orders from the last 30 days",
    query="SELECT * FROM orders WHERE status = 'pending' AND created_at > NOW() - INTERVAL '30 days'",
    query_type="sql",
    verified=True,
    metadata={
        "category": "order_status",
        "complexity": "medium",
    }
)
```

### Step 3.2: Add Question Variants

Add variations of common questions to improve matching:

```python
# Add variants for the same query pattern
variants = [
    "List orders that are pending",
    "Get unprocessed orders",
    "Pending order report",
    "Show me orders waiting to be processed",
    "What orders haven't been completed yet",
]

base_query = "SELECT * FROM orders WHERE status = 'pending'"

for question in variants:
    await service.add_example(
        tenant_id="acme",
        dataset_name="orders",
        question=question,
        query=base_query,
        query_type="sql",
        verified=True,
    )
```

### Step 3.3: Add Complex Examples

Include examples for complex queries:

```python
# Complex aggregation example
await service.add_example(
    tenant_id="acme",
    dataset_name="orders",
    question="What is the total revenue by customer for orders over $100?",
    query="""
        SELECT 
            customer_id,
            SUM(total_amount) as total_revenue,
            COUNT(*) as order_count
        FROM orders
        WHERE total_amount > 100
        GROUP BY customer_id
        ORDER BY total_revenue DESC
    """,
    query_type="sql",
    verified=True,
    metadata={"category": "analytics", "complexity": "high"}
)
```

### Step 3.4: Review Staging Queue

Check unverified examples that were auto-generated:

```python
# List examples in staging
staging_examples = await service.list_examples(
    tenant_id="acme",
    dataset_name="orders",
    verified=False,
)

for example in staging_examples:
    print(f"Question: {example['question']}")
    print(f"Query: {example['query']}")
    print(f"Needs review: {example['id']}")
    print("---")
```

---

## Phase 4: Continuous Improvement

### Step 4.1: Monitor Usage Patterns

Track which questions are being asked:

```python
# Get all examples to analyze patterns
examples = await service.list_examples(
    tenant_id="acme",
    dataset_name="orders",
)

# Analyze question categories
from collections import Counter

categories = Counter(
    ex.get('metadata', {}).get('category', 'uncategorized')
    for ex in examples
)

print("Question distribution:")
for category, count in categories.most_common():
    print(f"  {category}: {count}")
```

### Step 4.2: Verify Staged Examples

Review and verify examples from the staging queue:

```python
# Review a staged example
example = staging_examples[0]

# Test the query
cursor.execute(example['query'])
results = cursor.fetchall()

# If correct, verify it
if results_are_correct:
    await service.verify_example(
        example_id=example['id'],
        verified=True
    )
else:
    # Update with correct query
    await service.update_example(
        example_id=example['id'],
        query=corrected_query,
        verified=True
    )
```

### Step 4.3: Re-onboard with Enrichment

Enhance schema understanding with LLM-generated descriptions:

```python
# Re-onboard with enrichment enabled
result = await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders",
    source_type="postgres",
    raw_schema=DDL,
    description="E-commerce orders database",
    enable_enrichment=True,  # LLM enhances column descriptions
)

print(f"Enriched schema nodes: {len(result['schema_nodes'])}")
```

### Step 4.4: Add Domain-Specific Context

Enhance datasets with business context:

```python
# Add business rules as examples
await service.add_example(
    tenant_id="acme",
    dataset_name="orders",
    question="Show high-value orders",
    query="SELECT * FROM orders WHERE total_amount > 1000",
    query_type="sql",
    verified=True,
    metadata={
        "business_rule": "High-value threshold is $1000",
        "category": "business_logic"
    }
)
```

---

## Phase 5: Production Operations

### Step 5.1: Multi-Dataset Setup

Manage multiple datasets for a tenant:

```python
# Onboard additional datasets
await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="customers",
    source_type="postgres",
    raw_schema=CUSTOMER_DDL,
    description="Customer information and profiles",
)

await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="products",
    source_type="postgres",
    raw_schema=PRODUCT_DDL,
    description="Product catalog and inventory",
)

# List all datasets
datasets = await service.list_datasets(tenant_id="acme")
for dataset in datasets:
    print(f"Dataset: {dataset['name']}")
    print(f"  Tables: {dataset['table_count']}")
    print(f"  Examples: {dataset['example_count']}")
```

### Step 5.2: Dataset Routing

Let ContextForge automatically select the right dataset:

```python
# Question about orders - routes to orders dataset
result = await service.generate_query(
    tenant_id="acme",
    dataset_name="orders",  # Explicit routing
    question="Show pending orders",
)

# For multi-dataset queries, use explicit dataset selection
# or implement custom routing logic based on question analysis
```

### Step 5.3: Monitoring and Metrics

Track system performance:

```python
# Get dataset statistics
stats = await service.get_dataset_stats(
    tenant_id="acme",
    dataset_name="orders",
)

print(f"Total examples: {stats['total_examples']}")
print(f"Verified examples: {stats['verified_examples']}")
print(f"Staging queue: {stats['staging_count']}")
print(f"Success rate: {stats['success_rate']}%")
```

### Step 5.4: Error Handling

Implement robust error handling for production:

```python
from app.exceptions import QueryGenerationError, DatasetNotFoundError

try:
    result = await service.generate_query(
        tenant_id="acme",
        dataset_name="orders",
        question=user_question,
    )
    
    # Validate confidence threshold
    if result['confidence'] < 0.7:
        # Log low confidence for review
        logger.warning(f"Low confidence query: {result['confidence']}")
        # Optionally prompt user for verification
    
    return result['query']
    
except DatasetNotFoundError:
    # Handle missing dataset
    return "Dataset not found. Please check dataset name."
    
except QueryGenerationError as e:
    # Handle generation failure
    logger.error(f"Query generation failed: {e}")
    return "Unable to generate query. Please rephrase your question."
```

---

## Improvement Cycle

The ContextForge improvement cycle is continuous:

```
Generate Query → Execute & Verify → Add Example → Verify Example → Improve Quality
       ↑                                                                    |
       +--------------------------------------------------------------------+
```

### Cycle Steps:

1. **Generate Query**: User asks a question, system generates query
2. **Execute & Verify**: User executes query and verifies correctness
3. **Add Example**: Correct query is added to knowledge base
4. **Verify Example**: Example is reviewed and verified
5. **Improve Quality**: Future similar questions benefit from the example

### Metrics to Track:

- **Query Success Rate**: Percentage of queries that are correct on first generation
- **Example Growth**: Number of verified examples over time
- **Coverage**: Percentage of question types with verified examples
- **Confidence Trends**: Average confidence scores over time

---

## Best Practices

### 1. Start with Core Examples

Begin with 5-10 verified examples per dataset covering common use cases:

```python
core_examples = [
    ("Show all records", "SELECT * FROM orders"),
    ("Count total records", "SELECT COUNT(*) FROM orders"),
    ("Filter by status", "SELECT * FROM orders WHERE status = 'pending'"),
    ("Recent records", "SELECT * FROM orders WHERE created_at > NOW() - INTERVAL '7 days'"),
    ("Aggregate by field", "SELECT status, COUNT(*) FROM orders GROUP BY status"),
]

for question, query in core_examples:
    await service.add_example(
        tenant_id="acme",
        dataset_name="orders",
        question=question,
        query=query,
        query_type="sql",
        verified=True,
    )
```

### 2. Add Variants for Common Questions

For frequently asked questions, add multiple phrasings:

```python
# Same query, different phrasings
common_query = "SELECT * FROM orders WHERE status = 'pending'"
phrasings = [
    "Show pending orders",
    "List orders that are pending",
    "Get unprocessed orders",
    "Pending order report",
    "What orders are waiting",
]
```

### 3. Re-onboard Schemas Periodically

Update schema understanding when database changes:

```python
# After schema changes, re-onboard with enrichment
await service.onboard_dataset(
    tenant_id="acme",
    dataset_name="orders",
    source_type="postgres",
    raw_schema=UPDATED_DDL,
    description="Updated schema with new columns",
    enable_enrichment=True,
)
```

### 4. Review Staging Queue Daily

Make it a habit to review and verify staged examples:

```python
# Daily review script
async def daily_review():
    staging = await service.list_examples(
        tenant_id="acme",
        dataset_name="orders",
        verified=False,
    )
    
    print(f"Staging queue: {len(staging)} examples to review")
    
    for example in staging[:10]:  # Review top 10
        print(f"\nQuestion: {example['question']}")
        print(f"Query: {example['query']}")
        # Manual review and verification
```

### 5. Monitor Query Quality Metrics

Track and improve quality over time:

```python
# Weekly quality report
async def quality_report():
    stats = await service.get_dataset_stats(
        tenant_id="acme",
        dataset_name="orders",
    )
    
    print("Weekly Quality Report")
    print(f"  Success Rate: {stats['success_rate']}%")
    print(f"  Verified Examples: {stats['verified_examples']}")
    print(f"  Avg Confidence: {stats['avg_confidence']}")
    print(f"  Staging Queue: {stats['staging_count']}")
    
    # Set improvement goals
    if stats['success_rate'] < 90:
        print("  Goal: Add more examples for low-confidence queries")
```

### 6. Use Metadata for Organization

Tag examples with metadata for better organization:

```python
await service.add_example(
    tenant_id="acme",
    dataset_name="orders",
    question="Revenue by customer",
    query="SELECT customer_id, SUM(total_amount) FROM orders GROUP BY customer_id",
    query_type="sql",
    verified=True,
    metadata={
        "category": "analytics",
        "complexity": "medium",
        "department": "finance",
        "frequency": "daily",
    }
)
```

### 7. Document Business Rules

Capture domain knowledge in examples:

```python
# Business rule: VIP customers have orders > $10,000 total
await service.add_example(
    tenant_id="acme",
    dataset_name="orders",
    question="Show VIP customers",
    query="""
        SELECT customer_id, SUM(total_amount) as total
        FROM orders
        GROUP BY customer_id
        HAVING SUM(total_amount) > 10000
    """,
    query_type="sql",
    verified=True,
    metadata={
        "business_rule": "VIP threshold is $10,000 total orders",
    }
)
```

---

## Troubleshooting

### Low Confidence Scores

If queries consistently have low confidence:

1. Add more verified examples for similar questions
2. Re-onboard schema with enrichment enabled
3. Review and verify staged examples
4. Add question variants for common patterns

### Incorrect Query Generation

If generated queries are incorrect:

1. Add the correct query as a verified example
2. Check schema accuracy in KnowledgeNodes
3. Review similar examples being used
4. Add more context in dataset description

### Slow Query Generation

If generation is slow:

1. Check embedding generation performance
2. Review number of examples (optimize if > 1000)
3. Ensure database indexes are optimized
4. Consider caching for frequent questions

---

## Summary

The ContextForge workflow is designed for continuous improvement:

1. **Start Simple**: Onboard dataset, generate first queries
2. **Build Knowledge**: Add verified examples as you go
3. **Improve Quality**: Review staging queue, add variants
4. **Scale Up**: Multi-dataset, multi-tenant production
5. **Monitor & Refine**: Track metrics, optimize continuously

By following this workflow, query generation quality improves over time as the system learns from verified examples and user feedback.
