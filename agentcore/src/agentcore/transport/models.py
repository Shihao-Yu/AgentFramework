"""Chat contract message models for WebSocket communication."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional, Union
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Message types in the chat contract."""
    AUTH = "auth"
    QUERY = "query"
    HUMAN_INPUT = "human_input"
    COMPONENT = "component"
    SUGGESTIONS = "suggestions"
    UI_FIELD_OPTIONS = "ui_field_options"
    MARKDOWN = "markdown"


class Locale(BaseModel):
    """User locale settings."""
    location: str = "America/Los_Angeles"
    language: str = "en-US"


class UserAgent(BaseModel):
    """Application/module context."""
    type: str = "Default"


class Attachment(BaseModel):
    """File attachment."""
    fileName: str
    size: int
    type: str
    reference: str


class AuthMessage(BaseModel):
    """UI -> Agent: Initial authentication message."""
    type: str = Field(default="auth", frozen=True)
    token: str
    loadBotIntro: bool = False
    language: str = "en"


class QueryMessage(BaseModel):
    """UI -> Agent: User query with full context."""
    type: str = Field(default="query", frozen=True)
    locale: Locale = Field(default_factory=Locale)
    user_id: str = ""
    user_name: str = ""
    user_agent: UserAgent = Field(default_factory=UserAgent)
    query: str
    selected_docs: list[str] = Field(default_factory=list)
    question_answer_uuid: str
    session_id: str
    include_eod_marker: bool = True
    personalized: bool = False
    attachments: list[Attachment] = Field(default_factory=list)
    context: str = "{}"


class HumanInputPayload(BaseModel):
    """Payload for human input message."""
    interaction_id: str
    form_id: str
    values: dict[str, Any]
    clear_previous_message: bool = False
    session_id: str


class HumanInputMessage(BaseModel):
    """UI -> Agent: Form submission message."""
    type: str = Field(default="human_input", frozen=True)
    payload: HumanInputPayload


class UserInfo(BaseModel):
    """Raw user info from token."""
    upn: str = ""
    name: str = ""
    email: str = ""
    groups: list[str] = Field(default_factory=list)
    claims: dict[str, Any] = Field(default_factory=dict)
    is_azure: bool = False
    adusername: str = ""


class EnrichedUserInfo(BaseModel):
    """Extended user profile from database."""
    user_id: int
    ad_username: str = ""
    super_user: bool = False
    enabled: bool = True
    first_name: str = ""
    last_name: str = ""
    display_name: str = ""
    email: str = ""
    department: str = ""
    title: str = ""
    buyer: bool = False
    planner: bool = False
    e_procurement: bool = False
    permissions: list[str] = Field(default_factory=list)


class AuthResponsePayload(BaseModel):
    """Payload for auth response."""
    status: str
    message: str
    user: Optional[UserInfo] = None
    enriched: Optional[EnrichedUserInfo] = None


class AuthResponse(BaseModel):
    """Agent -> UI: Authentication response."""
    type: str = Field(default="auth", frozen=True)
    payload: AuthResponsePayload

    @classmethod
    def success(
        cls,
        user: UserInfo,
        enriched: EnrichedUserInfo,
    ) -> "AuthResponse":
        return cls(
            payload=AuthResponsePayload(
                status="success",
                message="authenticated",
                user=user,
                enriched=enriched,
            )
        )

    @classmethod
    def error(cls, message: str) -> "AuthResponse":
        return cls(
            payload=AuthResponsePayload(
                status="error",
                message=message,
            )
        )


class SuggestionOption(BaseModel):
    """A single suggestion option."""
    label: str
    value: str


class SuggestionsPayload(BaseModel):
    """Payload for suggestions message."""
    field: str = "suggestions"
    options: list[SuggestionOption]


class SuggestionsMessage(BaseModel):
    """Agent -> UI: Suggested queries."""
    type: str = Field(default="suggestions", frozen=True)
    payload: SuggestionsPayload

    @classmethod
    def create(cls, suggestions: list[str]) -> "SuggestionsMessage":
        return cls(
            payload=SuggestionsPayload(
                options=[
                    SuggestionOption(label=s, value=s) for s in suggestions
                ]
            )
        )


class ProgressData(BaseModel):
    """Progress indicator data."""
    status: str


class ProgressPayload(BaseModel):
    """Payload for progress message."""
    component: str = "progress"
    data: ProgressData


