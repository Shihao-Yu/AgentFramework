"""
Dependency injection for FastAPI.

Provides access to services, clients, and authentication.
"""

import os
import logging
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.clients.embedding_client import EmbeddingClient
from app.clients.inference_client import InferenceClient


class EmbeddingClientNotConfiguredError(RuntimeError):
    pass


class InferenceClientNotConfiguredError(RuntimeError):
    pass

logger = logging.getLogger(__name__)


# ==================== Client Singletons ====================

_embedding_client: Optional[EmbeddingClient] = None
_inference_client: Optional[InferenceClient] = None
_clients_initialized: bool = False


def _initialize_clients() -> None:
    """Initialize clients based on environment configuration."""
    global _embedding_client, _inference_client, _clients_initialized
    
    if _clients_initialized:
        return
    
    # Initialize embedding client
    _embedding_client = _create_embedding_client()
    
    # Initialize inference client
    _inference_client = _create_inference_client()
    
    _clients_initialized = True


def _create_embedding_client() -> EmbeddingClient:
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from contextforge.providers.embedding import OpenAIEmbeddingProvider
            
            model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
            logger.info(f"Using OpenAI embedding provider with model {model}")
            
            return _OpenAIEmbeddingClientWrapper(
                OpenAIEmbeddingProvider(api_key=openai_key, model=model)
            )
        except ImportError:
            logger.warning("OpenAI provider not available, trying alternatives")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI embedding: {e}")
    
    try:
        from contextforge.providers.embedding import SentenceTransformersProvider
        
        model = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        logger.info(f"Using SentenceTransformers embedding provider with model {model}")
        
        return _SentenceTransformersClientWrapper(
            SentenceTransformersProvider(model_name=model)
        )
    except ImportError:
        logger.warning("SentenceTransformers not available")
    except Exception as e:
        logger.warning(f"Failed to initialize SentenceTransformers: {e}")
    
    raise EmbeddingClientNotConfiguredError(
        "No embedding provider available. "
        "Set OPENAI_API_KEY or install sentence-transformers."
    )


def _create_inference_client() -> InferenceClient:
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from infra.inference import InferenceClient as InfraInferenceClient
            from infra.tracing import TracingClient, TracedInferenceClient
            
            model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
            base_url = os.environ.get("OPENAI_BASE_URL")
            logger.info(f"Using infra InferenceClient with model {model}")
            
            inference = InfraInferenceClient(
                api_key=openai_key,
                base_url=base_url,
                model=model,
            )
            tracing = TracingClient()
            
            return _InfraInferenceClientWrapper(
                TracedInferenceClient(inference, tracing)
            )
        except ImportError:
            logger.warning("infra package not available, trying contextforge provider")
        except Exception as e:
            logger.warning(f"Failed to initialize infra InferenceClient: {e}")
        
        try:
            from contextforge.providers.llm import OpenAILLMProvider
            
            model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
            logger.info(f"Using OpenAI LLM provider with model {model}")
            
            return _OpenAIInferenceClientWrapper(
                OpenAILLMProvider(api_key=openai_key, model=model)
            )
        except ImportError:
            logger.warning("OpenAI provider not available")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI LLM: {e}")
    
    raise InferenceClientNotConfiguredError(
        "No LLM provider available. Set OPENAI_API_KEY."
    )


# ==================== Provider Wrappers ====================
# These wrap library providers to match the app's client interfaces

class _OpenAIEmbeddingClientWrapper(EmbeddingClient):
    
    def __init__(self, provider):
        self._provider = provider
    
    async def embed(self, text: str) -> list[float]:
        result = await self._provider.embed(text)
        self._validate_dimension(result)
        return result
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results = await self._provider.embed_batch(texts)
        if results:
            self._validate_dimension(results[0])
        return results
    
    def _validate_dimension(self, embedding: list[float]) -> None:
        if len(embedding) != self.expected_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: got {len(embedding)}, "
                f"expected {self.expected_dimension}. "
                f"Update EMBEDDING_DIMENSION in config to match your model."
            )
    
    async def health_check(self) -> bool:
        try:
            result = await self._provider.embed("health check")
            return len(result) == self.expected_dimension
        except Exception:
            return False


class _SentenceTransformersClientWrapper(EmbeddingClient):
    
    def __init__(self, provider):
        self._provider = provider
    
    async def embed(self, text: str) -> list[float]:
        result = await self._provider.embed(text)
        self._validate_dimension(result)
        return result
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results = await self._provider.embed_batch(texts)
        if results:
            self._validate_dimension(results[0])
        return results
    
    def _validate_dimension(self, embedding: list[float]) -> None:
        if len(embedding) != self.expected_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: got {len(embedding)}, "
                f"expected {self.expected_dimension}. "
                f"Update EMBEDDING_DIMENSION in config to match your model."
            )
    
    async def health_check(self) -> bool:
        try:
            result = await self._provider.embed("health check")
            return len(result) == self.expected_dimension
        except Exception:
            return False


class _InfraInferenceClientWrapper(InferenceClient):
    
    def __init__(self, traced_client):
        self._client = traced_client
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        from infra.inference import Message, InferenceConfig
        
        messages = []
        if system_prompt:
            messages.append(Message.system(system_prompt))
        messages.append(Message.user(prompt))
        
        config = InferenceConfig(temperature=temperature, max_tokens=max_tokens)
        response = await self._client.complete(messages, config=config)
        return response.content or ""
    
    async def generate_structured(self, prompt, response_model, system_prompt=None, temperature=0.3, model=None):
        from infra.inference import Message, InferenceConfig
        
        messages = []
        if system_prompt:
            messages.append(Message.system(system_prompt))
        messages.append(Message.user(prompt))
        
        config = InferenceConfig(temperature=temperature, model=model)
        return await self._client.complete_structured(messages, response_model, config=config)
    
    async def health_check(self) -> bool:
        try:
            result = await self.generate("Say ok", max_tokens=10)
            return len(result) > 0
        except Exception:
            return False


