import os
from typing import Any, Optional


class ClickHouseClient:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self._host = host or os.environ.get("CLICKHOUSE_HOST", "localhost")
        self._port = port or int(os.environ.get("CLICKHOUSE_PORT", "8123"))
        self._username = username or os.environ.get("CLICKHOUSE_USER", "default")
        self._password = password or os.environ.get("CLICKHOUSE_PASSWORD", "")
        self._database = database or os.environ.get("CLICKHOUSE_DATABASE", "default")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import clickhouse_connect
            except ImportError:
                raise ImportError(
                    "clickhouse-connect package required. Install with: pip install clickhouse-connect"
                )

            self._client = clickhouse_connect.get_client(
                host=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                database=self._database,
            )
        return self._client

    def query(self, query: str, parameters: Optional[dict] = None) -> list[dict[str, Any]]:
        client = self._get_client()
        result = client.query(query, parameters=parameters or {})
        columns = result.column_names
        return [dict(zip(columns, row)) for row in result.result_rows]

    def query_df(self, query: str, parameters: Optional[dict] = None) -> Any:
        client = self._get_client()
        return client.query_df(query, parameters=parameters or {})

    def command(self, cmd: str, parameters: Optional[dict] = None) -> Any:
        client = self._get_client()
        return client.command(cmd, parameters=parameters or {})

    def insert(
        self,
        table: str,
        data: list[dict[str, Any]],
        column_names: Optional[list[str]] = None,
    ) -> None:
        if not data:
            return

        client = self._get_client()
        columns = column_names or list(data[0].keys())
        rows = [[row.get(col) for col in columns] for row in data]
        client.insert(table, rows, column_names=columns)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "ClickHouseClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
