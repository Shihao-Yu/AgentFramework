"""Unit tests for transport module."""

import json
import pytest
from uuid import uuid4

from agentcore.transport.models import (
    MessageType,
    AuthMessage,
    QueryMessage,
    HumanInputMessage,
    HumanInputPayload,
    AuthResponse,
    SuggestionsMessage,
    ProgressMessage,
    UIInteractionMessage,
    UIFieldOptionsMessage,
    MarkdownMessage,
    ErrorMessage,
    Locale,
    UserAgent,
    Attachment,
    FormField,
    FormDefinition,
    UserInfo,
    EnrichedUserInfo,
)
from agentcore.transport.parser import parse_message, ParseError, serialize_message


class TestMessageModels:
    """Tests for message models."""

    def test_auth_message(self):
        msg = AuthMessage(token="test-token", language="en-US")
        
        assert msg.type == "auth"
        assert msg.token == "test-token"
        assert msg.language == "en-US"
        assert msg.loadBotIntro is False

    def test_query_message(self):
        msg = QueryMessage(
            query="Find PO 12345",
            session_id="session-123",
            question_answer_uuid=str(uuid4()),
        )
        
        assert msg.type == "query"
        assert msg.query == "Find PO 12345"
        assert msg.session_id == "session-123"
        assert msg.locale.language == "en-US"

    def test_query_message_with_attachments(self):
        attachment = Attachment(
            fileName="test.pdf",
            size=1024,
            type="application/pdf",
            reference="ref/123",
        )
        msg = QueryMessage(
            query="Process this",
            session_id="session-123",
            question_answer_uuid=str(uuid4()),
            attachments=[attachment],
        )
        
        assert len(msg.attachments) == 1
        assert msg.attachments[0].fileName == "test.pdf"

    def test_human_input_message(self):
        msg = HumanInputMessage(
            payload=HumanInputPayload(
                interaction_id="int-123",
                form_id="form-123",
                values={"field1": "value1"},
                session_id="session-123",
            )
        )
        
        assert msg.type == "human_input"
        assert msg.payload.interaction_id == "int-123"
        assert msg.payload.values["field1"] == "value1"

    def test_auth_response_success(self):
        user_info = UserInfo(upn="user@test.com", email="user@test.com")
        enriched = EnrichedUserInfo(
            user_id=1,
            display_name="Test User",
            email="user@test.com",
            permissions=["Admin", "Buyer"],
        )
        
        response = AuthResponse.success(user_info, enriched)
        
        assert response.type == "auth"
        assert response.payload.status == "success"
        assert response.payload.user.email == "user@test.com"
        assert "Admin" in response.payload.enriched.permissions

    def test_auth_response_error(self):
        response = AuthResponse.error("Invalid token")
        
        assert response.type == "auth"
        assert response.payload.status == "error"
        assert response.payload.message == "Invalid token"

    def test_suggestions_message(self):
        msg = SuggestionsMessage.create(["Option 1", "Option 2"])
        
        assert msg.type == "suggestions"
        assert len(msg.payload.options) == 2
        assert msg.payload.options[0].label == "Option 1"
        assert msg.payload.options[0].value == "Option 1"

    def test_progress_message(self):
        msg = ProgressMessage.create("Thinking")
        
        assert msg.type == "component"
        assert msg.payload.component == "progress"
        assert msg.payload.data.status == "Thinking"

    def test_progress_message_shortcuts(self):
        assert ProgressMessage.thinking().payload.data.status == "Thinking"
        assert ProgressMessage.retrieving().payload.data.status == "Retrieving information"
        assert ProgressMessage.processing().payload.data.status == "Processing"
        assert ProgressMessage.complete().payload.data.status == "_synthesis_complete"

    def test_ui_interaction_message_form(self):
        form = FormDefinition(
            id="test-form",
            fields=[
                FormField(key="name", label="Name", type="text", required=True),
                FormField(key="age", label="Age", type="number"),
            ]
        )
        
        msg = UIInteractionMessage.create_form("int-123", form)
        
        assert msg.type == "component"
        assert msg.payload.component == "ui_interaction"
        assert msg.payload.data.interaction_id == "int-123"
        assert msg.payload.data.form.id == "test-form"
        assert len(msg.payload.data.form.fields) == 2

    def test_ui_interaction_message_confirm(self):
        msg = UIInteractionMessage.create_confirm("int-123", "Are you sure?")
        
        assert msg.type == "component"
        assert msg.payload.data.interaction_id == "int-123"
        assert msg.payload.data.form.fields[0].type == "confirm"

    def test_markdown_message(self):
        msg = MarkdownMessage.create("## Hello\n\nWorld")
        
        assert msg.type == "markdown"
        assert msg.payload == "## Hello\n\nWorld"

    def test_error_message(self):
        msg = ErrorMessage.create("Something went wrong", code="SERVER_ERROR")
        
        assert msg.type == "component"
        assert msg.payload.component == "error"
        assert msg.payload.data.message == "Something went wrong"
        assert msg.payload.data.code == "SERVER_ERROR"

    def test_error_message_shortcuts(self):
        validation_err = ErrorMessage.validation_error("Field required", "name")
        assert validation_err.payload.data.code == "VALIDATION_ERROR"
        assert validation_err.payload.data.field == "name"
        
        auth_err = ErrorMessage.auth_error("Invalid token")
        assert auth_err.payload.data.code == "AUTH_ERROR"


