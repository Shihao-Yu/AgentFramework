#!/usr/bin/env python3
"""
ContextForge Complete Workflow Example

Demonstrates the end-to-end usage of ContextForge for:
1. Service initialization with database connection
2. Dataset onboarding (PostgreSQL schema parsing and storage)
3. Query generation from natural language questions
4. Adding and verifying Q&A examples
5. Dataset management (listing, details, deletion)

Prerequisites:
- PostgreSQL 15+ with pgvector extension installed
- Database configured via environment variables or .env file
- Required tables created via alembic migrations

Usage:
    cd contextforge
    python examples/complete_workflow.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (asyncpg driver)
                  Example: postgresql+asyncpg://user:pass@localhost:5432/contextforge
"""

import asyncio
import os
import sys
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv


# -----------------------------------------------------------------------------
# Sample Data
# -----------------------------------------------------------------------------

SAMPLE_DDL = """
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    tier VARCHAR(20) DEFAULT 'standard',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(50) NOT NULL UNIQUE,
    customer_id INTEGER REFERENCES customers(id),
    status VARCHAR(20) DEFAULT 'pending',
    total_amount DECIMAL(10,2),
    currency VARCHAR(3) DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_name VARCHAR(255) NOT NULL,
    quantity INTEGER DEFAULT 1,
    unit_price DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW()
);
"""

SAMPLE_QUESTIONS = [
    "Show all pending orders",
    "Find customers by email",
    "Get total revenue by customer tier",
    "List orders created today",
    "Show orders with total amount over 1000",
]

SAMPLE_EXAMPLES = [
    {
        "question": "Show pending orders",
        "query": "SELECT * FROM orders WHERE status = 'pending'",
        "explanation": "Filters orders table by status column",
    },
    {
        "question": "Find customer by email",
        "query": "SELECT * FROM customers WHERE email = :email",
        "explanation": "Uses parameterized query for email lookup",
    },
    {
        "question": "Get order count by status",
        "query": "SELECT status, COUNT(*) as count FROM orders GROUP BY status",
        "explanation": "Aggregates orders by status with count",
    },
]


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def print_section(title: str, char: str = "-") -> None:
    """Print a section header."""
    print(f"\n{char * 50}")
    print(title)
    print(char * 50)


def print_result(result: dict, indent: int = 0) -> None:
    """Print a result dictionary with formatting."""
    prefix = "  " * indent
    for key, value in result.items():
        if value is not None:
            if isinstance(value, dict):
                print(f"{prefix}{key}:")
                print_result(value, indent + 1)
            elif isinstance(value, list) and len(value) > 5:
                print(f"{prefix}{key}: [{len(value)} items]")
            else:
                print(f"{prefix}{key}: {value}")


# -----------------------------------------------------------------------------
# Main Workflow
# -----------------------------------------------------------------------------

