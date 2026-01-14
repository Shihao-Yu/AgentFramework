"""
SQL Query Validator for LLM-generated queries.

Provides multi-layered defense against SQL injection:
1. Blocklist for dangerous keywords (DDL/DML operations)
2. Allowlist for tables (optional)
3. Read-only enforcement (SELECT only)
4. Injection pattern detection
5. Automatic LIMIT injection

Usage:
    validator = QueryValidator(allowed_tables=["orders", "customers"])
    result = validator.validate("SELECT * FROM orders WHERE id = 1")
    
    if result.is_valid:
        safe_query = result.sanitized_query
    else:
        print(f"Blocked: {result.error}")
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

# Try to import sqlparse for better parsing
try:
    import sqlparse
    from sqlparse import tokens as T
    SQLPARSE_AVAILABLE = True
except ImportError:
    SQLPARSE_AVAILABLE = False
    logger.warning("sqlparse not installed. Using regex-based validation (less accurate).")


@dataclass
class QueryValidationResult:
    """Result of query validation."""
    is_valid: bool
    error: Optional[str] = None
    sanitized_query: Optional[str] = None
    warnings: Optional[List[str]] = None


class QueryValidator:
    """
    Multi-layered SQL query validator for LLM-generated queries.
    
    Security layers:
    1. Dangerous keyword blocklist (DROP, DELETE, INSERT, etc.)
    2. Injection pattern detection (1=1, UNION, comments)
    3. Read-only enforcement (SELECT only by default)
    4. Table allowlist (optional)
    5. Automatic LIMIT injection
    
    Example:
        validator = QueryValidator(
            allowed_tables=["orders", "products"],
            max_limit=1000,
        )
        
        result = validator.validate("SELECT * FROM orders")
        if result.is_valid:
            execute(result.sanitized_query)
    """
    
    # Dangerous keywords that indicate write operations
    DANGEROUS_KEYWORDS: Set[str] = {
        # DDL
        'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'RENAME',
        # DML (write)
        'DELETE', 'INSERT', 'UPDATE', 'REPLACE', 'MERGE', 'UPSERT',
        # Execution
        'EXEC', 'EXECUTE', 'CALL',
        # Permissions
        'GRANT', 'REVOKE',
        # File operations
        'INTO OUTFILE', 'INTO DUMPFILE', 'LOAD_FILE', 'LOAD DATA',
        # PostgreSQL specific
        'COPY', 'VACUUM', 'ANALYZE', 'CLUSTER', 'REINDEX',
        # Transaction control (could be dangerous in some contexts)
        'COMMIT', 'ROLLBACK', 'SAVEPOINT',
    }
    
    # Patterns that indicate SQL injection attempts
    INJECTION_PATTERNS: List[tuple] = [
        (r"(\b1\s*=\s*1\b|\b1\s*=\s*'1'\b)", "Always-true condition"),
        (r"(\b0\s*=\s*0\b|\b''\s*=\s*''\b)", "Always-true condition"),
        (r"(\bOR\s+1\s*=\s*1\b)", "OR injection pattern"),
        (r"(\bOR\s+'[^']*'\s*=\s*'[^']*'\b)", "OR string injection"),
        (r"(--\s*$|--\s+)", "SQL comment injection"),
        (r"(/\*.*?\*/)", "Block comment"),
        (r"(;\s*DROP\b|;\s*DELETE\b|;\s*INSERT\b)", "Statement chaining"),
        (r"(\bUNION\s+(ALL\s+)?SELECT\b)", "UNION injection"),
        (r"(SLEEP\s*\(|BENCHMARK\s*\(|WAITFOR\s+DELAY)", "Time-based injection"),
        (r"(CHAR\s*\(\s*\d+\s*\)|CHR\s*\()", "Character encoding bypass"),
    ]
    
    def __init__(
        self,
        allowed_tables: Optional[List[str]] = None,
        allowed_schemas: Optional[List[str]] = None,
        max_limit: int = 1000,
        require_limit: bool = True,
        allow_joins: bool = True,
        max_subqueries: int = 3,
        block_union: bool = True,
        additional_blocked_keywords: Optional[List[str]] = None,
    ):
        """
        Initialize query validator.
        
        Args:
            allowed_tables: Allowlist of table names (None = allow all)
            allowed_schemas: Allowlist of schema names (None = allow all)
            max_limit: Maximum LIMIT value (default 1000)
            require_limit: Whether to require/inject LIMIT clause
            allow_joins: Whether JOIN operations are allowed
            max_subqueries: Maximum number of subqueries allowed
            block_union: Whether to block UNION queries
            additional_blocked_keywords: Extra keywords to block
        """
        self.allowed_tables = set(t.lower() for t in allowed_tables) if allowed_tables else None
        self.allowed_schemas = set(s.lower() for s in allowed_schemas) if allowed_schemas else None
        self.max_limit = max_limit
        self.require_limit = require_limit
        self.allow_joins = allow_joins
        self.max_subqueries = max_subqueries
        self.block_union = block_union
        
        # Build complete blocked keywords set
        self.blocked_keywords = self.DANGEROUS_KEYWORDS.copy()
        if additional_blocked_keywords:
            self.blocked_keywords.update(k.upper() for k in additional_blocked_keywords)
        if block_union:
            self.blocked_keywords.add('UNION')
    
    def validate(self, query: str) -> QueryValidationResult:
        """
        Validate a SQL query for security.
        
        Args:
            query: SQL query string to validate
            
        Returns:
            QueryValidationResult with validation status and sanitized query
        """
        if not query or not query.strip():
            return QueryValidationResult(
                is_valid=False,
                error="Empty query",
            )
        
        query = query.strip()
        warnings: List[str] = []
        
        # Layer 1: Check for multiple statements
        if self._has_multiple_statements(query):
            self._log_blocked(query, "Multiple statements detected")
            return QueryValidationResult(
                is_valid=False,
                error="Multiple statements not allowed",
            )
        
        # Layer 2: Check dangerous keywords
        blocked = self._check_blocked_keywords(query)
        if blocked:
            self._log_blocked(query, f"Dangerous keyword: {blocked}")
            return QueryValidationResult(
                is_valid=False,
                error=f"Dangerous keyword '{blocked}' not allowed",
            )
        
        # Layer 3: Check injection patterns
        injection = self._check_injection_patterns(query)
        if injection:
            self._log_blocked(query, f"Injection pattern: {injection}")
            return QueryValidationResult(
                is_valid=False,
                error=f"Suspicious pattern detected: {injection}",
            )
        
        # Layer 4: Verify SELECT only
        if not self._is_select_query(query):
            self._log_blocked(query, "Not a SELECT query")
            return QueryValidationResult(
                is_valid=False,
                error="Only SELECT queries allowed",
            )
        
        # Layer 5: Check table allowlist
        if self.allowed_tables:
            table_error = self._check_table_allowlist(query)
            if table_error:
                self._log_blocked(query, f"Table not allowed: {table_error}")
                return QueryValidationResult(
                    is_valid=False,
                    error=table_error,
                )
        
        # Layer 6: Check JOIN if restricted
        if not self.allow_joins and self._has_join(query):
            return QueryValidationResult(
                is_valid=False,
                error="JOIN operations not allowed",
            )
        
        # Layer 7: Check subquery count
        subquery_count = self._count_subqueries(query)
        if subquery_count > self.max_subqueries:
            return QueryValidationResult(
                is_valid=False,
                error=f"Too many subqueries ({subquery_count} > {self.max_subqueries})",
            )
        
        # Sanitization: Add or adjust LIMIT
        sanitized = self._sanitize_limit(query)
        if sanitized != query:
            warnings.append(f"Added LIMIT {self.max_limit}")
        
        return QueryValidationResult(
            is_valid=True,
            sanitized_query=sanitized,
            warnings=warnings if warnings else None,
        )
    
    def _has_multiple_statements(self, query: str) -> bool:
        """Check if query contains multiple statements."""
        if SQLPARSE_AVAILABLE:
            parsed = sqlparse.parse(query)
            # Filter out empty statements
            statements = [s for s in parsed if s.get_type() is not None or str(s).strip()]
            return len(statements) > 1
        
        # Regex fallback: count semicolons not in strings
        # Simple heuristic - won't catch all cases
        clean = re.sub(r"'[^']*'", "", query)  # Remove string literals
        return clean.count(';') > 1 or (clean.count(';') == 1 and not clean.rstrip().endswith(';'))
    
    def _check_blocked_keywords(self, query: str) -> Optional[str]:
        """Check for blocked keywords. Returns the blocked keyword if found."""
        query_upper = query.upper()
        
        for keyword in self.blocked_keywords:
            # Use word boundary for single words
            if ' ' in keyword:
                # Multi-word phrase
                if keyword in query_upper:
                    return keyword
            else:
                # Single word - use word boundary
                pattern = rf'\b{re.escape(keyword)}\b'
                if re.search(pattern, query_upper):
                    return keyword
        
        return None
    
    def _check_injection_patterns(self, query: str) -> Optional[str]:
        """Check for SQL injection patterns."""
        for pattern, description in self.INJECTION_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return description
        return None
    
    def _is_select_query(self, query: str) -> bool:
        """Verify query is a SELECT statement."""
        if SQLPARSE_AVAILABLE:
            parsed = sqlparse.parse(query)
            if not parsed:
                return False
            stmt = parsed[0]
            return stmt.get_type() == 'SELECT'
        
        # Regex fallback
        clean = query.strip().upper()
        # Handle WITH (CTE) before SELECT
        if clean.startswith('WITH'):
            # Find the main query after CTEs
            # Simple check: should have SELECT somewhere
            return 'SELECT' in clean and not any(
                kw in clean for kw in ['INSERT', 'UPDATE', 'DELETE', 'DROP']
            )
        return clean.startswith('SELECT')
    
    def _check_table_allowlist(self, query: str) -> Optional[str]:
        """Check if all tables are in allowlist. Returns error message if not."""
        tables = self._extract_tables(query)
        
        for table in tables:
            table_lower = table.lower()
            # Handle schema.table format
            if '.' in table_lower:
                schema, table_name = table_lower.rsplit('.', 1)
                if self.allowed_schemas and schema not in self.allowed_schemas:
                    return f"Schema '{schema}' not allowed"
                if table_name not in self.allowed_tables:
                    return f"Table '{table_name}' not allowed"
            else:
                if table_lower not in self.allowed_tables:
                    return f"Table '{table}' not allowed"
        
        return None
    
    def _extract_tables(self, query: str) -> List[str]:
        """Extract table names from query."""
        if SQLPARSE_AVAILABLE:
            return self._extract_tables_sqlparse(query)
        return self._extract_tables_regex(query)
    
    def _extract_tables_sqlparse(self, query: str) -> List[str]:
        """Extract tables using sqlparse."""
        tables = []
        parsed = sqlparse.parse(query)
        if not parsed:
            return tables
        
        stmt = parsed[0]
        from_seen = False
        
        for token in stmt.tokens:
            if from_seen:
                if token.ttype is T.Keyword:
                    # End of FROM clause
                    if token.value.upper() in ('WHERE', 'GROUP', 'ORDER', 'LIMIT', 'HAVING'):
                        from_seen = False
                elif isinstance(token, sqlparse.sql.Identifier):
                    tables.append(token.get_real_name())
                elif isinstance(token, sqlparse.sql.IdentifierList):
                    for identifier in token.get_identifiers():
                        if isinstance(identifier, sqlparse.sql.Identifier):
                            tables.append(identifier.get_real_name())
            
            if token.ttype is T.Keyword and token.value.upper() in ('FROM', 'JOIN', 'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'FULL JOIN', 'CROSS JOIN'):
                from_seen = True
        
        return tables
    
    def _extract_tables_regex(self, query: str) -> List[str]:
        """Extract tables using regex (fallback)."""
        tables = []
        
        # Match FROM table and JOIN table
        patterns = [
            r'\bFROM\s+(\w+(?:\.\w+)?)',
            r'\bJOIN\s+(\w+(?:\.\w+)?)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            tables.extend(matches)
        
        return tables
    
    def _has_join(self, query: str) -> bool:
        """Check if query has JOIN operations."""
        return bool(re.search(r'\bJOIN\b', query, re.IGNORECASE))
    
    def _count_subqueries(self, query: str) -> int:
        """Count number of subqueries."""
        # Simple heuristic: count SELECT keywords minus 1
        count = len(re.findall(r'\bSELECT\b', query, re.IGNORECASE))
        return max(0, count - 1)
    
    def _sanitize_limit(self, query: str) -> str:
        """Add or adjust LIMIT clause."""
        if not self.require_limit:
            return query
        
        query_upper = query.upper()
        
        # Check if LIMIT exists
        limit_match = re.search(r'\bLIMIT\s+(\d+)', query, re.IGNORECASE)
        
        if limit_match:
            current_limit = int(limit_match.group(1))
            if current_limit > self.max_limit:
                # Replace with max_limit
                return re.sub(
                    r'\bLIMIT\s+\d+',
                    f'LIMIT {self.max_limit}',
                    query,
                    flags=re.IGNORECASE,
                )
            return query
        
        # No LIMIT - add it
        # Remove trailing semicolon if present
        query = query.rstrip(';').rstrip()
        return f"{query} LIMIT {self.max_limit}"
    
    def _log_blocked(self, query: str, reason: str) -> None:
        """Log blocked query for audit."""
        # Truncate query for logging
        truncated = query[:200] + '...' if len(query) > 200 else query
        logger.warning(f"Query blocked: {reason} | Query: {truncated}")


# Convenience function for simple validation
def validate_query(
    query: str,
    allowed_tables: Optional[List[str]] = None,
    max_limit: int = 1000,
) -> QueryValidationResult:
    """
    Convenience function for simple query validation.
    
    Args:
        query: SQL query to validate
        allowed_tables: Optional list of allowed tables
        max_limit: Maximum LIMIT value
        
    Returns:
        QueryValidationResult
    """
    validator = QueryValidator(
        allowed_tables=allowed_tables,
        max_limit=max_limit,
    )
    return validator.validate(query)
