"""
Tests for QueryForge query execution functionality.

Tests cover:
- Successful query execution
- Query timeout handling
- Row limit enforcement
- Error handling and rollback
- Unsupported source types
- Execution metrics (timing, truncation)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


class TestQueryExecution:
    """Test QueryForgeService._execute_query method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_embedding_client(self):
        """Create mock embedding client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session, mock_embedding_client):
        """Create QueryForgeService with mocks."""
        from app.services.queryforge_service import QueryForgeService
        return QueryForgeService(
            session=mock_session,
            embedding_client=mock_embedding_client,
        )

    @pytest.mark.asyncio
    async def test_execute_query_success(self, service, mock_session):
        """Should return results on successful execution."""
        # Mock query result
        mock_result = MagicMock()
        mock_result.keys.return_value = ["id", "name", "value"]
        mock_result.fetchmany.return_value = [
            (1, "Alice", 100),
            (2, "Bob", 200),
        ]
        mock_session.execute.return_value = mock_result
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELECT id, name, value FROM users",
                source_type="postgres"
            )
        
        assert result["status"] == "success"
        assert result["columns"] == ["id", "name", "value"]
        assert len(result["rows"]) == 2
        assert result["row_count"] == 2
        assert result["truncated"] is False
        assert "execution_time_ms" in result

    @pytest.mark.asyncio
    async def test_execute_query_with_column_dict(self, service, mock_session):
        """Should return rows as dicts with column keys."""
        mock_result = MagicMock()
        mock_result.keys.return_value = ["product", "price"]
        mock_result.fetchmany.return_value = [
            ("Widget", 9.99),
            ("Gadget", 19.99),
        ]
        mock_session.execute.return_value = mock_result
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELECT product, price FROM products",
                source_type="postgres"
            )
        
        assert result["rows"][0] == {"product": "Widget", "price": 9.99}
        assert result["rows"][1] == {"product": "Gadget", "price": 19.99}


class TestQueryExecutionTimeout:
    """Test query timeout handling."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_embedding_client(self):
        """Create mock embedding client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session, mock_embedding_client):
        """Create QueryForgeService with mocks."""
        from app.services.queryforge_service import QueryForgeService
        return QueryForgeService(
            session=mock_session,
            embedding_client=mock_embedding_client,
        )

    @pytest.mark.asyncio
    async def test_execute_query_timeout(self, service, mock_session):
        """Should handle timeout gracefully."""
        # Make execute hang until timeout
        async def slow_query():
            await asyncio.sleep(10)
            return MagicMock()
        
        mock_session.execute.side_effect = slow_query
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 0.1  # Very short timeout
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELECT * FROM slow_table",
                source_type="postgres"
            )
        
        assert result["status"] == "error"
        assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_timeout_triggers_rollback(self, service, mock_session):
        """Should rollback on timeout."""
        async def slow_query():
            await asyncio.sleep(10)
            return MagicMock()
        
        mock_session.execute.side_effect = slow_query
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 0.1
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            await service._execute_query(
                query="SELECT * FROM slow_table",
                source_type="postgres"
            )
        
        mock_session.rollback.assert_called_once()


class TestQueryExecutionRowLimits:
    """Test row limit enforcement."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_embedding_client(self):
        """Create mock embedding client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session, mock_embedding_client):
        """Create QueryForgeService with mocks."""
        from app.services.queryforge_service import QueryForgeService
        return QueryForgeService(
            session=mock_session,
            embedding_client=mock_embedding_client,
        )

    @pytest.mark.asyncio
    async def test_execute_query_truncates_results(self, service, mock_session):
        """Should truncate results exceeding max_rows."""
        # Return more rows than max_rows
        mock_result = MagicMock()
        mock_result.keys.return_value = ["id"]
        mock_result.fetchmany.return_value = [(i,) for i in range(11)]  # 11 rows
        mock_session.execute.return_value = mock_result
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 10  # Limit to 10
            
            result = await service._execute_query(
                query="SELECT id FROM large_table",
                source_type="postgres"
            )
        
        assert result["status"] == "success"
        assert result["row_count"] == 10
        assert result["truncated"] is True

    @pytest.mark.asyncio
    async def test_execute_query_not_truncated_under_limit(self, service, mock_session):
        """Should not truncate when under limit."""
        mock_result = MagicMock()
        mock_result.keys.return_value = ["id"]
        mock_result.fetchmany.return_value = [(i,) for i in range(5)]
        mock_session.execute.return_value = mock_result
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELECT id FROM small_table",
                source_type="postgres"
            )
        
        assert result["truncated"] is False
        assert result["row_count"] == 5


class TestQueryExecutionErrorHandling:
    """Test error handling during query execution."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_embedding_client(self):
        """Create mock embedding client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session, mock_embedding_client):
        """Create QueryForgeService with mocks."""
        from app.services.queryforge_service import QueryForgeService
        return QueryForgeService(
            session=mock_session,
            embedding_client=mock_embedding_client,
        )

    @pytest.mark.asyncio
    async def test_execute_query_handles_db_error(self, service, mock_session):
        """Should handle database errors gracefully."""
        mock_session.execute.side_effect = Exception("Database connection lost")
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELECT * FROM users",
                source_type="postgres"
            )
        
        assert result["status"] == "error"
        assert "Database connection lost" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_query_error_triggers_rollback(self, service, mock_session):
        """Should rollback on error."""
        mock_session.execute.side_effect = Exception("Query error")
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            await service._execute_query(
                query="SELECT * FROM users",
                source_type="postgres"
            )
        
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_handles_sql_syntax_error(self, service, mock_session):
        """Should handle SQL syntax errors."""
        mock_session.execute.side_effect = Exception(
            "syntax error at or near \"SELEC\""
        )
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELEC * FROM users",  # Typo
                source_type="postgres"
            )
        
        assert result["status"] == "error"
        assert "syntax error" in result["error"]


class TestQueryExecutionSourceTypes:
    """Test source type handling."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_embedding_client(self):
        """Create mock embedding client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session, mock_embedding_client):
        """Create QueryForgeService with mocks."""
        from app.services.queryforge_service import QueryForgeService
        return QueryForgeService(
            session=mock_session,
            embedding_client=mock_embedding_client,
        )

    @pytest.mark.asyncio
    async def test_execute_query_supports_postgres(self, service, mock_session):
        """Should support postgres source type."""
        mock_result = MagicMock()
        mock_result.keys.return_value = []
        mock_result.fetchmany.return_value = []
        mock_session.execute.return_value = mock_result
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELECT 1",
                source_type="postgres"
            )
        
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_query_supports_mysql(self, service, mock_session):
        """Should support mysql source type."""
        mock_result = MagicMock()
        mock_result.keys.return_value = []
        mock_result.fetchmany.return_value = []
        mock_session.execute.return_value = mock_result
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELECT 1",
                source_type="mysql"
            )
        
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_query_rejects_unsupported_source(self, service, mock_session):
        """Should reject unsupported source types."""
        result = await service._execute_query(
            query="db.users.find({})",
            source_type="mongodb"  # Unsupported
        )
        
        assert result["status"] == "error"
        assert "not supported" in result["error"].lower()
        
        # Should not attempt to execute
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_query_rejects_elasticsearch(self, service, mock_session):
        """Should reject elasticsearch/opensearch source types."""
        result = await service._execute_query(
            query='{"query": {"match_all": {}}}',
            source_type="elasticsearch"
        )
        
        assert result["status"] == "error"
        assert "not supported" in result["error"].lower()


class TestQueryExecutionMetrics:
    """Test execution metrics reporting."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_embedding_client(self):
        """Create mock embedding client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session, mock_embedding_client):
        """Create QueryForgeService with mocks."""
        from app.services.queryforge_service import QueryForgeService
        return QueryForgeService(
            session=mock_session,
            embedding_client=mock_embedding_client,
        )

    @pytest.mark.asyncio
    async def test_execute_query_reports_timing(self, service, mock_session):
        """Should report execution time."""
        mock_result = MagicMock()
        mock_result.keys.return_value = []
        mock_result.fetchmany.return_value = []
        mock_session.execute.return_value = mock_result
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELECT 1",
                source_type="postgres"
            )
        
        assert "execution_time_ms" in result
        assert isinstance(result["execution_time_ms"], float)
        assert result["execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_execute_query_timing_is_rounded(self, service, mock_session):
        """Execution time should be rounded to 2 decimal places."""
        mock_result = MagicMock()
        mock_result.keys.return_value = []
        mock_result.fetchmany.return_value = []
        mock_session.execute.return_value = mock_result
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELECT 1",
                source_type="postgres"
            )
        
        # Check that execution_time_ms has at most 2 decimal places
        time_str = str(result["execution_time_ms"])
        if '.' in time_str:
            decimal_places = len(time_str.split('.')[1])
            assert decimal_places <= 2


class TestQueryExecutionEmptyResults:
    """Test handling of empty query results."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_embedding_client(self):
        """Create mock embedding client."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session, mock_embedding_client):
        """Create QueryForgeService with mocks."""
        from app.services.queryforge_service import QueryForgeService
        return QueryForgeService(
            session=mock_session,
            embedding_client=mock_embedding_client,
        )

    @pytest.mark.asyncio
    async def test_execute_query_empty_results(self, service, mock_session):
        """Should handle empty result set."""
        mock_result = MagicMock()
        mock_result.keys.return_value = ["id", "name"]
        mock_result.fetchmany.return_value = []
        mock_session.execute.return_value = mock_result
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELECT * FROM users WHERE 1=0",
                source_type="postgres"
            )
        
        assert result["status"] == "success"
        assert result["columns"] == ["id", "name"]
        assert result["rows"] == []
        assert result["row_count"] == 0
        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_execute_query_no_columns(self, service, mock_session):
        """Should handle result with no columns."""
        mock_result = MagicMock()
        mock_result.keys.return_value = []  # No columns
        mock_result.fetchmany.return_value = []
        mock_session.execute.return_value = mock_result
        
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.QUERYFORGE_EXECUTION_TIMEOUT = 30
            mock_settings.QUERYFORGE_MAX_ROWS = 1000
            
            result = await service._execute_query(
                query="SELECT",  # Edge case
                source_type="postgres"
            )
        
        assert result["status"] == "success"
        assert result["columns"] == []
