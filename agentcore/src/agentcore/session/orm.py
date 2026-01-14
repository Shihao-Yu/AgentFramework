"""SQLAlchemy ORM models for session persistence."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _get_db_schema() -> str:
    return os.environ.get("SESSION_DB_SCHEMA", "agent")


_SCHEMA = _get_db_schema()


class Base(DeclarativeBase):
    """Base class for ORM models."""
    pass


class SessionModel(Base):
    """SQLAlchemy model for agent sessions."""

    __tablename__ = "agent_sessions"
    __table_args__ = (
        Index("ix_sessions_user_agent", "user_id", "agent_type"),
        Index("ix_sessions_expires", "expires_at"),
        {"schema": _SCHEMA},
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    agent_type = Column(String(50), nullable=False, index=True)
    state = Column(JSON, default=dict, nullable=False)
    blackboard = Column(JSON, default=dict, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)

    messages = relationship(
        "MessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="MessageModel.created_at",
    )
    checkpoints = relationship(
        "CheckpointModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="CheckpointModel.created_at",
    )


class MessageModel(Base):
    """SQLAlchemy model for session messages."""

    __tablename__ = "agent_messages"
    __table_args__ = (
        Index("ix_messages_session_created", "session_id", "created_at"),
        {"schema": _SCHEMA},
    )

    id = Column(String(36), primary_key=True)
    session_id = Column(
        String(36),
        ForeignKey(f"{_SCHEMA}.agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=True)
    name = Column(String(100), nullable=True)
    tool_call_id = Column(String(100), nullable=True)
    tool_calls = Column(JSON, nullable=True)
    extra_metadata = Column(JSON, default=dict, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    session = relationship("SessionModel", back_populates="messages")


class CheckpointModel(Base):
    """SQLAlchemy model for session checkpoints."""

    __tablename__ = "agent_checkpoints"
    __table_args__ = (
        Index("ix_checkpoints_session_thread", "session_id", "thread_id"),
        Index("ix_checkpoints_checkpoint", "checkpoint_id"),
        {"schema": _SCHEMA},
    )

    id = Column(String(36), primary_key=True)
    session_id = Column(
        String(36),
        ForeignKey(f"{_SCHEMA}.agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id = Column(String(100), nullable=False, index=True)
    checkpoint_id = Column(String(100), nullable=False)
    parent_checkpoint_id = Column(String(100), nullable=True)
    state = Column(JSON, nullable=False)
    extra_metadata = Column(JSON, default=dict, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    session = relationship("SessionModel", back_populates="checkpoints")
