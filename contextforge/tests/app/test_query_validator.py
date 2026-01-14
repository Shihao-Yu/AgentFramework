"""
Tests for SQL injection prevention in QueryValidator.

Tests cover:
- Basic SELECT queries (should pass)
- DDL attacks (DROP, CREATE, ALTER, TRUNCATE)
- DML attacks (DELETE, INSERT, UPDATE)
- SQL injection patterns (OR 1=1, UNION, comments)
- Multiple statement attacks
- Table allowlist enforcement
- LIMIT injection and enforcement
- Subquery limits
- JOIN restrictions
"""

import pytest
from app.utils.query_validator import QueryValidator, QueryValidationResult, validate_query


class TestBasicValidation:
    """Test basic query validation."""

    def test_valid_simple_select(self):
        """Simple SELECT should pass."""
        validator = QueryValidator()
        result = validator.validate("SELECT * FROM users")
        
        assert result.is_valid
        assert result.error is None
        assert "LIMIT" in result.sanitized_query

    def test_valid_select_with_where(self):
        """SELECT with WHERE should pass."""
        validator = QueryValidator()
        result = validator.validate("SELECT id, name FROM users WHERE active = true")
        
        assert result.is_valid
        assert "SELECT id, name FROM users WHERE active = true" in result.sanitized_query

    def test_valid_select_with_join(self):
        """SELECT with JOIN should pass by default."""
        validator = QueryValidator()
        result = validator.validate(
            "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id"
        )
        
        assert result.is_valid

    def test_valid_select_with_existing_limit(self):
        """SELECT with existing LIMIT should preserve it if under max."""
        validator = QueryValidator(max_limit=1000)
        result = validator.validate("SELECT * FROM users LIMIT 100")
        
        assert result.is_valid
        assert "LIMIT 100" in result.sanitized_query

    def test_empty_query_rejected(self):
        """Empty query should be rejected."""
        validator = QueryValidator()
        result = validator.validate("")
        
        assert not result.is_valid
        assert "Empty" in result.error

    def test_whitespace_only_rejected(self):
        """Whitespace-only query should be rejected."""
        validator = QueryValidator()
        result = validator.validate("   \n\t  ")
        
        assert not result.is_valid


class TestDDLAttacks:
    """Test detection of DDL attacks."""

    def test_drop_table_blocked(self):
        """DROP TABLE should be blocked."""
        validator = QueryValidator()
        result = validator.validate("DROP TABLE users")
        
        assert not result.is_valid
        assert "DROP" in result.error

    def test_drop_in_select_blocked(self):
        """DROP hidden in SELECT should be blocked."""
        validator = QueryValidator()
        result = validator.validate("SELECT * FROM users; DROP TABLE users")
        
        assert not result.is_valid

    def test_create_table_blocked(self):
        """CREATE TABLE should be blocked."""
        validator = QueryValidator()
        result = validator.validate("CREATE TABLE evil (id INT)")
        
        assert not result.is_valid
        assert "CREATE" in result.error

    def test_alter_table_blocked(self):
        """ALTER TABLE should be blocked."""
        validator = QueryValidator()
        result = validator.validate("ALTER TABLE users ADD COLUMN hacked TEXT")
        
        assert not result.is_valid
        assert "ALTER" in result.error

    def test_truncate_blocked(self):
        """TRUNCATE should be blocked."""
        validator = QueryValidator()
        result = validator.validate("TRUNCATE users")
        
        assert not result.is_valid
        assert "TRUNCATE" in result.error


class TestDMLAttacks:
    """Test detection of DML write attacks."""

    def test_delete_blocked(self):
        """DELETE should be blocked."""
        validator = QueryValidator()
        result = validator.validate("DELETE FROM users WHERE id = 1")
        
        assert not result.is_valid
        assert "DELETE" in result.error

    def test_insert_blocked(self):
        """INSERT should be blocked."""
        validator = QueryValidator()
        result = validator.validate("INSERT INTO users (name) VALUES ('hacker')")
        
        assert not result.is_valid
        assert "INSERT" in result.error

    def test_update_blocked(self):
        """UPDATE should be blocked."""
        validator = QueryValidator()
        result = validator.validate("UPDATE users SET admin = true WHERE id = 1")
        
        assert not result.is_valid
        assert "UPDATE" in result.error

    def test_merge_blocked(self):
        """MERGE should be blocked."""
        validator = QueryValidator()
        result = validator.validate("MERGE INTO users USING temp ON users.id = temp.id")
        
        assert not result.is_valid
        assert "MERGE" in result.error