class _OpenAIInferenceClientWrapper(InferenceClient):
    
    def __init__(self, provider):
        self._provider = provider
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        return await self._provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    async def generate_structured(self, prompt, response_model, system_prompt=None, temperature=0.3, model=None):
        return await self._provider.generate_structured(
            prompt=prompt,
            response_model=response_model,
            system_prompt=system_prompt,
            temperature=temperature,
            model=model,
        )
    
    async def health_check(self) -> bool:
        try:
            result = await self._provider.generate("Say ok", max_tokens=10)
            return len(result) > 0
        except Exception:
            return False


def get_embedding_client_instance() -> EmbeddingClient:
    global _embedding_client
    _initialize_clients()
    if _embedding_client is None:
        raise EmbeddingClientNotConfiguredError("Embedding client not initialized")
    return _embedding_client


def get_inference_client_instance() -> InferenceClient:
    global _inference_client
    _initialize_clients()
    if _inference_client is None:
        raise InferenceClientNotConfiguredError("Inference client not initialized")
    return _inference_client


# ==================== FastAPI Dependencies ====================

async def get_embedding_client() -> EmbeddingClient:
    return get_embedding_client_instance()


async def get_optional_embedding_client() -> Optional[EmbeddingClient]:
    try:
        return get_embedding_client_instance()
    except EmbeddingClientNotConfiguredError:
        return None


async def get_inference_client() -> InferenceClient:
    return get_inference_client_instance()


async def get_optional_inference_client() -> Optional[InferenceClient]:
    try:
        return get_inference_client_instance()
    except InferenceClientNotConfiguredError:
        return None


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_tenant_ids: Optional[str] = Header(None, alias="X-Tenant-IDs"),
) -> dict:
    """
    Dependency for getting current user context.
    
    Authentication modes (configured via AUTH_MODE env var):
    - "none": No authentication (development only)
    - "header": Trust headers from API gateway (X-User-ID, X-Tenant-IDs)
    - "jwt": Validate JWT token (not yet implemented)
    
    Returns:
        dict with user_id, tenant_ids, and is_authenticated flag
    
    Production implementation should:
    - Set AUTH_MODE=header and configure API gateway to set headers
    - Or implement JWT validation with proper issuer/audience
    """
    auth_mode = os.environ.get("AUTH_MODE", "header")
    
    user_context = {
        "user_id": "anonymous",
        "tenant_ids": ["default", "shared"],
        "is_authenticated": False,
    }
    
    if auth_mode == "none":
        # Development mode - no auth required
        user_context["user_id"] = x_user_id or "dev-user"
        user_context["is_authenticated"] = True
        if x_tenant_ids:
            user_context["tenant_ids"] = [t.strip() for t in x_tenant_ids.split(",")]
        return user_context
    
    if auth_mode == "header":
        # API gateway mode - trust headers
        if x_user_id:
            user_context["user_id"] = x_user_id
            user_context["is_authenticated"] = True
            if x_tenant_ids:
                user_context["tenant_ids"] = [t.strip() for t in x_tenant_ids.split(",")]
            else:
                # Default tenants for authenticated users
                user_context["tenant_ids"] = ["default", "shared"]
        return user_context
    
    if auth_mode == "jwt":
        # JWT mode - validate token
        if authorization and authorization.startswith("Bearer "):
            # JWT validation placeholder
            # To implement:
            # 1. Extract token: token = authorization.replace("Bearer ", "")
            # 2. Validate token with your auth provider
            # 3. Extract claims (sub, tenant_ids, etc.)
            # 4. Return user context
            #
            # Example with contextforge.providers.auth.jwt:
            # from contextforge.providers.auth import JWTAuthProvider
            # provider = JWTAuthProvider(jwks_url="...")
            # auth_context = await provider.authenticate(token)
            # user_context["user_id"] = auth_context.user_id
            # user_context["tenant_ids"] = auth_context.tenant_ids
            # user_context["is_authenticated"] = True
            logger.warning("JWT authentication not implemented. Falling back to anonymous.")
    
    return user_context


# Legacy compatibility - returns just user_id string
async def get_current_user_id(
    user_context: dict = Depends(get_current_user),
) -> str:
    """Get just the user ID (legacy compatibility)."""
    return user_context.get("user_id", "anonymous")


async def get_current_user_required(
    user_context: dict = Depends(get_current_user),
) -> dict:
    """
    Dependency that requires authentication.
    
    Raises HTTPException if user is not authenticated.
    """
    if not user_context.get("is_authenticated", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_context


async def get_user_tenant_ids(
    user_context: dict = Depends(get_current_user),
) -> list[str]:
    return user_context.get("tenant_ids", ["default", "shared"])


# ==================== Redis Dependency ====================

async def get_redis_client():
    from app.core.redis import get_redis_client as _get_redis
    return await _get_redis()


# ==================== Graph Service Dependency ====================

async def get_graph_service(
    session: AsyncSession = Depends(get_session),
):
    """Dependency for GraphService with Redis client."""
    from app.services.graph_service import GraphService
    from app.core.redis import get_redis_client as _get_redis
    
    redis_client = await _get_redis()
    return GraphService(session, redis_client=redis_client)
