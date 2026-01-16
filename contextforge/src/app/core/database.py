"""
Database session management.

Provides async SQLAlchemy engine and session factory.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings


# Create async engine
engine = create_async_engine(
    settings.FRAMEWORK_DB_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    echo=settings.DEBUG,
    # Use NullPool for testing, connection pool for production
    poolclass=None if settings.DEBUG else None,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.
    
    Usage:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database connection (call on startup)."""
    # Test connection
    async with engine.begin() as conn:
        await conn.execute("SELECT 1")


async def close_db() -> None:
    """Close database connections (call on shutdown)."""
    await engine.dispose()


from contextlib import asynccontextmanager

@asynccontextmanager
async def get_session_context():
    """
    Context manager for getting a database session.
    
    Useful for non-FastAPI contexts like jobs and scripts.
    
    Usage:
        async with get_session_context() as session:
            # Use session
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
