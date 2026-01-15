"""
ContextForge - Main Application Class

The primary entry point for the ContextForge library.
"""

from __future__ import annotations

from typing import Optional, List, Literal
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)

from contextforge.core.config import ContextForgeConfig
from contextforge.core.exceptions import ConfigurationError
from contextforge.protocols.embedding import EmbeddingProvider
from contextforge.protocols.llm import LLMProvider
from contextforge.protocols.auth import AuthProvider, AuthContext
from contextforge.providers.embedding import SentenceTransformersProvider
from contextforge.providers.auth import HeaderAuthProvider




class ContextForge:
    """
    Main entry point for ContextForge library.
    
    Provides:
    - FastAPI router for API endpoints
    - FastAPI app with Admin UI (optional)
    - Service factories for dependency injection
    - Database session management
    
    Basic Usage:
        from contextforge import ContextForge
        
        cf = ContextForge(database_url="postgresql+asyncpg://...")
        app.include_router(cf.router, prefix="/api/kb")
    
    Full Configuration:
        from contextforge import ContextForge, ContextForgeConfig
        from contextforge.providers.embedding import SentenceTransformersProvider
        
        cf = ContextForge(
            config=ContextForgeConfig(
                database_url="postgresql+asyncpg://...",
                db_schema="knowledge",
                admin_ui_enabled=True,
            ),
            embedding_provider=SentenceTransformersProvider(
                model_name="all-MiniLM-L6-v2",
            ),
        )
        
        # Option 1: Include just the API routes
        app.include_router(cf.router, prefix="/api/kb")
        
        # Option 2: Mount full app with Admin UI
        app.mount("/knowledge", cf.app)
    
    Using Services Directly:
        @app.get("/my-endpoint")
        async def my_endpoint(
            node_service = Depends(cf.get_node_service),
        ):
            nodes = await node_service.list_nodes(tenant_id="my-tenant")
            return nodes
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        config: Optional[ContextForgeConfig] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        llm_provider: Optional[LLMProvider] = None,
        auth_provider: Optional[AuthProvider] = None,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
    ):
        """
        Initialize ContextForge.
        
        Args:
            database_url: PostgreSQL connection URL (shortcut for config)
            config: Full configuration object
            embedding_provider: Custom embedding provider (default: SentenceTransformers)
            llm_provider: Custom LLM provider (optional, for query generation)
            auth_provider: Custom auth provider (default: HeaderAuthProvider)
            session_factory: Existing session factory (to share with host app)
        """
        # Configuration
        if config is not None:
            self.config = config
        elif database_url is not None:
            self.config = ContextForgeConfig(database_url=database_url)
        else:
            # Try to load from environment
            self.config = ContextForgeConfig()
        
        # Providers
        self._init_embedding_provider(embedding_provider)
        self.llm_provider = llm_provider
        self.auth_provider = auth_provider or HeaderAuthProvider()
        
        # Database
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = session_factory
        
        # FastAPI components
        self._router: Optional[APIRouter] = None
        self._app: Optional[FastAPI] = None
    
    def _init_embedding_provider(self, provider: Optional[EmbeddingProvider]) -> None:
        """Initialize embedding provider."""
        if provider is not None:
            self.embedding_provider = provider
            return
        
        try:
            self.embedding_provider = SentenceTransformersProvider()
        except ImportError:
            raise ConfigurationError(
                "No embedding provider configured and sentence-transformers not installed. "
                "Either pass embedding_provider or install: pip install sentence-transformers",
                config_key="embedding_provider",
            )
    
    # ===================
    # Database
    # ===================
    
    @property
    def engine(self) -> AsyncEngine:
        """Get or create database engine."""
        if self._engine is None:
            self._engine = create_async_engine(
                self.config.database_url,
                pool_size=self.config.db_pool_size,
                max_overflow=self.config.db_max_overflow,
                echo=self.config.db_echo,
            )
        return self._engine
    
    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get or create session factory."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory
    
    @asynccontextmanager
    async def get_session(self):
        """Get a database session as context manager."""
        async with self.session_factory() as session:
            try:
                yield session
            finally:
                await session.close()
    
    async def dispose(self) -> None:
        """Dispose database connections. Call on shutdown."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
    
    # ===================
    # FastAPI Router
    # ===================
    
    @property
    def router(self) -> APIRouter:
        """
        Get FastAPI router with all ContextForge endpoints.
        
        Use this to add ContextForge API to your existing app:
            app.include_router(cf.router, prefix="/api/kb")
        """
        if self._router is None:
            self._router = self._create_router()
        return self._router
    
    def _create_router(self) -> APIRouter:
        """Create API router with all endpoints."""
        router = APIRouter(tags=["ContextForge"])
        
        # Import routes from app module
        # These imports are deferred to avoid circular imports
        try:
            from app.routes.nodes import router as nodes_router
            from app.routes.edges import router as edges_router
            from app.routes.search import router as search_router
            from app.routes.tenants import router as tenants_router
            from app.routes.graph import router as graph_router
            from app.routes.context import router as context_router
            from app.routes.datasets import router as datasets_router
            
            router.include_router(nodes_router)
            router.include_router(edges_router)
            router.include_router(search_router)
            router.include_router(tenants_router)
            router.include_router(graph_router)
            router.include_router(context_router)
            
            if self.config.enable_queryforge:
                router.include_router(datasets_router)
            
            if self.config.enable_staging:
                from app.routes.staging import router as staging_router
                router.include_router(staging_router)
            
            if self.config.enable_analytics:
                from app.routes.metrics import router as metrics_router
                router.include_router(metrics_router)
                
        except ImportError as e:
            # If app module not available, create minimal router
            self._create_minimal_router(router)
        
        return router
    
    def _create_minimal_router(self, router: APIRouter) -> None:
        """Create minimal router when full app not available."""
        from contextforge import __version__
        
        @router.get("/health")
        async def health():
            return {"status": "ok", "version": __version__}
        
        @router.get("/config")
        async def get_config():
            return {
                "db_schema": self.config.db_schema,
                "embedding_dimensions": self.embedding_provider.dimensions,
                "features": {
                    "queryforge": self.config.enable_queryforge,
                    "staging": self.config.enable_staging,
                    "analytics": self.config.enable_analytics,
                },
            }
    
    # ===================
    # FastAPI App
    # ===================
    
    @property
    def app(self) -> FastAPI:
        """
        Get full FastAPI application with Admin UI.
        
        Use this to mount ContextForge as a sub-application:
            app.mount("/knowledge", cf.app)
        """
        if self._app is None:
            self._app = self._create_app()
        return self._app
    
    def _create_app(self) -> FastAPI:
        """Create FastAPI application."""
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            yield
            # Shutdown
            await self.dispose()
        
        from contextforge import __version__
        
        app = FastAPI(
            title=self.config.admin_ui_title,
            version=__version__,
            description="ContextForge Knowledge Management API",
            lifespan=lifespan,
        )
        
        # CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Include API routes
        app.include_router(self.router, prefix=self.config.api_prefix)
        
        # Mount Admin UI if enabled
        if self.config.admin_ui_enabled:
            self._mount_admin_ui(app)
        
        return app
    
    def _mount_admin_ui(self, app: FastAPI) -> None:
        """Mount Admin UI static files."""
        from pathlib import Path
        import importlib.resources
        
        admin_path = None
        
        try:
            bundled = importlib.resources.files("contextforge") / "admin"
            if bundled.is_dir():
                admin_path = Path(str(bundled))
        except Exception:
            pass
        
        if admin_path is None:
            dev_paths = [
                Path(__file__).parent.parent / "admin",
                Path(__file__).parent.parent.parent.parent / "admin-ui" / "dist",
            ]
            for path in dev_paths:
                if path.exists() and (path / "index.html").exists():
                    admin_path = path
                    break
        
        if admin_path and admin_path.exists():
            app.mount(
                self.config.admin_ui_path,
                StaticFiles(directory=str(admin_path), html=True),
                name="admin-ui",
            )
    
    # ===================
    # Service Factories
    # ===================
    
    def get_node_service(self):
        """
        FastAPI dependency for NodeService.
        
        Usage:
            @app.get("/nodes")
            async def list_nodes(
                service = Depends(cf.get_node_service),
            ):
                return await service.list_nodes(...)
        """
        async def _get_service():
            from app.services.node_service import NodeService
            async with self.get_session() as session:
                yield NodeService(
                    session=session,
                    embedding_client=self.embedding_provider,
                )
        return Depends(_get_service)
    
    def get_search_service(self):
        """FastAPI dependency for SearchService."""
        async def _get_service():
            from app.services.search_service import SearchService
            async with self.get_session() as session:
                yield SearchService(
                    session=session,
                    embedding_client=self.embedding_provider,
                    bm25_weight=self.config.search_bm25_weight,
                    vector_weight=self.config.search_vector_weight,
                )
        return Depends(_get_service)
    
    def get_graph_service(self):
        """FastAPI dependency for GraphService."""
        async def _get_service():
            from app.services.graph_service import GraphService
            async with self.get_session() as session:
                yield GraphService(session=session)
        return Depends(_get_service)
    
    def get_queryforge_service(self):
        """FastAPI dependency for QueryForgeService."""
        async def _get_service():
            from app.services.queryforge_service import QueryForgeService
            async with self.get_session() as session:
                yield QueryForgeService(
                    session=session,
                    embedding_client=self.embedding_provider,
                    llm_client=self.llm_provider,
                )
        return Depends(_get_service)
    
    # ===================
    # Auth Dependencies
    # ===================
    
    def get_current_user(self):
        """
        FastAPI dependency for current user.
        
        Usage:
            @app.get("/me")
            async def get_me(user: AuthContext = cf.get_current_user()):
                return {"user_id": user.user_id}
        """
        async def _get_user(request: Request) -> AuthContext:
            return await self.auth_provider.get_current_user(request)
        return Depends(_get_user)
    
    def require_tenant_access(self, tenant_id_param: str = "tenant_id"):
        """
        FastAPI dependency that checks tenant access.
        
        Usage:
            @app.get("/tenants/{tenant_id}/nodes")
            async def list_nodes(
                tenant_id: str,
                user: AuthContext = cf.require_tenant_access(),
            ):
                # user is guaranteed to have access to tenant_id
                ...
        """
        async def _check_access(
            request: Request,
        ) -> AuthContext:
            from contextforge.core.exceptions import AuthorizationError
            
            user = await self.auth_provider.get_current_user(request)
            tenant_id = request.path_params.get(tenant_id_param)
            
            if tenant_id and not await self.auth_provider.check_tenant_access(user, tenant_id):
                raise AuthorizationError(
                    f"Access denied to tenant: {tenant_id}",
                    tenant_id=tenant_id,
                )
            
            return user
        return Depends(_check_access)
    
    async def check_database(self) -> dict:
        """Check database connection and schema."""
        async with self.get_session() as session:
            from sqlalchemy import text
            
            result = await session.execute(text("SELECT 1"))
            row = result.fetchone()
            
            return {
                "connected": row is not None,
                "schema": self.config.db_schema,
            }
    
    # ===================
    # Context API
    # ===================
    
    async def get_context(
        self,
        query: Optional[str] = None,
        tenant_ids: Optional[List[str]] = None,
        entry_types: Optional[List["NodeType"]] = None,
        tags: Optional[List[str]] = None,
        max_depth: int = 2,
        expand: bool = True,
        entry_limit: int = 10,
        context_limit: int = 50,
        include_entities: bool = True,
        include_schemas: bool = False,
        include_examples: bool = False,
        search_method: Literal["hybrid", "bm25", "vector"] = "hybrid",
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
        min_score: Optional[float] = None,
        max_tokens: Optional[int] = None,
        token_model: str = "gpt-4",
        expansion_types: Optional[List["NodeType"]] = None,
        *,
        request: Optional["ContextRequest"] = None,
    ) -> "ContextResponse":
        from app.schemas.context import ContextRequest, ContextResponse
        from app.services.context_service import ContextService
        from app.clients.embedding_client import EmbeddingClient
        
        if request is None:
            if query is None:
                raise ValueError("Either 'query' or 'request' must be provided")
            if tenant_ids is None:
                raise ValueError("Either 'tenant_ids' or 'request' must be provided")
            
            request = ContextRequest(
                query=query,
                tenant_ids=tenant_ids,
                entry_types=entry_types,
                tags=tags,
                max_depth=max_depth,
                expand=expand,
                entry_limit=entry_limit,
                context_limit=context_limit,
                include_entities=include_entities,
                include_schemas=include_schemas,
                include_examples=include_examples,
                search_method=search_method,
                bm25_weight=bm25_weight,
                vector_weight=vector_weight,
                min_score=min_score,
                max_tokens=max_tokens,
                token_model=token_model,
                expansion_types=expansion_types,
            )
        
        async with self.get_session() as session:
            embedding_client = EmbeddingClient(self.embedding_provider)
            service = ContextService(session, embedding_client)
            return await service.get_context(request)
