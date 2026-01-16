import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional


class PostgresClient:
    def __init__(self, url: Optional[str] = None, echo: bool = False):
        self._url = url or os.environ.get("FRAMEWORK_DB_URL", "")
        self._echo = echo
        self._engine = None
        self._session_factory = None

    def _ensure_engine(self):
        if self._engine is None:
            try:
                from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
            except ImportError:
                raise ImportError(
                    "sqlalchemy package required. Install with: pip install sqlalchemy[asyncio] asyncpg"
                )

            self._engine = create_async_engine(self._url, echo=self._echo)
            self._session_factory = async_sessionmaker(
                self._engine,
                expire_on_commit=False,
            )
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[Any, None]:
        self._ensure_engine()
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[Any, None]:
        engine = self._ensure_engine()
        async with engine.connect() as conn:
            yield conn

    async def execute(self, query: Any, params: Optional[dict] = None) -> Any:
        async with self.session() as session:
            result = await session.execute(query, params or {})
            return result

    async def fetch_one(self, query: Any, params: Optional[dict] = None) -> Optional[Any]:
        async with self.session() as session:
            result = await session.execute(query, params or {})
            return result.fetchone()

    async def fetch_all(self, query: Any, params: Optional[dict] = None) -> list[Any]:
        async with self.session() as session:
            result = await session.execute(query, params or {})
            return list(result.fetchall())

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    async def __aenter__(self) -> "PostgresClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
