"""
Dependency injection for FastAPI.

Provides access to services, clients, and authentication.
"""

from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.clients.embedding_client import EmbeddingClient, MockEmbeddingClient
from app.clients.inference_client import InferenceClient, MockInferenceClient


# ==================== Client Singletons ====================

# These are placeholder implementations - replace with your actual clients
_embedding_client: Optional[EmbeddingClient] = None
_inference_client: Optional[InferenceClient] = None


def get_embedding_client_instance() -> EmbeddingClient:
    """
    Get or create embedding client singleton.
    
    Replace MockEmbeddingClient with your actual implementation.
    """
    global _embedding_client
    if _embedding_client is None:
        # TODO: Replace with your actual embedding client
        _embedding_client = MockEmbeddingClient()
    return _embedding_client


def get_inference_client_instance() -> InferenceClient:
    """
    Get or create inference client singleton.
    
    Replace MockInferenceClient with your actual implementation.
    """
    global _inference_client
    if _inference_client is None:
        # TODO: Replace with your actual inference client
        _inference_client = MockInferenceClient()
    return _inference_client


# ==================== FastAPI Dependencies ====================

async def get_embedding_client() -> EmbeddingClient:
    """Dependency for embedding client."""
    return get_embedding_client_instance()


async def get_inference_client() -> InferenceClient:
    """Dependency for inference client."""
    return get_inference_client_instance()


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
) -> str:
    """
    Dependency for getting current user.
    
    TODO: Implement actual authentication.
    
    Current behavior:
    - Returns X-User-ID header if provided
    - Returns "anonymous" if no auth headers
    
    Production implementation should:
    - Validate JWT token from Authorization header
    - Extract user ID from token claims
    - Raise HTTPException if token is invalid
    """
    if x_user_id:
        return x_user_id
    
    if authorization:
        # TODO: Implement JWT validation
        # token = authorization.replace("Bearer ", "")
        # claims = validate_jwt(token)
        # return claims["sub"]
        pass
    
    return "anonymous"


async def get_current_user_required(
    user: str = Depends(get_current_user),
) -> str:
    """
    Dependency that requires authentication.
    
    Raises HTTPException if user is anonymous.
    """
    if user == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
