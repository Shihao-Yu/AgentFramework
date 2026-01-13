"""
Extraction strategies for different query types.

Provides pluggable extraction, validation, and formatting strategies
for SQL, OpenSearch DSL, MongoDB queries, and REST API requests.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional

from ..core.models import QueryType

logger = logging.getLogger(__name__)

# Import sqlparse for SQL validation (optional dependency)
try:
    import sqlparse

    SQLPARSE_AVAILABLE = True
except ImportError:
    SQLPARSE_AVAILABLE = False
    logger.warning("sqlparse not available - SQL validation disabled")


class ExtractionStrategy(ABC):
    """Base strategy for query extraction and validation."""

    def __init__(self, query_type: QueryType):
        self.query_type = query_type

    @abstractmethod
    def extract_query(self, llm_response: str) -> str:
        """Extract query from LLM response."""
        pass

    @abstractmethod
    def is_valid(self, query: str) -> bool:
        """Validate extracted query."""
        pass

    @abstractmethod
    def format_query(self, query: str) -> str:
        """Format query according to dialect conventions."""
        pass

    def is_intermediate(self, llm_response: str) -> bool:
        """Check if response contains intermediate query marker."""
        return "intermediate_sql" in llm_response.lower()


class SqlExtractionStrategy(ExtractionStrategy):
    """
    Production-grade SQL extraction strategy.

    Handles:
    - CREATE TABLE AS SELECT statements
    - WITH clauses (CTEs)
    - SELECT statements
    - Markdown code blocks
    """

    def __init__(self, query_type: QueryType = QueryType.POSTGRES):
        super().__init__(query_type)
        self.dialect = query_type.value

    def extract_query(self, llm_response: str) -> str:
        """
        Extract SQL query from LLM response with comprehensive pattern matching.

        Handles various formats:
        - CREATE TABLE AS SELECT
        - WITH clause (CTEs)
        - SELECT statements
        - Markdown code blocks (```sql or ```)
        """
        # Match CREATE TABLE ... AS SELECT
        sqls = re.findall(
            r"\bCREATE\s+TABLE\b.*?\bAS\b.*?;",
            llm_response,
            re.DOTALL | re.IGNORECASE,
        )
        if sqls:
            sql = sqls[-1]
            logger.debug(f"Extracted CREATE TABLE AS: {sql[:100]}...")
            return sql.strip()

        # Match WITH clause (CTEs)
        sqls = re.findall(
            r"\bWITH\b .*?;",
            llm_response,
            re.DOTALL | re.IGNORECASE,
        )
        if sqls:
            sql = sqls[-1]
            logger.debug(f"Extracted WITH clause: {sql[:100]}...")
            return sql.strip()

        # Match SELECT ... ;
        sqls = re.findall(
            r"\bSELECT\b .*?;",
            llm_response,
            re.DOTALL | re.IGNORECASE,
        )
        if sqls:
            sql = sqls[-1]
            logger.debug(f"Extracted SELECT: {sql[:100]}...")
            return sql.strip()

        # Match ```sql ... ``` blocks
        sqls = re.findall(
            r"```sql\s*\n(.*?)```",
            llm_response,
            re.DOTALL | re.IGNORECASE,
        )
        if sqls:
            sql = sqls[-1].strip()
            logger.debug(f"Extracted from sql block: {sql[:100]}...")
            return sql

        # Match any ``` ... ``` code blocks
        sqls = re.findall(
            r"```(.*?)```",
            llm_response,
            re.DOTALL | re.IGNORECASE,
        )
        if sqls:
            sql = sqls[-1].strip()
            logger.debug(f"Extracted from code block: {sql[:100]}...")
            return sql

        # Fallback: return entire response
        logger.warning("No SQL pattern matched, returning full response")
        return llm_response.strip()

    def is_valid(self, query: str) -> bool:
        """
        Validate SQL query using sqlparse.

        By default, only SELECT statements are considered valid for safety.
        Override this method to allow other statement types.
        """
        if not SQLPARSE_AVAILABLE:
            logger.warning("sqlparse not available, skipping validation")
            return True  # Assume valid if we can't validate

        try:
            parsed = sqlparse.parse(query)

            for statement in parsed:
                if statement.get_type() == "SELECT":
                    return True

            logger.warning("Query validation failed: not a SELECT statement")
            return False

        except Exception as e:
            logger.error(f"SQL validation error: {e}")
            return False

    def format_query(self, query: str) -> str:
        """
        Format SQL query according to dialect conventions.

        - Removes markdown code blocks
        - Ensures semicolon termination
        - Applies dialect-specific formatting
        """
        query = query.strip()

        # Remove markdown code blocks
        if query.startswith("```"):
            lines = query.split("\n")
            # Remove first line (```sql or similar)
            lines = lines[1:]
            # Remove last line (```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            query = "\n".join(lines)

        # Ensure query ends with semicolon
        if not query.rstrip().endswith(";"):
            query = query.rstrip() + ";"

        logger.debug(f"Formatted SQL query: {query[:100]}...")
        return query


class OpenSearchExtractionStrategy(ExtractionStrategy):
    """OpenSearch/Elasticsearch DSL extraction strategy."""

    def __init__(self):
        super().__init__(QueryType.OPENSEARCH)

    def extract_query(self, llm_response: str) -> str:
        """Extract OpenSearch DSL JSON from LLM response."""
        # Try to find JSON in code blocks first
        json_block_pattern = r"```json\s*\n?([\s\S]*?)\n?```"
        match = re.search(json_block_pattern, llm_response, re.IGNORECASE)

        if match:
            return match.group(1).strip()

        # Try to find raw JSON object
        json_pattern = r"\{[\s\S]*\}"
        matches = re.findall(json_pattern, llm_response)

        for match_str in matches:
            try:
                json.loads(match_str)
                return match_str.strip()
            except json.JSONDecodeError:
                continue

        logger.warning("No OpenSearch DSL pattern matched, returning full response")
        return llm_response.strip()

    def is_valid(self, query: str) -> bool:
        """Validate OpenSearch DSL is valid JSON with expected structure."""
        try:
            parsed = json.loads(query)
            # Basic structure validation - should have 'query' or 'aggs'
            if "query" in parsed or "aggs" in parsed or "aggregations" in parsed:
                return True
            logger.warning("OpenSearch DSL missing 'query' or 'aggs' key")
            return False
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in OpenSearch DSL: {e}")
            return False

    def format_query(self, query: str) -> str:
        """Format OpenSearch DSL as pretty-printed JSON."""
        try:
            parsed = json.loads(query)
            return json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            return query.strip()


class MongoDBExtractionStrategy(ExtractionStrategy):
    """MongoDB query extraction strategy."""

    def __init__(self):
        super().__init__(QueryType.MONGODB)

    def extract_query(self, llm_response: str) -> str:
        """Extract MongoDB query from LLM response."""
        # Try to find JSON in code blocks
        json_block_pattern = r"```(?:json|javascript)?\s*\n?([\s\S]*?)\n?```"
        match = re.search(json_block_pattern, llm_response, re.IGNORECASE)

        if match:
            return match.group(1).strip()

        logger.warning("MongoDB extraction using fallback")
        return llm_response.strip()

    def is_valid(self, query: str) -> bool:
        """Validate MongoDB query."""
        try:
            json.loads(query)
            return True
        except json.JSONDecodeError:
            logger.warning("MongoDB query is not valid JSON")
            return False

    def format_query(self, query: str) -> str:
        """Format MongoDB query."""
        try:
            parsed = json.loads(query)
            return json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            return query.strip()


class RestAPIExtractionStrategy(ExtractionStrategy):
    """
    REST API query extraction strategy.

    Extracts and validates REST API calls including:
    - HTTP method (GET, POST, PUT, DELETE, PATCH)
    - Endpoint path with path parameters
    - Query parameters
    - Request headers
    - Request body (JSON)
    """

    def __init__(self):
        super().__init__(QueryType.REST_API)

    def extract_query(self, llm_response: str) -> str:
        """
        Extract REST API call from LLM response.

        Expected formats:
        - GET /api/users?status=active
        - POST /api/orders
          Body: {"customer_id": 123, "items": [...]}
        - JSON request object in code blocks
        """
        # Try to find JSON in code blocks first (structured request format)
        json_block_pattern = r"```json\s*\n?([\s\S]*?)\n?```"
        match = re.search(json_block_pattern, llm_response, re.IGNORECASE)

        if match:
            try:
                parsed = json.loads(match.group(1).strip())
                # Validate it looks like an API request
                if "method" in parsed or "path" in parsed:
                    return json.dumps(parsed, indent=2)
            except json.JSONDecodeError:
                pass

        # Match HTTP method + endpoint pattern
        # Pattern: METHOD /path/to/endpoint?query=params
        api_calls = re.findall(
            r"\b(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s\n]+)",
            llm_response,
            re.IGNORECASE,
        )

        if api_calls:
            method, endpoint = api_calls[-1]
            method = method.upper()

            # Try to extract request body if POST/PUT/PATCH
            body = None
            if method in ["POST", "PUT", "PATCH"]:
                # Look for JSON body after "Body:" or in code blocks
                body_match = re.search(
                    r"(?:Body|body|BODY|Request|request):\s*(\{.*?\})",
                    llm_response,
                    re.DOTALL,
                )
                if not body_match:
                    # Try to find JSON in code blocks
                    body_match = re.search(
                        r"```(?:json)?\s*(\{.*?\})\s*```",
                        llm_response,
                        re.DOTALL,
                    )

                if body_match:
                    body = body_match.group(1).strip()

            # Format as structured JSON request
            request = {"method": method, "path": endpoint}
            if body:
                try:
                    request["body"] = json.loads(body)
                except json.JSONDecodeError:
                    request["body"] = body

            logger.debug(f"Extracted REST API call: {method} {endpoint}")
            return json.dumps(request, indent=2)

        # Match markdown code blocks with HTTP-like content
        code_blocks = re.findall(
            r"```(?:http|rest|api)?\s*\n(.*?)```",
            llm_response,
            re.DOTALL | re.IGNORECASE,
        )
        if code_blocks:
            content = code_blocks[-1].strip()
            logger.debug(f"Extracted from code block: {content[:100]}...")
            return content

        # Fallback: return entire response
        logger.warning("No REST API pattern matched, returning full response")
        return llm_response.strip()

    def is_valid(self, query: str) -> bool:
        """
        Validate REST API call.

        Checks:
        - Contains valid HTTP method
        - Has valid endpoint path structure
        - JSON body is valid (if present)
        """
        # Try to parse as JSON first (structured format)
        try:
            request = json.loads(query)
            if "method" in request and "path" in request:
                method = request["method"].upper()
                path = request["path"]
                if method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    if path.startswith("/"):
                        return True
        except json.JSONDecodeError:
            pass

        # Fall back to text-based validation
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        has_method = any(method in query.upper() for method in methods)

        if not has_method:
            logger.warning("No HTTP method found in REST API call")
            return False

        # Check for endpoint path (starts with /)
        has_path = re.search(r"/[a-zA-Z0-9/_\-{}:]+", query)
        if not has_path:
            logger.warning("No valid endpoint path found")
            return False

        return True

    def format_query(self, query: str) -> str:
        """
        Format REST API call consistently.

        Output format (JSON):
        {
            "method": "GET|POST|PUT|DELETE",
            "path": "/endpoint/path",
            "params": {...},
            "body": {...}
        }
        """
        # Try to parse and reformat as JSON
        try:
            request = json.loads(query)
            # Normalize method to uppercase
            if "method" in request:
                request["method"] = request["method"].upper()
            # Remove null/empty values
            cleaned = {}
            for key, value in request.items():
                if value is not None and value != {} and value != []:
                    cleaned[key] = value
            return json.dumps(cleaned, indent=2)
        except json.JSONDecodeError:
            pass

        # Normalize HTTP method to uppercase for text format
        query = query.strip()
        for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            pattern = re.compile(r"\b" + method + r"\b", re.IGNORECASE)
            query = pattern.sub(method, query)

        logger.debug(f"Formatted REST API call: {query[:100]}...")
        return query


def get_strategy(query_type: QueryType) -> ExtractionStrategy:
    """
    Factory function to get appropriate extraction strategy.

    Args:
        query_type: Query type enum

    Returns:
        Appropriate extraction strategy instance
    """
    # SQL dialects all use SqlExtractionStrategy
    if query_type in [
        QueryType.SQL_SERVER,
        QueryType.MYSQL,
        QueryType.POSTGRES,
        QueryType.ORACLE,
        QueryType.SQLITE,
        QueryType.CLICKHOUSE,
    ]:
        return SqlExtractionStrategy(query_type)

    # REST API
    elif query_type == QueryType.REST_API:
        return RestAPIExtractionStrategy()

    # Search engines
    elif query_type in [QueryType.OPENSEARCH, QueryType.ELASTICSEARCH]:
        return OpenSearchExtractionStrategy()

    # NoSQL
    elif query_type == QueryType.MONGODB:
        return MongoDBExtractionStrategy()

    # Default to SQL strategy as fallback
    else:
        logger.warning(f"No strategy for {query_type}, using SQL strategy as fallback")
        return SqlExtractionStrategy(query_type)
