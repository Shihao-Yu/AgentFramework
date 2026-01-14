"""Session store for persistent session management."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agentcore.inference import MessageRole
from agentcore.session.models import Checkpoint, MessageData, Session
from agentcore.session.orm import Base, CheckpointModel, MessageModel, SessionModel
from agentcore.settings.session import SessionSettings

logger = logging.getLogger(__name__)


class SessionStore:
    """Store for managing persistent agent sessions.
    
    The SessionStore provides:
    - CRUD operations for sessions
    - Message management within sessions
    - Checkpoint creation and retrieval
    - Expired session cleanup
    
    Example:
        ```python
        settings = SessionSettings()
        store = SessionStore(settings)
        await store.initialize()
        
        session = await store.get_or_create(
            session_id="sess-123",
            user_id=1,
            agent_type="purchasing",
        )
        
        await store.add_message(
            session_id="sess-123",
            message=MessageData(role=MessageRole.USER, content="Hello"),
        )
        
        await store.close()
        ```
    """

    def __init__(self, settings: Optional[SessionSettings] = None) -> None:
        """Initialize the session store.
        
        Args:
            settings: Session settings (uses defaults if not provided)
        """
        self._settings = settings or SessionSettings()
        self._engine = create_async_engine(
            self._settings.database_url,
            pool_size=self._settings.pool_size,
            max_overflow=self._settings.max_overflow,
            pool_timeout=self._settings.pool_timeout,
            echo=self._settings.echo_sql,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def initialize(self) -> None:
        """Initialize the database schema."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Session store initialized")

    async def close(self) -> None:
        """Close database connections."""
        await self._engine.dispose()
        logger.info("Session store closed")

    async def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session or None if not found
        """
        async with self._session_factory() as db:
            result = await db.execute(
                select(SessionModel)
                .where(SessionModel.id == session_id)
            )
            orm_session = result.scalar_one_or_none()
            
            if orm_session is None:
                return None
            
            return self._orm_to_session(orm_session)

    async def get_or_create(
        self,
        session_id: str,
        user_id: int,
        agent_type: str,
        ttl_hours: Optional[int] = None,
    ) -> Session:
        """Get an existing session or create a new one.
        
        Args:
            session_id: Session ID
            user_id: User ID
            agent_type: Type of agent
            ttl_hours: Session TTL in hours (uses settings default if not provided)
            
        Returns:
            Session (existing or newly created)
        """
        existing = await self.get(session_id)
        if existing:
            return existing
        
        ttl = ttl_hours or self._settings.session_ttl_hours
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)
        
        session = Session(
            id=session_id,
            user_id=user_id,
            agent_type=agent_type,
            expires_at=expires_at,
        )
        
        await self.save(session)
        return session

    async def save(self, session: Session) -> None:
        """Save a session.
        
        Args:
            session: Session to save
        """
        async with self._session_factory() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session.id)
            )
            orm_session = result.scalar_one_or_none()
            
            if orm_session is None:
                orm_session = SessionModel(
                    id=session.id,
                    user_id=session.user_id,
                    agent_type=session.agent_type,
                    state=session.state,
                    blackboard=session.blackboard_data,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                    expires_at=session.expires_at,
                )
                db.add(orm_session)
            else:
                orm_session.state = session.state
                orm_session.blackboard = session.blackboard_data
                orm_session.updated_at = session.updated_at
                orm_session.expires_at = session.expires_at
            
            await db.commit()

    async def add_message(
        self,
        session_id: str,
        message: MessageData,
    ) -> str:
        """Add a message to a session.
        
        Args:
            session_id: Session ID
            message: Message to add
            
        Returns:
            Message ID
            
        Raises:
            ValueError: If session not found or message limit exceeded
        """
        async with self._session_factory() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            orm_session = result.scalar_one_or_none()
            
            if orm_session is None:
                raise ValueError(f"Session {session_id} not found")
            
            msg_count = len(orm_session.messages)
            max_messages = self._settings.max_messages_per_session
            
            if msg_count >= max_messages:
                raise ValueError(
                    f"Session {session_id} has reached maximum messages ({max_messages})"
                )
            
            orm_message = MessageModel(
                id=message.id,
                session_id=session_id,
                role=message.role.value,
                content=message.content,
                name=message.name,
                tool_call_id=message.tool_call_id,
                tool_calls=message.tool_calls,
                extra_metadata=message.metadata,
                created_at=message.created_at,
            )
            
            db.add(orm_message)
            orm_session.updated_at = datetime.now(timezone.utc)
            
            await db.commit()
            
            return message.id

    async def get_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
    ) -> list[MessageData]:
        """Get messages from a session.
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages (most recent)
            since: Only return messages after this time
            
        Returns:
            List of messages
        """
        async with self._session_factory() as db:
            query = (
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .order_by(MessageModel.created_at)
            )
            
            if since:
                query = query.where(MessageModel.created_at > since)
            
            result = await db.execute(query)
            orm_messages = result.scalars().all()
            
            messages = [self._orm_to_message(m) for m in orm_messages]
            
            if limit:
                messages = messages[-limit:]
            
            return messages

    async def delete(self, session_id: str) -> bool:
        """Delete a session and all its messages.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if deleted, False if not found
        """
        async with self._session_factory() as db:
            result = await db.execute(
                delete(SessionModel).where(SessionModel.id == session_id)
            )
            await db.commit()
            
            return result.rowcount > 0

    async def cleanup_expired(self) -> int:
        """Delete all expired sessions.
        
        Returns:
            Number of sessions deleted
        """
        async with self._session_factory() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                delete(SessionModel)
                .where(SessionModel.expires_at.isnot(None))
                .where(SessionModel.expires_at < now)
            )
            await db.commit()
            
            count = result.rowcount
            if count > 0:
                logger.info(f"Cleaned up {count} expired sessions")
            
            return count

    async def create_checkpoint(
        self,
        session_id: str,
        thread_id: str,
        state: dict,
        parent_checkpoint_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Checkpoint:
        """Create a checkpoint for a session.
        
        Args:
            session_id: Session ID
            thread_id: Thread identifier
            state: State to checkpoint
            parent_checkpoint_id: ID of parent checkpoint
            metadata: Additional metadata
            
        Returns:
            Created checkpoint
        """
        checkpoint = Checkpoint(
            id=str(uuid4()),
            session_id=session_id,
            thread_id=thread_id,
            checkpoint_id=str(uuid4()),
            parent_checkpoint_id=parent_checkpoint_id,
            state=state,
            metadata=metadata or {},
        )
        
        async with self._session_factory() as db:
            orm_checkpoint = CheckpointModel(
                id=checkpoint.id,
                session_id=session_id,
                thread_id=thread_id,
                checkpoint_id=checkpoint.checkpoint_id,
                parent_checkpoint_id=parent_checkpoint_id,
                state=state,
                extra_metadata=checkpoint.metadata,
                created_at=checkpoint.created_at,
            )
            db.add(orm_checkpoint)
            await db.commit()
        
        return checkpoint

    async def get_latest_checkpoint(
        self,
        session_id: str,
        thread_id: str,
    ) -> Optional[Checkpoint]:
        """Get the most recent checkpoint for a session thread.
        
        Args:
            session_id: Session ID
            thread_id: Thread identifier
            
        Returns:
            Latest checkpoint or None
        """
        async with self._session_factory() as db:
            result = await db.execute(
                select(CheckpointModel)
                .where(CheckpointModel.session_id == session_id)
                .where(CheckpointModel.thread_id == thread_id)
                .order_by(CheckpointModel.created_at.desc())
                .limit(1)
            )
            orm_checkpoint = result.scalar_one_or_none()
            
            if orm_checkpoint is None:
                return None
            
            return self._orm_to_checkpoint(orm_checkpoint)

    async def list_sessions(
        self,
        user_id: Optional[int] = None,
        agent_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions with optional filtering.
        
        Args:
            user_id: Filter by user ID
            agent_type: Filter by agent type
            limit: Maximum number of sessions
            
        Returns:
            List of sessions
        """
        async with self._session_factory() as db:
            query = select(SessionModel).order_by(SessionModel.updated_at.desc())
            
            if user_id is not None:
                query = query.where(SessionModel.user_id == user_id)
            
            if agent_type is not None:
                query = query.where(SessionModel.agent_type == agent_type)
            
            query = query.limit(limit)
            
            result = await db.execute(query)
            orm_sessions = result.scalars().all()
            
            return [self._orm_to_session(s) for s in orm_sessions]

    def _orm_to_session(self, orm: SessionModel) -> Session:
        """Convert ORM model to Pydantic model."""
        messages = [self._orm_to_message(m) for m in orm.messages]
        
        return Session(
            id=orm.id,
            user_id=orm.user_id,
            agent_type=orm.agent_type,
            state=orm.state or {},
            blackboard_data=orm.blackboard or {},
            messages=messages,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            expires_at=orm.expires_at,
        )

    def _orm_to_message(self, orm: MessageModel) -> MessageData:
        """Convert ORM model to Pydantic model."""
        return MessageData(
            id=orm.id,
            role=MessageRole(orm.role),
            content=orm.content,
            name=orm.name,
            tool_call_id=orm.tool_call_id,
            tool_calls=orm.tool_calls,
            metadata=orm.extra_metadata or {},
            created_at=orm.created_at,
        )

    def _orm_to_checkpoint(self, orm: CheckpointModel) -> Checkpoint:
        """Convert ORM model to Pydantic model."""
        return Checkpoint(
            id=orm.id,
            session_id=orm.session_id,
            thread_id=orm.thread_id,
            checkpoint_id=orm.checkpoint_id,
            parent_checkpoint_id=orm.parent_checkpoint_id,
            state=orm.state,
            metadata=orm.extra_metadata or {},
            created_at=orm.created_at,
        )


