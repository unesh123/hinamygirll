from __future__ import annotations

from unittest.mock import MagicMock, patch

from hinaa_api.memory.repository import MemoryRepository


def test_fts_search_pg_tsvector_path():
    """Verify that on Postgres, fts_search attempts tsvector full-text search first."""
    repo = MemoryRepository(db_path=":memory:")
    # Simulate a Postgres connection
    repo._pg = "postgresql+psycopg://user:pass@localhost:5432/hinaa"

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [{"id": "mem-1", "rank": 0.85}, {"id": "mem-2", "rank": 0.42}]
    mock_conn.execute.return_value = mock_cursor

    with patch.object(repo, "_get_connection", return_value=mock_conn):
        results = repo.fts_search("quantum computing algorithms", tenant_id="tenant-alpha", limit=10)

    assert len(results) == 2
    assert results[0] == ("mem-1", 0.85)
    assert results[1] == ("mem-2", 0.42)
    first_call_sql = mock_conn.execute.call_args_list[0][0][0]
    assert "to_tsvector('simple', content)" in first_call_sql
    assert "plainto_tsquery('simple', ?)" in first_call_sql


def test_fts_search_pg_multiterm_ilike_fallback():
    """Verify that if tsvector query fails on Postgres, multi-term ILIKE ranking takes over."""
    repo = MemoryRepository(db_path=":memory:")
    repo._pg = "postgresql+psycopg://user:pass@localhost:5432/hinaa"

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn

    def execute_side_effect(sql, params=None):
        if "to_tsvector" in sql:
            raise RuntimeError("function to_tsvector does not exist")
        cursor = MagicMock()
        cursor.fetchall.return_value = [{"id": "mem-fallback-1", "rank": 2.0}]
        return cursor

    mock_conn.execute.side_effect = execute_side_effect

    with patch.object(repo, "_get_connection", return_value=mock_conn):
        results = repo.fts_search("react hooks tutorial", tenant_id="default", limit=5)

    assert len(results) == 1
    assert results[0] == ("mem-fallback-1", 2.0)
    second_call_sql = mock_conn.execute.call_args_list[1][0][0]
    assert "content ILIKE ?" in second_call_sql
    assert "ORDER BY rank DESC" in second_call_sql