async def run_workflow(database_url: Optional[str] = None) -> None:
    """
    Run the complete ContextForge workflow demonstration.
    
    Args:
        database_url: Optional database URL override. If not provided,
                      uses DATABASE_URL environment variable.
    """
    # Import after path setup
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    from app.services.queryforge_service import QueryForgeService
    from app.clients.embedding_client import MockEmbeddingClient
    from app.clients.inference_client import MockInferenceClient
    
    # Database setup
    db_url = database_url or os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/faq_knowledge_base"
    )
    
    print("=" * 60)
    print("ContextForge Complete Workflow Demo")
    print("=" * 60)
    print(f"\nDatabase: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    
    # Create async engine
    engine = create_async_engine(
        db_url,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,
    )
    
    # Create async session factory
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_factory() as session:
        # Initialize clients
        # Note: Replace with real clients for production use
        embedding_client = MockEmbeddingClient()
        llm_client = MockInferenceClient()
        
        # Initialize the QueryForge service
        service = QueryForgeService(
            session=session,
            embedding_client=embedding_client,
            llm_client=llm_client,
        )
        
        # ---------------------------------------------------------------------
        # Check Service Availability
        # ---------------------------------------------------------------------
        print_section("Service Status")
        
        print(f"ContextForge available: {service.is_available()}")
        print(f"ContextForge module: {service.is_contextforge_available()}")
        print(f"QueryForge (external): {service.is_queryforge_available()}")
        
        available_sources = service.list_available_sources()
        print(f"Available sources: {', '.join(available_sources) if available_sources else 'none'}")
        
        if not service.is_available():
            error = service.get_import_error()
            print(f"\nError: {error}")
            print("Please ensure ContextForge modules are properly installed.")
            return
        
        # ---------------------------------------------------------------------
        # Step 1: Onboard Dataset
        # ---------------------------------------------------------------------
        print_section("Step 1: Onboarding Dataset")
        
        # Define dataset parameters
        tenant_id = "demo"
        dataset_name = "ecommerce"
        
        print(f"Tenant: {tenant_id}")
        print(f"Dataset: {dataset_name}")
        print(f"Source type: postgres")
        print(f"Schema length: {len(SAMPLE_DDL)} chars")
        
        result = await service.onboard_dataset(
            tenant_id=tenant_id,
            dataset_name=dataset_name,
            source_type="postgres",
            raw_schema=SAMPLE_DDL,
            description="E-commerce database with customers, orders, and order items",
            tags=["ecommerce", "demo", "orders"],
            enable_enrichment=False,  # Set True with real LLM client
            created_by="demo_user",
        )
        
        print("\nOnboarding Result:")
        print_result(result)
        
        if result.get("status") != "success":
            print(f"\nFailed to onboard dataset: {result.get('error')}")
            return
        
        schema_index_id = result.get("schema_index_id")
        field_count = result.get("field_count", 0)
        print(f"\nCreated schema index (ID: {schema_index_id}) with {field_count} fields")
        
        # ---------------------------------------------------------------------
        # Step 2: Generate Queries from Natural Language
        # ---------------------------------------------------------------------
        print_section("Step 2: Generating Queries")
        
        print("Testing query generation with sample questions...\n")
        
        for i, question in enumerate(SAMPLE_QUESTIONS, 1):
            result = await service.generate_query(
                tenant_id=tenant_id,
                dataset_name=dataset_name,
                question=question,
                include_explanation=True,
                use_pipeline=True,
            )
            
            print(f"[{i}] Q: {question}")
            
            if result.get("status") == "success":
                query = result.get("query", "N/A")
                query_type = result.get("query_type", "unknown")
                
                # Truncate long queries for display
                display_query = query[:80] + "..." if len(query) > 80 else query
                print(f"    Query: {display_query}")
                print(f"    Type: {query_type}")
                
                if result.get("confidence"):
                    print(f"    Confidence: {result.get('confidence')}")
            else:
                print(f"    Error: {result.get('error', 'Unknown error')}")
            
            print()
        
        # ---------------------------------------------------------------------
        # Step 3: Add Q&A Examples
        # ---------------------------------------------------------------------
        print_section("Step 3: Adding Q&A Examples")
        
        print(f"Adding {len(SAMPLE_EXAMPLES)} examples to improve query generation...\n")
        
        example_ids = []
        for example in SAMPLE_EXAMPLES:
            result = await service.add_example(
                tenant_id=tenant_id,
                dataset_name=dataset_name,
                question=example["question"],
                query=example["query"],
                query_type="sql",
                explanation=example.get("explanation"),
                verified=True,
                created_by="demo_user",
            )
            
            if result.get("status") == "success":
                example_id = result.get("example_id")
                example_ids.append(example_id)
                print(f"Added: '{example['question'][:40]}...' (ID: {example_id})")
            else:
                print(f"Failed: '{example['question'][:40]}...' - {result.get('error')}")
        
        print(f"\nTotal examples added: {len(example_ids)}")
        
        # ---------------------------------------------------------------------
        # Step 4: List and Verify Examples
        # ---------------------------------------------------------------------
        print_section("Step 4: Listing Examples")
        
        examples = await service.list_examples(
            tenant_id=tenant_id,
            dataset_name=dataset_name,
            verified_only=False,
            limit=20,
        )
        
        print(f"Found {len(examples)} examples for dataset '{dataset_name}':\n")
        
        for ex in examples:
            status = "verified" if ex.get("verified") else "pending"
            print(f"  [{status}] {ex.get('question', 'N/A')[:50]}")
            print(f"           Query: {ex.get('query', 'N/A')[:50]}...")
            print()
        
        # Verify an example (if we have unverified ones)
        if example_ids:
            print(f"Verifying example ID {example_ids[0]}...")
            verify_result = await service.verify_example(
                example_id=example_ids[0],
                verified=True,
                updated_by="demo_user",
            )
            print(f"Verification result: {verify_result.get('status')}")
        
        # ---------------------------------------------------------------------
        # Step 5: List All Datasets
        # ---------------------------------------------------------------------
        print_section("Step 5: Listing Datasets")
        
        datasets = await service.list_datasets(
            tenant_id=tenant_id,
            limit=50,
        )
        
        print(f"Found {len(datasets)} dataset(s) for tenant '{tenant_id}':\n")
        
        for ds in datasets:
            print(f"  - {ds.get('dataset_name')} ({ds.get('source_type')})")
            print(f"    Description: {ds.get('description', 'N/A')[:60]}")
            print(f"    Status: {ds.get('status')}")
            print(f"    Tags: {', '.join(ds.get('tags', []))}")
            print()
        
        # ---------------------------------------------------------------------
        # Step 6: Get Dataset Details
        # ---------------------------------------------------------------------
        print_section("Step 6: Dataset Details")
        
        details = await service.get_dataset(
            tenant_id=tenant_id,
            dataset_name=dataset_name,
        )
        
        if details:
            print(f"Dataset: {details.get('dataset_name')}")
            print(f"Source Type: {details.get('source_type')}")
            print(f"Description: {details.get('description')}")
            print(f"Field Count: {details.get('field_count')}")
            print(f"Example Count: {details.get('example_count')}")
            print(f"Verified Examples: {details.get('verified_example_count')}")
            print(f"Status: {details.get('status')}")
            print(f"Tags: {', '.join(details.get('tags', []))}")
            print(f"Created: {details.get('created_at')}")
        else:
            print(f"Dataset '{dataset_name}' not found")
        
        # ---------------------------------------------------------------------
        # Step 7: Cleanup (Optional)
        # ---------------------------------------------------------------------
        print_section("Step 7: Cleanup (Optional)")
        
        # Uncomment to delete the demo dataset
        # print(f"Deleting dataset '{dataset_name}'...")
        # delete_result = await service.delete_dataset(
        #     tenant_id=tenant_id,
        #     dataset_name=dataset_name,
        # )
        # print(f"Delete result: {delete_result}")
        
        print("Skipping cleanup - dataset preserved for inspection")
        print("To delete, uncomment the cleanup code in this script")
        
        # ---------------------------------------------------------------------
        # Summary
        # ---------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("Demo Complete!")
        print("=" * 60)
        print(f"""
Summary:
  - Onboarded dataset: {dataset_name}
  - Schema fields created: {field_count}
  - Examples added: {len(example_ids)}
  - Queries tested: {len(SAMPLE_QUESTIONS)}

Next Steps:
  1. Replace MockEmbeddingClient with a real embedding service
  2. Replace MockInferenceClient with a real LLM service
  3. Add more domain-specific examples for better query generation
  4. Enable schema enrichment for automatic metadata extraction
""")
    
    # Close engine
    await engine.dispose()


async def main() -> None:
    """Entry point for the workflow demo."""
    # Load environment variables from .env file
    load_dotenv()
    
    try:
        await run_workflow()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\nError running demo: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
