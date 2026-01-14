"""Unit tests for the session module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agentcore.inference import MessageRole
from agentcore.session.models import (
    Checkpoint,
    MessageData,
    Session,
)
from agentcore.session.store import MockSessionStore


class TestMessageData:
    def test_create_message(self):
        msg = MessageData(
            role=MessageRole.USER,
            content="Hello",
        )
        
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert msg.id is not None
        assert msg.created_at is not None
    
    def test_to_openai_format_user(self):
        msg = MessageData(
            role=MessageRole.USER,
            content="Hello",
        )
        
        openai_msg = msg.to_openai_format()
        
        assert openai_msg["role"] == "user"
        assert openai_msg["content"] == "Hello"
    
    def test_to_openai_format_tool(self):
        msg = MessageData(
            role=MessageRole.TOOL,
            content='{"result": 42}',
            tool_call_id="call_123",
        )
        
        openai_msg = msg.to_openai_format()
        
        assert openai_msg["role"] == "tool"
        assert openai_msg["tool_call_id"] == "call_123"
    
    def test_to_openai_format_assistant_with_tools(self):
        msg = MessageData(
            role=MessageRole.ASSISTANT,
            content=None,
            tool_calls=[
                {"id": "call_1", "type": "function", "function": {"name": "search"}}
            ],
        )
        
        openai_msg = msg.to_openai_format()
        
        assert openai_msg["role"] == "assistant"
        assert len(openai_msg["tool_calls"]) == 1


class TestSession:
    def test_create_session(self):
        session = Session(
            user_id=1,
            agent_type="purchasing",
        )
        
        assert session.id is not None
        assert session.user_id == 1
        assert session.agent_type == "purchasing"
        assert session.message_count == 0
    
    def test_add_message(self):
        session = Session(user_id=1, agent_type="test")
        msg = MessageData(role=MessageRole.USER, content="Hello")
        
        session.add_message(msg)
        
        assert session.message_count == 1
        assert session.messages[0].content == "Hello"
    
    def test_get_messages_with_limit(self):
        session = Session(user_id=1, agent_type="test")
        
        for i in range(10):
            session.add_message(
                MessageData(role=MessageRole.USER, content=f"Message {i}")
            )
        
        recent = session.get_messages(limit=3)
        
        assert len(recent) == 3
        assert recent[0].content == "Message 7"
        assert recent[2].content == "Message 9"
    
    def test_get_messages_by_role(self):
        session = Session(user_id=1, agent_type="test")
        session.add_message(MessageData(role=MessageRole.USER, content="User 1"))
        session.add_message(MessageData(role=MessageRole.ASSISTANT, content="Asst 1"))
        session.add_message(MessageData(role=MessageRole.USER, content="User 2"))
        
        user_messages = session.get_messages(roles=[MessageRole.USER])
        
        assert len(user_messages) == 2
    
    def test_get_openai_messages(self):
        session = Session(user_id=1, agent_type="test")
        session.add_message(
            MessageData(role=MessageRole.SYSTEM, content="You are helpful")
        )
        session.add_message(MessageData(role=MessageRole.USER, content="Hi"))
        session.add_message(MessageData(role=MessageRole.ASSISTANT, content="Hello"))
        
        all_msgs = session.get_openai_messages()
        assert len(all_msgs) == 3
        
        no_system = session.get_openai_messages(include_system=False)
        assert len(no_system) == 2
    
    def test_clear_messages(self):
        session = Session(user_id=1, agent_type="test")
        session.add_message(MessageData(role=MessageRole.USER, content="Hello"))
        
        session.clear_messages()
        
        assert session.message_count == 0
    
    def test_state_operations(self):
        session = Session(user_id=1, agent_type="test")
        
        session.set_state("key1", "value1")
        session.set_state("key2", 42)
        
        assert session.get_state("key1") == "value1"
        assert session.get_state("key2") == 42
        assert session.get_state("missing", "default") == "default"
    
    def test_is_expired(self):
        not_expired = Session(
            user_id=1,
            agent_type="test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        
        expired = Session(
            user_id=1,
            agent_type="test",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        
        no_expiry = Session(
            user_id=1,
            agent_type="test",
            expires_at=None,
        )
        
        assert not_expired.is_expired is False
        assert expired.is_expired is True
        assert no_expiry.is_expired is False
    
    def test_duration_seconds(self):
        created = datetime.now(timezone.utc)
        session = Session(
            user_id=1,
            agent_type="test",
            created_at=created,
            updated_at=created + timedelta(seconds=60),
        )
        
        assert session.duration_seconds == 60.0


class TestCheckpoint:
    def test_create_checkpoint(self):
        checkpoint = Checkpoint(
            session_id="sess-123",
            thread_id="thread-1",
            checkpoint_id="cp-1",
            state={"step": 3, "context": "test"},
        )
        
        assert checkpoint.id is not None
        assert checkpoint.session_id == "sess-123"
        assert checkpoint.thread_id == "thread-1"
        assert checkpoint.state["step"] == 3


class TestMockSessionStore:
    @pytest.fixture
    def store(self) -> MockSessionStore:
        return MockSessionStore()
    
    @pytest.mark.asyncio
    async def test_get_nonexistent(self, store):
        result = await store.get("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_or_create_new(self, store):
        session = await store.get_or_create(
            session_id="sess-1",
            user_id=1,
            agent_type="test",
        )
        
        assert session.id == "sess-1"
        assert session.user_id == 1
        assert session.expires_at is not None
    
    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, store):
        session1 = await store.get_or_create("sess-1", 1, "test")
        session1.set_state("key", "value")
        await store.save(session1)
        
        session2 = await store.get_or_create("sess-1", 1, "test")
        
        assert session2.get_state("key") == "value"
    
    @pytest.mark.asyncio
    async def test_save_and_get(self, store):
        session = Session(id="sess-1", user_id=1, agent_type="test")
        session.set_state("test_key", "test_value")
        
        await store.save(session)
        
        retrieved = await store.get("sess-1")
        assert retrieved is not None
        assert retrieved.get_state("test_key") == "test_value"
    
    @pytest.mark.asyncio
    async def test_add_message(self, store):
        await store.get_or_create("sess-1", 1, "test")
        
        msg_id = await store.add_message(
            "sess-1",
            MessageData(role=MessageRole.USER, content="Hello"),
        )
        
        assert msg_id is not None
        
        messages = await store.get_messages("sess-1")
        assert len(messages) == 1
        assert messages[0].content == "Hello"
    
    @pytest.mark.asyncio
    async def test_add_message_to_nonexistent_session(self, store):
        with pytest.raises(ValueError, match="not found"):
            await store.add_message(
                "nonexistent",
                MessageData(role=MessageRole.USER, content="Hello"),
            )
    
    @pytest.mark.asyncio
    async def test_get_messages_with_limit(self, store):
        await store.get_or_create("sess-1", 1, "test")
        
        for i in range(5):
            await store.add_message(
                "sess-1",
                MessageData(role=MessageRole.USER, content=f"Msg {i}"),
            )
        
        messages = await store.get_messages("sess-1", limit=2)
        
        assert len(messages) == 2
        assert messages[0].content == "Msg 3"
        assert messages[1].content == "Msg 4"
    
    @pytest.mark.asyncio
    async def test_delete(self, store):
        await store.get_or_create("sess-1", 1, "test")
        
        result = await store.delete("sess-1")
        assert result is True
        
        session = await store.get("sess-1")
        assert session is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, store):
        result = await store.delete("nonexistent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_cleanup_expired(self, store):
        session1 = await store.get_or_create("sess-1", 1, "test")
        session1.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await store.save(session1)
        
        session2 = await store.get_or_create("sess-2", 1, "test")
        session2.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await store.save(session2)
        
        count = await store.cleanup_expired()
        
        assert count == 1
        assert await store.get("sess-1") is None
        assert await store.get("sess-2") is not None
    
    @pytest.mark.asyncio
    async def test_create_and_get_checkpoint(self, store):
        await store.get_or_create("sess-1", 1, "test")
        
        checkpoint = await store.create_checkpoint(
            session_id="sess-1",
            thread_id="thread-1",
            state={"step": 2},
        )
        
        assert checkpoint.session_id == "sess-1"
        assert checkpoint.thread_id == "thread-1"
        
        latest = await store.get_latest_checkpoint("sess-1", "thread-1")
        
        assert latest is not None
        assert latest.state["step"] == 2
    
    @pytest.mark.asyncio
    async def test_get_latest_checkpoint_multiple(self, store):
        await store.get_or_create("sess-1", 1, "test")
        
        await store.create_checkpoint("sess-1", "thread-1", {"step": 1})
        await store.create_checkpoint("sess-1", "thread-1", {"step": 2})
        await store.create_checkpoint("sess-1", "thread-1", {"step": 3})
        
        latest = await store.get_latest_checkpoint("sess-1", "thread-1")
        
        assert latest.state["step"] == 3
    
    @pytest.mark.asyncio
    async def test_list_sessions(self, store):
        await store.get_or_create("sess-1", 1, "purchasing")
        await store.get_or_create("sess-2", 1, "purchasing")
        await store.get_or_create("sess-3", 2, "payables")
        
        all_sessions = await store.list_sessions()
        assert len(all_sessions) == 3
        
        user_sessions = await store.list_sessions(user_id=1)
        assert len(user_sessions) == 2
        
        type_sessions = await store.list_sessions(agent_type="payables")
        assert len(type_sessions) == 1
    
    @pytest.mark.asyncio
    async def test_list_sessions_with_limit(self, store):
        for i in range(10):
            await store.get_or_create(f"sess-{i}", 1, "test")
        
        sessions = await store.list_sessions(limit=3)
        
        assert len(sessions) == 3
    
    def test_clear(self, store):
        store._sessions["sess-1"] = Session(id="sess-1", user_id=1, agent_type="test")
        store._checkpoints["sess-1"] = []
        
        store.clear()
        
        assert len(store._sessions) == 0
        assert len(store._checkpoints) == 0
