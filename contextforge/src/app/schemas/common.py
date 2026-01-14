"""
Common schema types used across the API.
"""

from typing import TypeVar, Generic, List, Optional
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    
    data: List[T]
    total: int
    page: int
    limit: int
    total_pages: int


class SuccessResponse(BaseModel):
    """Simple success response."""
    
    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response."""
    
    success: bool = False
    error: str
    detail: Optional[str] = None