class ProgressMessage(BaseModel):
    """Agent -> UI: Progress indicator."""
    type: str = Field(default="component", frozen=True)
    payload: ProgressPayload

    @classmethod
    def create(cls, status: str) -> "ProgressMessage":
        return cls(
            payload=ProgressPayload(
                data=ProgressData(status=status)
            )
        )

    @classmethod
    def thinking(cls) -> "ProgressMessage":
        return cls.create("Thinking")

    @classmethod
    def retrieving(cls) -> "ProgressMessage":
        return cls.create("Retrieving information")

    @classmethod
    def processing(cls) -> "ProgressMessage":
        return cls.create("Processing")

    @classmethod
    def complete(cls) -> "ProgressMessage":
        return cls.create("_synthesis_complete")


class DataSource(BaseModel):
    """Async data source configuration for form fields."""
    provider: str
    minChars: int = 0
    debounceMs: int = 300
    pageSize: int = 10
    extraParams: dict[str, Any] = Field(default_factory=dict)


class FormField(BaseModel):
    """A form field definition."""
    key: str
    label: str
    type: str
    required: bool = False
    helpText: str = ""
    placeholder: str = ""
    searchable: bool = False
    async_: bool = Field(default=False, alias="async")
    dataSource: Optional[DataSource] = None
    options: list[dict[str, Any]] = Field(default_factory=list)
    defaultValue: Optional[Any] = None
    
    model_config = {"populate_by_name": True}


class TableColumn(BaseModel):
    """A table column definition."""
    key: str
    label: str
    type: str = "text"
    required: bool = False
    textAlign: str = "start"


class TableRow(BaseModel):
    """A table row."""
    id: str
    selected: bool = False
    data: dict[str, Any] = Field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        if name in self.data:
            return self.data[name]
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")


class FormDefinition(BaseModel):
    """A form definition."""
    id: str
    fields: list[FormField]


class UIInteractionData(BaseModel):
    """UI interaction data."""
    interaction_id: str
    component_type: str = "form"
    required: bool = True
    form: Optional[FormDefinition] = None


class UIInteractionPayload(BaseModel):
    """Payload for UI interaction message."""
    component: str = "ui_interaction"
    data: UIInteractionData


class UIInteractionMessage(BaseModel):
    """Agent -> UI: Interactive form."""
    type: str = Field(default="component", frozen=True)
    payload: UIInteractionPayload

    @classmethod
    def create_form(
        cls,
        interaction_id: str,
        form: FormDefinition,
        required: bool = True,
    ) -> "UIInteractionMessage":
        return cls(
            payload=UIInteractionPayload(
                data=UIInteractionData(
                    interaction_id=interaction_id,
                    component_type="form",
                    required=required,
                    form=form,
                )
            )
        )

    @classmethod
    def create_confirm(
        cls,
        interaction_id: str,
        prompt: str,
    ) -> "UIInteractionMessage":
        form = FormDefinition(
            id=interaction_id,
            fields=[
                FormField(
                    key="confirm",
                    label=prompt,
                    type="confirm",
                    required=True,
                )
            ],
        )
        return cls.create_form(interaction_id, form, required=True)


class UIFieldOptionsPayload(BaseModel):
    """Payload for UI field options."""
    interaction_id: str
    form_id: str
    field_key: str
    client_request_id: str = ""
    options: list[dict[str, Any]]


class UIFieldOptionsMessage(BaseModel):
    """Agent -> UI: Async field options."""
    type: str = Field(default="ui_field_options", frozen=True)
    payload: UIFieldOptionsPayload


class MarkdownMessage(BaseModel):
    """Agent -> UI: Rich text content."""
    type: str = Field(default="markdown", frozen=True)
    payload: str

    @classmethod
    def create(cls, content: str) -> "MarkdownMessage":
        return cls(payload=content)


class ErrorData(BaseModel):
    """Error data."""
    code: str = "ERROR"
    message: str
    field: Optional[str] = None


class ErrorPayload(BaseModel):
    """Payload for error message."""
    component: str = "error"
    data: ErrorData


class ErrorMessage(BaseModel):
    """Agent -> UI: Error message."""
    type: str = Field(default="component", frozen=True)
    payload: ErrorPayload

    @classmethod
    def create(
        cls,
        message: str,
        code: str = "ERROR",
        field: Optional[str] = None,
    ) -> "ErrorMessage":
        return cls(
            payload=ErrorPayload(
                data=ErrorData(code=code, message=message, field=field)
            )
        )

    @classmethod
    def validation_error(cls, message: str, field: str) -> "ErrorMessage":
        return cls.create(message, code="VALIDATION_ERROR", field=field)

    @classmethod
    def auth_error(cls, message: str) -> "ErrorMessage":
        return cls.create(message, code="AUTH_ERROR")


IncomingMessage = Union[AuthMessage, QueryMessage, HumanInputMessage]
OutgoingMessage = Union[
    AuthResponse,
    SuggestionsMessage,
    ProgressMessage,
    UIInteractionMessage,
    UIFieldOptionsMessage,
    MarkdownMessage,
    ErrorMessage,
]