class MockSessionStore:
    """In-memory session store for testing."""

    def __init__(self) -> None:
        """Initialize the mock store."""
        self._sessions: dict[str, Session] = {}
        self._checkpoints: dict[str, list[Checkpoint]] = {}

    async def initialize(self) -> None:
        """No-op for mock store."""
        pass

    async def close(self) -> None:
        """No-op for mock store."""
        pass

    async def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    async def get_or_create(
        self,
        session_id: str,
        user_id: int,
        agent_type: str,
        ttl_hours: Optional[int] = None,
    ) -> Session:
        """Get or create a session."""
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        ttl = ttl_hours or 24
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)
        
        session = Session(
            id=session_id,
            user_id=user_id,
            agent_type=agent_type,
            expires_at=expires_at,
        )
        
        self._sessions[session_id] = session
        return session

    async def save(self, session: Session) -> None:
        """Save a session."""
        self._sessions[session.id] = session

    async def add_message(
        self,
        session_id: str,
        message: MessageData,
    ) -> str:
        """Add a message to a session."""
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        
        session.add_message(message)
        return message.id

    async def get_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
    ) -> list[MessageData]:
        """Get messages from a session."""
        session = self._sessions.get(session_id)
        if session is None:
            return []
        
        messages = session.messages
        
        if since:
            messages = [m for m in messages if m.created_at > since]
        
        if limit:
            messages = messages[-limit:]
        
        return messages

    async def delete(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._checkpoints.pop(session_id, None)
            return True
        return False

    async def cleanup_expired(self) -> int:
        """Clean up expired sessions."""
        now = datetime.now(timezone.utc)
        expired = [
            sid for sid, s in self._sessions.items()
            if s.expires_at and s.expires_at < now
        ]
        
        for sid in expired:
            del self._sessions[sid]
            self._checkpoints.pop(sid, None)
        
        return len(expired)

    async def create_checkpoint(
        self,
        session_id: str,
        thread_id: str,
        state: dict,
        parent_checkpoint_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Checkpoint:
        """Create a checkpoint."""
        checkpoint = Checkpoint(
            session_id=session_id,
            thread_id=thread_id,
            checkpoint_id=str(uuid4()),
            parent_checkpoint_id=parent_checkpoint_id,
            state=state,
            metadata=metadata or {},
        )
        
        if session_id not in self._checkpoints:
            self._checkpoints[session_id] = []
        
        self._checkpoints[session_id].append(checkpoint)
        return checkpoint

    async def get_latest_checkpoint(
        self,
        session_id: str,
        thread_id: str,
    ) -> Optional[Checkpoint]:
        """Get the latest checkpoint."""
        checkpoints = self._checkpoints.get(session_id, [])
        matching = [c for c in checkpoints if c.thread_id == thread_id]
        
        if not matching:
            return None
        
        return max(matching, key=lambda c: c.created_at)

    async def list_sessions(
        self,
        user_id: Optional[int] = None,
        agent_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions."""
        sessions = list(self._sessions.values())
        
        if user_id is not None:
            sessions = [s for s in sessions if s.user_id == user_id]
        
        if agent_type is not None:
            sessions = [s for s in sessions if s.agent_type == agent_type]
        
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        
        return sessions[:limit]

    def clear(self) -> None:
        """Clear all data."""
        self._sessions.clear()
        self._checkpoints.clear()