class TestParser:
    """Tests for message parser."""

    def test_parse_auth_message_string(self):
        data = json.dumps({
            "type": "auth",
            "token": "test-token",
            "language": "en",
        })
        
        msg = parse_message(data)
        
        assert isinstance(msg, AuthMessage)
        assert msg.token == "test-token"

    def test_parse_auth_message_bytes(self):
        data = json.dumps({
            "type": "auth",
            "token": "test-token",
        }).encode("utf-8")
        
        msg = parse_message(data)
        
        assert isinstance(msg, AuthMessage)

    def test_parse_auth_message_dict(self):
        data = {
            "type": "auth",
            "token": "test-token",
        }
        
        msg = parse_message(data)
        
        assert isinstance(msg, AuthMessage)

    def test_parse_query_message(self):
        data = {
            "type": "query",
            "query": "Find PO 12345",
            "session_id": "session-123",
            "question_answer_uuid": "uuid-123",
            "locale": {"location": "America/New_York", "language": "en-US"},
        }
        
        msg = parse_message(data)
        
        assert isinstance(msg, QueryMessage)
        assert msg.query == "Find PO 12345"
        assert msg.locale.location == "America/New_York"

    def test_parse_human_input_message(self):
        data = {
            "type": "human_input",
            "payload": {
                "interaction_id": "int-123",
                "form_id": "form-123",
                "values": {"field1": "value1"},
                "session_id": "session-123",
            }
        }
        
        msg = parse_message(data)
        
        assert isinstance(msg, HumanInputMessage)
        assert msg.payload.values["field1"] == "value1"

    def test_parse_invalid_json(self):
        with pytest.raises(ParseError) as exc_info:
            parse_message("not valid json")
        
        assert "Invalid JSON" in str(exc_info.value)

    def test_parse_missing_type(self):
        with pytest.raises(ParseError) as exc_info:
            parse_message({"token": "test"})
        
        assert "Missing 'type' field" in str(exc_info.value)

    def test_parse_unknown_type(self):
        with pytest.raises(ParseError) as exc_info:
            parse_message({"type": "unknown_type"})
        
        assert "Unknown message type" in str(exc_info.value)

    def test_parse_validation_error(self):
        with pytest.raises(ParseError) as exc_info:
            parse_message({"type": "query"})
        
        assert "Validation error" in str(exc_info.value)


class TestSerializer:
    """Tests for message serialization."""

    def test_serialize_auth_response(self):
        response = AuthResponse.error("Test error")
        
        json_str = serialize_message(response)
        data = json.loads(json_str)
        
        assert data["type"] == "auth"
        assert data["payload"]["status"] == "error"
        assert data["payload"]["message"] == "Test error"

    def test_serialize_progress_message(self):
        msg = ProgressMessage.thinking()
        
        json_str = serialize_message(msg)
        data = json.loads(json_str)
        
        assert data["type"] == "component"
        assert data["payload"]["component"] == "progress"
        assert data["payload"]["data"]["status"] == "Thinking"

    def test_serialize_markdown_message(self):
        msg = MarkdownMessage.create("Hello **world**")
        
        json_str = serialize_message(msg)
        data = json.loads(json_str)
        
        assert data["type"] == "markdown"
        assert data["payload"] == "Hello **world**"

    def test_serialize_suggestions_message(self):
        msg = SuggestionsMessage.create(["A", "B", "C"])
        
        json_str = serialize_message(msg)
        data = json.loads(json_str)
        
        assert data["type"] == "suggestions"
        assert len(data["payload"]["options"]) == 3


class TestFormModels:
    """Tests for form-related models."""

    def test_form_field_with_data_source(self):
        from agentcore.transport.models import DataSource
        
        ds = DataSource(
            provider="get_supplier",
            minChars=2,
            debounceMs=300,
            pageSize=20,
        )
        
        field = FormField(
            key="supplier",
            label="Supplier",
            type="select",
            required=True,
            searchable=True,
            async_=True,
            dataSource=ds,
        )
        
        assert field.dataSource.provider == "get_supplier"
        assert field.async_ is True

    def test_form_definition(self):
        form = FormDefinition(
            id="test-form",
            fields=[
                FormField(key="name", label="Name", type="text"),
                FormField(key="email", label="Email", type="text"),
            ]
        )
        
        assert form.id == "test-form"
        assert len(form.fields) == 2

    def test_ui_field_options_message(self):
        from agentcore.transport.models import UIFieldOptionsPayload
        
        msg = UIFieldOptionsMessage(
            payload=UIFieldOptionsPayload(
                interaction_id="int-123",
                form_id="form-123",
                field_key="supplier",
                options=[
                    {"label": "Supplier A", "value": {"id": 1, "name": "Supplier A"}},
                    {"label": "Supplier B", "value": {"id": 2, "name": "Supplier B"}},
                ]
            )
        )
        
        assert msg.type == "ui_field_options"
        assert len(msg.payload.options) == 2


class TestMessageType:
    """Tests for MessageType enum."""

    def test_message_types(self):
        assert MessageType.AUTH.value == "auth"
        assert MessageType.QUERY.value == "query"
        assert MessageType.HUMAN_INPUT.value == "human_input"
        assert MessageType.COMPONENT.value == "component"
        assert MessageType.SUGGESTIONS.value == "suggestions"
        assert MessageType.MARKDOWN.value == "markdown"
