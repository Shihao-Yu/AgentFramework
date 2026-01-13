"""
Dataset API routes for QueryForge integration.

Provides endpoints for:
- Dataset onboarding (schema → nodes)
- Query generation (NL → SQL/DSL)
- Example management (Q&A pairs)
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_embedding_client, get_inference_client
from app.clients.embedding_client import EmbeddingClient
from app.clients.inference_client import InferenceClient
from app.services.queryforge_service import QueryForgeService
from app.schemas.datasets import (
    DatasetOnboardRequest,
    DatasetOnboardResponse,
    DatasetResponse,
    DatasetSummary,
    DatasetDeleteResponse,
    QueryGenerateRequest,
    QueryGenerateResponse,
    ExampleCreateRequest,
    ExampleResponse,
    ExampleListResponse,
    ExampleVerifyRequest,
    ExampleVerifyResponse,
    QueryForgeStatusResponse,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


# =============================================================================
# QueryForge Status
# =============================================================================

@router.get("/status", response_model=QueryForgeStatusResponse)
async def get_queryforge_status():
    """
    Check QueryForge availability and list available data sources.
    
    Returns:
        - available: Whether AgenticSearch QueryForge is installed
        - available_sources: List of registered source types
        - error: Import error message if not available
    """
    available = QueryForgeService.is_available()
    error = QueryForgeService.get_import_error()
    sources = QueryForgeService.list_available_sources()
    
    return QueryForgeStatusResponse(
        available=available,
        available_sources=sources,
        error=error,
        install_hint="pip install -e ../agentic_search" if not available else None,
    )


# =============================================================================
# Dataset Onboarding
# =============================================================================

@router.post("/onboard", response_model=DatasetOnboardResponse)
async def onboard_dataset(
    request: DatasetOnboardRequest,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """
    Onboard a new dataset by parsing its schema.
    
    This endpoint:
    1. Parses the raw schema using the appropriate source plugin
    2. Creates a schema_index node for the dataset
    3. Creates schema_field nodes for each field
    4. Links fields to the index with PARENT edges
    
    Supported source types:
    - postgres: SQL DDL
    - opensearch: JSON mapping
    - rest_api: OpenAPI/Swagger spec
    - clickhouse: ClickHouse DDL
    
    Example (PostgreSQL):
    ```json
    {
        "tenant_id": "acme",
        "dataset_name": "orders",
        "source_type": "postgres",
        "raw_schema": "CREATE TABLE orders (id INT PRIMARY KEY, status VARCHAR(50));",
        "description": "Order management table"
    }
    ```
    """
    service = QueryForgeService(session, embedding_client)
    
    result = await service.onboard_dataset(
        tenant_id=request.tenant_id,
        dataset_name=request.dataset_name,
        source_type=request.source_type,
        raw_schema=request.raw_schema,
        description=request.description,
        tags=request.tags,
        enable_enrichment=request.enable_enrichment,
    )
    
    return DatasetOnboardResponse(**result)


@router.get("", response_model=List[DatasetSummary])
async def list_datasets(
    tenant_id: str = Query(..., description="Tenant ID"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """
    List all datasets for a tenant.
    
    Optionally filter by source_type (postgres, opensearch, etc.).
    """
    service = QueryForgeService(session, embedding_client)
    
    datasets = await service.list_datasets(
        tenant_id=tenant_id,
        source_type=source_type,
        limit=limit,
    )
    
    return [DatasetSummary(**d) for d in datasets]


@router.get("/{dataset_name}", response_model=DatasetResponse)
async def get_dataset(
    dataset_name: str,
    tenant_id: str = Query(..., description="Tenant ID"),
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """
    Get detailed information about a dataset.
    
    Includes field count, example count, and verification stats.
    """
    service = QueryForgeService(session, embedding_client)
    
    dataset = await service.get_dataset(
        tenant_id=tenant_id,
        dataset_name=dataset_name,
    )
    
    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{dataset_name}' not found for tenant '{tenant_id}'"
        )
    
    return DatasetResponse(**dataset)


@router.delete("/{dataset_name}", response_model=DatasetDeleteResponse)
async def delete_dataset(
    dataset_name: str,
    tenant_id: str = Query(..., description="Tenant ID"),
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """
    Delete a dataset and all its associated nodes.
    
    This permanently deletes:
    - The schema_index node
    - All schema_field nodes
    - All example nodes
    - All edges between them
    """
    service = QueryForgeService(session, embedding_client)
    
    result = await service.delete_dataset(
        tenant_id=tenant_id,
        dataset_name=dataset_name,
    )
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return DatasetDeleteResponse(**result)


# =============================================================================
# Query Generation
# =============================================================================

@router.post("/generate", response_model=QueryGenerateResponse)
async def generate_query(
    request: QueryGenerateRequest,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    inference_client: InferenceClient = Depends(get_inference_client),
):
    """
    Generate a query from natural language.
    
    Uses the dataset's schema and examples to generate an appropriate query
    in the dataset's native format (SQL, OpenSearch DSL, or API request).
    
    Example:
    ```json
    {
        "tenant_id": "acme",
        "dataset_name": "orders",
        "question": "Show all pending orders from last week",
        "include_explanation": true
    }
    ```
    
    Note: Requires LLM client to be configured. Returns error if not available.
    """
    service = QueryForgeService(
        session, 
        embedding_client, 
        llm_client=inference_client,
    )
    
    # Check QueryForge availability
    if not service.is_available():
        return QueryGenerateResponse(
            status="error",
            error="AgenticSearch QueryForge not available",
        )
    
    result = await service.generate_query(
        tenant_id=request.tenant_id,
        dataset_name=request.dataset_name,
        question=request.question,
        include_explanation=request.include_explanation,
    )
    
    return QueryGenerateResponse(**result)


# =============================================================================
# Example Management
# =============================================================================

@router.post("/examples", response_model=ExampleResponse)
async def create_example(
    request: ExampleCreateRequest,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """
    Create a Q&A example for a dataset.
    
    Examples are used to improve query generation quality through few-shot learning.
    
    Example:
    ```json
    {
        "tenant_id": "acme",
        "dataset_name": "orders",
        "question": "Get all pending orders",
        "query": "SELECT * FROM orders WHERE status = 'pending'",
        "query_type": "sql",
        "verified": true
    }
    ```
    """
    service = QueryForgeService(session, embedding_client)
    
    result = await service.add_example(
        tenant_id=request.tenant_id,
        dataset_name=request.dataset_name,
        question=request.question,
        query=request.query,
        query_type=request.query_type,
        explanation=request.explanation,
        verified=request.verified,
    )
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    # Get the created example details
    examples = await service.list_examples(
        tenant_id=request.tenant_id,
        dataset_name=request.dataset_name,
        limit=1,
    )
    
    if examples:
        return ExampleResponse(**examples[0])
    
    return ExampleResponse(
        id=result["example_id"],
        question=request.question,
        query=request.query,
        query_type=request.query_type,
        explanation=request.explanation,
        verified=result.get("verified", False),
        dataset_name=request.dataset_name,
    )


@router.get("/examples", response_model=ExampleListResponse)
async def list_examples(
    tenant_id: str = Query(..., description="Tenant ID"),
    dataset_name: Optional[str] = Query(None, description="Filter by dataset"),
    verified_only: bool = Query(False, description="Only return verified examples"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """
    List examples for a tenant, optionally filtered by dataset.
    """
    service = QueryForgeService(session, embedding_client)
    
    examples = await service.list_examples(
        tenant_id=tenant_id,
        dataset_name=dataset_name,
        verified_only=verified_only,
        limit=limit,
    )
    
    return ExampleListResponse(
        examples=[ExampleResponse(**e) for e in examples],
        total=len(examples),
    )


@router.patch("/examples/{example_id}/verify", response_model=ExampleVerifyResponse)
async def verify_example(
    example_id: int,
    request: ExampleVerifyRequest,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
):
    """
    Mark an example as verified or unverified.
    
    Verified examples are used for query generation.
    Unverified examples are kept for review.
    """
    service = QueryForgeService(session, embedding_client)
    
    result = await service.verify_example(
        example_id=example_id,
        verified=request.verified,
    )
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return ExampleVerifyResponse(**result)