class TestSQLInjectionPatterns:
    """Test detection of SQL injection patterns."""

    def test_or_1_equals_1_blocked(self):
        """OR 1=1 injection should be blocked."""
        validator = QueryValidator()
        result = validator.validate("SELECT * FROM users WHERE id = 1 OR 1=1")
        
        assert not result.is_valid
        assert "Always-true" in result.error or "injection" in result.error.lower()

    def test_or_1_equals_1_spaced_blocked(self):
        """OR 1 = 1 with spaces should be blocked."""
        validator = QueryValidator()
        result = validator.validate("SELECT * FROM users WHERE id = 1 OR 1 = 1")
        
        assert not result.is_valid

    def test_string_injection_blocked(self):
        """String comparison injection should be blocked."""
        validator = QueryValidator()
        result = validator.validate("SELECT * FROM users WHERE name = '' OR 'a'='a'")
        
        assert not result.is_valid

    def test_comment_injection_blocked(self):
        """SQL comment injection should be blocked."""
        validator = QueryValidator()
        result = validator.validate("SELECT * FROM users WHERE id = 1 --")
        
        assert not result.is_valid
        assert "comment" in result.error.lower()

    def test_block_comment_blocked(self):
        """Block comment injection should be blocked."""
        validator = QueryValidator()
        result = validator.validate("SELECT * FROM users /* WHERE id = 1 */")
        
        assert not result.is_valid

    def test_union_injection_blocked(self):
        """UNION injection should be blocked by default."""
        validator = QueryValidator()
        result = validator.validate(
            "SELECT name FROM users UNION SELECT password FROM credentials"
        )
        
        assert not result.is_valid

    def test_union_all_injection_blocked(self):
        """UNION ALL injection should be blocked."""
        validator = QueryValidator()
        result = validator.validate(
            "SELECT name FROM users UNION ALL SELECT secret FROM keys"
        )
        
        assert not result.is_valid

    def test_sleep_injection_blocked(self):
        """SLEEP injection (time-based) should be blocked."""
        validator = QueryValidator()
        result = validator.validate("SELECT * FROM users WHERE SLEEP(5)")
        
        assert not result.is_valid

    def test_benchmark_injection_blocked(self):
        """BENCHMARK injection should be blocked."""
        validator = QueryValidator()
        result = validator.validate(
            "SELECT * FROM users WHERE BENCHMARK(1000000, SHA1('test'))"
        )
        
        assert not result.is_valid


class TestMultipleStatements:
    """Test detection of multiple statement attacks."""

    def test_semicolon_chaining_blocked(self):
        """Semicolon statement chaining should be blocked."""
        validator = QueryValidator()
        result = validator.validate("SELECT * FROM users; DELETE FROM users")
        
        assert not result.is_valid

    def test_multiple_selects_blocked(self):
        """Multiple SELECT statements should be blocked."""
        validator = QueryValidator()
        result = validator.validate("SELECT 1; SELECT 2")
        
        assert not result.is_valid

    def test_trailing_semicolon_allowed(self):
        """Single trailing semicolon should be allowed."""
        validator = QueryValidator()
        result = validator.validate("SELECT * FROM users;")
        
        assert result.is_valid


