"""
Utility functions for ContextForge.

Provides serialization helpers to reduce boilerplate code in storage layer.
"""

import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def to_json_dict(obj: Any) -> Dict[str, Any]:
    """
    Convert a dataclass instance to a JSON-serializable dictionary.

    Handles datetime objects by converting them to ISO format strings.

    Args:
        obj: A dataclass instance

    Returns:
        Dictionary with JSON-serializable values

    Raises:
        TypeError: If obj is not a dataclass instance

    Example:
        >>> @dataclass
        ... class User:
        ...     name: str
        ...     created_at: datetime
        >>> user = User("Alice", datetime(2024, 1, 1))
        >>> to_json_dict(user)
        {'name': 'Alice', 'created_at': '2024-01-01T00:00:00'}
    """
    if not is_dataclass(obj):
        raise TypeError(f"Expected dataclass instance, got {type(obj).__name__}")

    data = asdict(obj)

    # Recursively handle datetime serialization
    return _convert_datetimes(data)


def _convert_datetimes(data: Any) -> Any:
    """
    Recursively convert datetime objects to ISO format strings.

    Args:
        data: Any data structure (dict, list, datetime, or primitive)

    Returns:
        Data structure with datetime objects converted to strings
    """
    if isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, dict):
        return {key: _convert_datetimes(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_convert_datetimes(item) for item in data]
    else:
        return data


def to_json(obj: Any, ensure_ascii: bool = False) -> str:
    """
    Serialize a dataclass instance to a JSON string.

    Args:
        obj: A dataclass instance
        ensure_ascii: Whether to escape non-ASCII characters (default: False)

    Returns:
        JSON string representation

    Raises:
        TypeError: If obj is not a dataclass instance

    Example:
        >>> @dataclass
        ... class User:
        ...     name: str
        >>> to_json(User("Alice"))
        '{"name": "Alice"}'
    """
    json_dict = to_json_dict(obj)
    return json.dumps(json_dict, ensure_ascii=ensure_ascii)


def from_json_dict(data: Dict[str, Any], cls: Type[T]) -> T:
    """
    Construct a dataclass instance from a JSON-parsed dictionary.

    Handles datetime fields by parsing ISO format strings.

    Args:
        data: Dictionary from json.loads()
        cls: Dataclass type to construct

    Returns:
        Instance of cls

    Raises:
        TypeError: If cls is not a dataclass
        ValueError: If required fields are missing

    Example:
        >>> @dataclass
        ... class User:
        ...     name: str
        ...     created_at: datetime
        >>> data = {'name': 'Alice', 'created_at': '2024-01-01T00:00:00'}
        >>> from_json_dict(data, User)
        User(name='Alice', created_at=datetime(2024, 1, 1))
    """
    if not is_dataclass(cls):
        raise TypeError(f"Expected dataclass type, got {cls.__name__}")

    # Parse datetime fields based on type hints
    if hasattr(cls, "__annotations__"):
        for field_name, field_type in cls.__annotations__.items():
            if field_name in data:
                value = data[field_name]

                # Handle datetime fields
                if field_type == datetime or (
                    hasattr(field_type, "__origin__")
                    and field_type.__origin__ is type(None)
                    and datetime in getattr(field_type, "__args__", [])
                ):
                    if isinstance(value, str):
                        try:
                            data[field_name] = datetime.fromisoformat(value)
                        except (ValueError, TypeError):
                            # Keep original value if parsing fails
                            pass

    return cls(**data)


def from_json(json_str: str, cls: Type[T]) -> T:
    """
    Deserialize a JSON string to a dataclass instance.

    Args:
        json_str: JSON string representation
        cls: Dataclass type to construct

    Returns:
        Instance of cls

    Raises:
        TypeError: If cls is not a dataclass
        ValueError: If JSON is invalid or required fields are missing

    Example:
        >>> @dataclass
        ... class User:
        ...     name: str
        >>> from_json('{"name": "Alice"}', User)
        User(name='Alice')
    """
    data = json.loads(json_str)
    return from_json_dict(data, cls)


def serialize_for_storage(obj: Any, embedding_fields: List[str]) -> tuple:
    """
    Serialize a dataclass for vector storage with separate embedding text.

    Extracts specified fields to create embedding text while serializing
    the full object to JSON for document storage.

    Args:
        obj: Dataclass instance to serialize
        embedding_fields: List of field names to include in embedding text

    Returns:
        Tuple of (json_document, embedding_text)

    Example:
        >>> @dataclass
        ... class Field:
        ...     name: str
        ...     description: str
        ...     internal_id: int
        >>> field = Field("user_id", "Unique user identifier", 123)
        >>> doc, embed = serialize_for_storage(field, ["name", "description"])
        >>> embed
        'user_id Unique user identifier'
    """
    if not is_dataclass(obj):
        raise TypeError(f"Expected dataclass instance, got {type(obj).__name__}")

    # Serialize full object
    json_document = to_json(obj, ensure_ascii=False)

    # Extract embedding fields
    embedding_parts = []
    for field_name in embedding_fields:
        if hasattr(obj, field_name):
            value = getattr(obj, field_name)
            if value:  # Skip None or empty values
                if isinstance(value, list):
                    embedding_parts.extend(str(v) for v in value if v)
                else:
                    embedding_parts.append(str(value))

    embedding_text = " ".join(embedding_parts)

    return json_document, embedding_text


# Validation helpers


def validate_required_fields(obj: Any, required_fields: List[str]) -> List[str]:
    """
    Validate that required fields are present and non-empty.

    Args:
        obj: Dataclass instance to validate
        required_fields: List of field names that must be present

    Returns:
        List of validation error messages (empty if valid)

    Example:
        >>> @dataclass
        ... class User:
        ...     name: str
        ...     email: str
        >>> user = User("Alice", "")
        >>> validate_required_fields(user, ["name", "email"])
        ['Field "email" is required but empty']
    """
    errors = []

    for field_name in required_fields:
        if not hasattr(obj, field_name):
            errors.append(f'Required field "{field_name}" is missing')
            continue

        value = getattr(obj, field_name)

        # Check for None or empty values
        if value is None:
            errors.append(f'Field "{field_name}" is required but None')
        elif isinstance(value, str) and not value.strip():
            errors.append(f'Field "{field_name}" is required but empty')
        elif isinstance(value, (list, dict)) and not value:
            errors.append(f'Field "{field_name}" is required but empty')

    return errors


def validate_field_length(
    obj: Any, field_name: str, min_length: int = 0, max_length: Optional[int] = None
) -> List[str]:
    """
    Validate string field length.

    Args:
        obj: Dataclass instance
        field_name: Name of the field to validate
        min_length: Minimum required length
        max_length: Maximum allowed length (None for no limit)

    Returns:
        List of validation error messages (empty if valid)

    Example:
        >>> @dataclass
        ... class User:
        ...     name: str
        >>> user = User("Al")
        >>> validate_field_length(user, "name", min_length=3)
        ['Field "name" must be at least 3 characters (got 2)']
    """
    errors = []

    if not hasattr(obj, field_name):
        return errors  # Field doesn't exist, skip validation

    value = getattr(obj, field_name)

    if not isinstance(value, str):
        return errors  # Not a string, skip length validation

    length = len(value)

    if length < min_length:
        errors.append(
            f'Field "{field_name}" must be at least {min_length} characters (got {length})'
        )

    if max_length is not None and length > max_length:
        errors.append(
            f'Field "{field_name}" must be at most {max_length} characters (got {length})'
        )

    return errors


def generate_rewritten_question(
    llm_client: Any,
    last_question: str,
    new_question: str,
    **kwargs
) -> str:
    """
    Combine previous and new questions for multi-turn conversations.

    If the new question relates to the last question, combines them into a
    singular question. If the new question is self-contained, returns it as-is.

    Example:
        >>> last = "Who are the top 5 customers by sales?"
        >>> new = "Show me their email addresses"
        >>> result = generate_rewritten_question(llm_client, last, new)
        >>> # Returns: "Who are the top 5 customers by sales and what are their email addresses?"

    Args:
        llm_client: LLM client with system_message, user_message, submit_prompt methods
        last_question: Previous question from conversation
        new_question: New question to combine or use standalone
        **kwargs: Additional arguments for LLM submission

    Returns:
        Combined question if related, otherwise the new question
    """
    if last_question is None:
        return new_question

    prompt = [
        llm_client.system_message(
            "Your goal is to combine a sequence of questions into a singular question if they are related. "
            "If the second question does not relate to the first question and is fully self-contained, "
            "return the second question. Return just the new combined question with no additional explanations. "
            "The question should theoretically be answerable with a single query."
        ),
        llm_client.user_message(
            f"First question: {last_question}\nSecond question: {new_question}"
        ),
    ]

    logger.info("Generating rewritten question for conversation context")
    return llm_client.submit_prompt(prompt=prompt, **kwargs)


def generate_question_from_query(
    llm_client: Any,
    query: str,
    query_type: str = "query",
    **kwargs
) -> str:
    """
    Generate natural language question from a query (reverse generation).

    Useful for:
    - Training data generation
    - Documentation
    - Query explanation
    - Query catalog indexing

    Example:
        >>> query = "SELECT customer_name, SUM(order_total) FROM orders GROUP BY customer_name ORDER BY 2 DESC LIMIT 10"
        >>> question = generate_question_from_query(llm_client, query, query_type="SQL")
        >>> # Returns: "What are the top 10 customers by total order value?"

    Args:
        llm_client: LLM client with system_message, user_message, submit_prompt methods
        query: The query to generate a question from (SQL, DSL, etc.)
        query_type: Type of query ("SQL", "Elasticsearch", "MongoDB", etc.)
        **kwargs: Additional arguments for LLM submission

    Returns:
        Natural language question that the query answers
    """
    response = llm_client.submit_prompt(
        [
            llm_client.system_message(
                f"The user will give you a {query_type} query and you will try to guess what the business question "
                f"this query is answering. Return just the question without any additional explanation. "
                f"Do not reference technical details like table names or field names in the question - "
                f"focus on the business intent."
            ),
            llm_client.user_message(query),
        ],
        **kwargs,
    )

    logger.info(f"Generated question from {query_type} query")
    return response


def sanitize_query_for_execution(query: str, allowed_operations: Optional[List[str]] = None) -> tuple:
    """
    Basic safety check before query execution.

    This is a simple safety validator - production systems should implement
    more sophisticated query analysis and sandboxing.

    Args:
        query: Query to validate
        allowed_operations: List of allowed operations (e.g., ["SELECT"] for SQL)

    Returns:
        Tuple of (is_safe, reason)
    """
    if allowed_operations is None:
        allowed_operations = ["SELECT"]  # Default to read-only for SQL

    query_upper = query.upper().strip()

    # Check for dangerous operations
    dangerous_keywords = [
        "DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE",
        "GRANT", "REVOKE", "INSERT", "UPDATE"
    ]

    for keyword in dangerous_keywords:
        if keyword in query_upper:
            if keyword not in [op.upper() for op in allowed_operations]:
                return False, f"Disallowed operation: {keyword}"

    return True, "Query appears safe for execution"


class ConversationContext:
    """
    Simple conversation context manager for multi-turn query generation.

    Maintains conversation history and enables context-aware query generation.
    """

    def __init__(self, max_history: int = 5):
        """
        Initialize conversation context.

        Args:
            max_history: Maximum number of questions to keep in history
        """
        self.history: List[str] = []
        self.max_history = max_history
        logger.info(f"Initialized conversation context with max_history={max_history}")

    def add_question(self, question: str):
        """Add a question to conversation history"""
        self.history.append(question)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        logger.debug(f"Added question to history: {question[:50]}...")

    def get_last_question(self) -> Optional[str]:
        """Get the most recent question"""
        return self.history[-1] if self.history else None

    def get_combined_context(self, separator: str = " | ") -> str:
        """Get all questions combined as context"""
        return separator.join(self.history)

    def clear(self):
        """Clear conversation history"""
        self.history = []
        logger.info("Cleared conversation history")

    def __repr__(self) -> str:
        return f"ConversationContext(history={len(self.history)} questions)"
