"""
Dataset schemas for QueryForge integration.

Defines request/response models for:
- Dataset onboarding
- Query generation
- Example management
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# =============================================================================
# Dataset Onboarding
# =============================================================================

class DatasetOnboardRequest(BaseModel):
    """Request to onboard a new dataset."""
    tenant_id: str = Field(..., min_length=1, max_length=100)
    dataset_name: str = Field(..., min_length=1, max_length=200)
    source_type: str = Field(
        ..., 
        description="Data source type: postgres, opensearch, rest_api, clickhouse"
    )
    raw_schema: Union[str, Dict[str, Any]] = Field(
        ..., 
        description="Raw schema: DDL string, JSON mapping, or OpenAPI spec"
    )
    description: Optional[str] = Field(None, max_length=2000)
    tags: List[str] = Field(default=[])
    enable_enrichment: bool = Field(
        default=False,
        description="Use LLM to enrich field metadata"
    )


class DatasetOnboardResponse(BaseModel):
    """Response from dataset onboarding."""
    status: str
    dataset_name: Optional[str] = None
    source_type: Optional[str] = None
    schema_index_id: Optional[int] = None
    field_count: Optional[int] = None
    fields: Optional[List[int]] = None
    error: Optional[str] = None
    errors: Optional[List[str]] = None


class DatasetResponse(BaseModel):
    """Dataset details response."""
    id: int
    tenant_id: str
    dataset_name: str
    source_type: str
    description: str
    field_count: int
    example_count: int
    verified_example_count: int
    tags: List[str]
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DatasetListResponse(BaseModel):
    """List of datasets."""
    datasets: List[DatasetResponse]
    total: int


class DatasetSummary(BaseModel):
    """Brief dataset summary for list endpoints."""
    id: int
    dataset_name: str
    source_type: str
    description: str
    tags: List[str]
    status: str
    created_at: Optional[str] = None


class DatasetDeleteResponse(BaseModel):
    """Response from dataset deletion."""
    status: str
    dataset_name: str
    deleted_nodes: int
    error: Optional[str] = None


# =============================================================================
# Query Generation
# =============================================================================

class QueryGenerateRequest(BaseModel):
    """Request to generate a query."""
    tenant_id: str = Field(..., min_length=1, max_length=100)
    dataset_name: str = Field(..., min_length=1, max_length=200)
    question: str = Field(..., min_length=1, max_length=2000)
    include_explanation: bool = Field(default=False)


class QueryGenerateResponse(BaseModel):
    """Response from query generation."""
    status: str
    query: Optional[str] = None
    query_type: Optional[str] = None
    explanation: Optional[str] = None
    confidence: Optional[float] = None
    error: Optional[str] = None


# =============================================================================
# Example Management
# =============================================================================

class ExampleCreateRequest(BaseModel):
    """Request to create a new example."""
    tenant_id: str = Field(..., min_length=1, max_length=100)
    dataset_name: str = Field(..., min_length=1, max_length=200)
    question: str = Field(..., min_length=1, max_length=2000)
    query: str = Field(..., min_length=1, max_length=10000)
    query_type: str = Field(
        ..., 
        pattern="^(sql|elasticsearch|api)$",
        description="Query type: sql, elasticsearch, or api"
    )
    explanation: Optional[str] = Field(None, max_length=2000)
    verified: bool = Field(default=False)


class ExampleResponse(BaseModel):
    """Example details response."""
    id: int
    question: str
    query: str
    query_type: str
    explanation: Optional[str] = None
    verified: bool
    dataset_name: Optional[str] = None
    created_at: Optional[str] = None


class ExampleListResponse(BaseModel):
    """List of examples."""
    examples: List[ExampleResponse]
    total: int


class ExampleVerifyRequest(BaseModel):
    """Request to verify an example."""
    verified: bool = Field(default=True)


class ExampleVerifyResponse(BaseModel):
    """Response from example verification."""
    status: str
    example_id: int
    verified: bool
    error: Optional[str] = None


# =============================================================================
# QueryForge Status
# =============================================================================

class QueryForgeStatusResponse(BaseModel):
    """QueryForge availability status."""
    available: bool
    available_sources: List[str]
    error: Optional[str] = None
    install_hint: Optional[str] = None