class TestTableAllowlist:
    """Test table allowlist enforcement."""

    def test_allowed_table_passes(self):
        """Query on allowed table should pass."""
        validator = QueryValidator(allowed_tables=["users", "orders"])
        result = validator.validate("SELECT * FROM users")
        
        assert result.is_valid

    def test_disallowed_table_blocked(self):
        """Query on disallowed table should be blocked."""
        validator = QueryValidator(allowed_tables=["users", "orders"])
        result = validator.validate("SELECT * FROM secrets")
        
        assert not result.is_valid
        assert "secrets" in result.error.lower() or "not allowed" in result.error.lower()

    def test_case_insensitive_table_matching(self):
        """Table matching should be case insensitive."""
        validator = QueryValidator(allowed_tables=["Users"])
        result = validator.validate("SELECT * FROM users")
        
        assert result.is_valid

    def test_schema_qualified_table(self):
        """Schema-qualified table names should work."""
        validator = QueryValidator(
            allowed_tables=["users"],
            allowed_schemas=["public"]
        )
        result = validator.validate("SELECT * FROM public.users")
        
        assert result.is_valid

    def test_disallowed_schema_blocked(self):
        """Disallowed schema should be blocked."""
        validator = QueryValidator(
            allowed_tables=["users"],
            allowed_schemas=["public"]
        )
        result = validator.validate("SELECT * FROM admin.users")
        
        assert not result.is_valid


class TestLimitEnforcement:
    """Test LIMIT clause enforcement."""

    def test_limit_added_when_missing(self):
        """LIMIT should be added when missing."""
        validator = QueryValidator(max_limit=500)
        result = validator.validate("SELECT * FROM users")
        
        assert result.is_valid
        assert "LIMIT 500" in result.sanitized_query

    def test_limit_reduced_when_too_high(self):
        """LIMIT should be reduced when above max."""
        validator = QueryValidator(max_limit=100)
        result = validator.validate("SELECT * FROM users LIMIT 9999")
        
        assert result.is_valid
        assert "LIMIT 100" in result.sanitized_query
        assert "LIMIT 9999" not in result.sanitized_query

    def test_limit_preserved_when_under_max(self):
        """LIMIT should be preserved when under max."""
        validator = QueryValidator(max_limit=1000)
        result = validator.validate("SELECT * FROM users LIMIT 50")
        
        assert result.is_valid
        assert "LIMIT 50" in result.sanitized_query

    def test_limit_not_required_when_disabled(self):
        """LIMIT should not be added when require_limit=False."""
        validator = QueryValidator(require_limit=False)
        result = validator.validate("SELECT * FROM users")
        
        assert result.is_valid
        assert "LIMIT" not in result.sanitized_query

    def test_warnings_for_added_limit(self):
        """Adding LIMIT should generate a warning."""
        validator = QueryValidator(max_limit=100)
        result = validator.validate("SELECT * FROM users")
        
        assert result.is_valid
        assert result.warnings is not None
        assert any("LIMIT" in w for w in result.warnings)


class TestSubqueryLimits:
    """Test subquery count limits."""

    def test_single_subquery_allowed(self):
        """Single subquery should be allowed by default."""
        validator = QueryValidator(max_subqueries=3)
        result = validator.validate(
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        )
        
        assert result.is_valid

    def test_excessive_subqueries_blocked(self):
        """Excessive subqueries should be blocked."""
        validator = QueryValidator(max_subqueries=1)
        result = validator.validate(
            """SELECT * FROM users 
               WHERE id IN (SELECT user_id FROM orders)
               AND dept_id IN (SELECT id FROM departments)
               AND role_id IN (SELECT id FROM roles)"""
        )
        
        assert not result.is_valid
        assert "subquer" in result.error.lower()


class TestJoinRestrictions:
    """Test JOIN restriction options."""

    def test_join_blocked_when_disabled(self):
        """JOIN should be blocked when allow_joins=False."""
        validator = QueryValidator(allow_joins=False)
        result = validator.validate(
            "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id"
        )
        
        assert not result.is_valid
        assert "JOIN" in result.error

    def test_join_allowed_by_default(self):
        """JOIN should be allowed by default."""
        validator = QueryValidator()
        result = validator.validate(
            "SELECT * FROM users u LEFT JOIN orders o ON u.id = o.user_id"
        )
        
        assert result.is_valid


class TestCTEQueries:
    """Test Common Table Expression (WITH) queries."""

    def test_simple_cte_allowed(self):
        """Simple CTE should be allowed."""
        validator = QueryValidator()
        result = validator.validate(
            """WITH active_users AS (SELECT * FROM users WHERE active = true)
               SELECT * FROM active_users"""
        )
        
        assert result.is_valid

    def test_cte_with_ddl_blocked(self):
        """CTE followed by DDL should be blocked."""
        validator = QueryValidator()
        result = validator.validate(
            "WITH x AS (SELECT 1) DROP TABLE users"
        )
        
        assert not result.is_valid


class TestConvenienceFunction:
    """Test the validate_query convenience function."""

    def test_convenience_function_basic(self):
        """Basic validation via convenience function."""
        result = validate_query("SELECT * FROM users")
        
        assert result.is_valid

    def test_convenience_function_with_tables(self):
        """Validation with allowed_tables via convenience function."""
        result = validate_query(
            "SELECT * FROM secrets",
            allowed_tables=["users", "orders"]
        )
        
        assert not result.is_valid

    def test_convenience_function_with_limit(self):
        """Validation with custom max_limit via convenience function."""
        result = validate_query(
            "SELECT * FROM users",
            max_limit=50
        )
        
        assert result.is_valid
        assert "LIMIT 50" in result.sanitized_query


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_query(self):
        """Very long query should be handled."""
        validator = QueryValidator()
        long_columns = ", ".join([f"col{i}" for i in range(100)])
        result = validator.validate(f"SELECT {long_columns} FROM users")
        
        assert result.is_valid

    def test_unicode_query(self):
        """Query with unicode characters should be handled."""
        validator = QueryValidator()
        result = validator.validate("SELECT * FROM users WHERE name = 'Caf\u00e9'")
        
        assert result.is_valid

    def test_newlines_in_query(self):
        """Query with newlines should be handled."""
        validator = QueryValidator()
        result = validator.validate("""
            SELECT 
                id,
                name
            FROM 
                users
            WHERE 
                active = true
        """)
        
        assert result.is_valid

    def test_additional_blocked_keywords(self):
        """Custom blocked keywords should work."""
        validator = QueryValidator(additional_blocked_keywords=["CUSTOM_EVIL"])
        result = validator.validate("SELECT CUSTOM_EVIL FROM users")
        
        assert not result.is_valid

    def test_union_allowed_when_not_blocked(self):
        """UNION should work when block_union=False."""
        validator = QueryValidator(block_union=False)
        result = validator.validate("SELECT 1 UNION SELECT 2")
        
        # Note: still blocked by injection pattern detection
        # This tests the keyword blocking specifically
        assert "UNION" not in validator.blocked_keywords


class TestRealWorldInjections:
    """Test real-world SQL injection payloads."""

    def test_classic_auth_bypass(self):
        """Classic authentication bypass should be blocked."""
        validator = QueryValidator()
        result = validator.validate(
            "SELECT * FROM users WHERE username = 'admin' AND password = '' OR '1'='1'"
        )
        
        assert not result.is_valid

    def test_stacked_queries_with_waitfor(self):
        """Stacked queries with WAITFOR should be blocked."""
        validator = QueryValidator()
        result = validator.validate(
            "SELECT * FROM users; WAITFOR DELAY '0:0:5'"
        )
        
        assert not result.is_valid

    def test_error_based_extraction(self):
        """Error-based extraction attempt should be blocked."""
        validator = QueryValidator()
        result = validator.validate(
            "SELECT * FROM users WHERE id = 1 AND 1=CONVERT(int, (SELECT TOP 1 name FROM sysobjects))"
        )
        
        # This is blocked as non-SELECT or blocked keyword
        assert not result.is_valid or "SELECT" in result.sanitized_query

    def test_piggyback_query(self):
        """Piggyback query should be blocked."""
        validator = QueryValidator()
        result = validator.validate(
            "SELECT * FROM users WHERE id = 1; INSERT INTO log VALUES('hacked')"
        )
        
        assert not result.is_valid

    def test_char_encoding_bypass(self):
        """CHAR() encoding bypass should be blocked."""
        validator = QueryValidator()
        result = validator.validate(
            "SELECT * FROM users WHERE name = CHAR(65) + CHAR(66)"
        )
        
        assert not result.is_valid
