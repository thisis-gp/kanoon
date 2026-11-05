"""Shared pytest fixtures. Unit tests need no GPU, network, or database.

Legacy script-style tests that need Postgres or a live LLM key are skipped unless
RUN_INTEGRATION=1 (the retrieval one TRUNCATEs `chunks`, so never run it on real data).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INTEGRATION_TESTS = {"test_search_end_to_end", "test_graph_queries", "test_gateway",
                     "test_ask_grounded", "test_pg_mining_and_cited_by",
                     "test_pg_pool_reuses_connections_and_suggestions_sql"}


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="integration test: set RUN_INTEGRATION=1 (needs DB / LLM key)")
    for item in items:
        if item.name in INTEGRATION_TESTS:
            item.add_marker(skip)


class FakeCursor:
    def __init__(self, handler):
        self.handler, self.rows, self.rowcount = handler, [], 0

    def execute(self, sql, params=None):
        self.rows = list(self.handler(" ".join(sql.split()), params) or [])

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self, handler):
        self.handler = handler

    def cursor(self):
        return FakeCursor(self.handler)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


class FakeEngine:
    """Stands in for RetrievalEngine: `handler(sql, params) -> rows` plays the database."""

    def __init__(self, handler=lambda sql, params: []):
        self.handler, self._cache = handler, {}

    def _conn(self):
        return FakeConn(self.handler)


@pytest.fixture
def api(monkeypatch):
    """The FastAPI module with a clean rate-limit table and no real DB calls."""
    from model import api as api_mod
    from model import history as history_mod
    api_mod._hits.clear()
    api_mod._last_prune[0] = 0.0
    api_mod._health_db.update(at=-1e9, ok=True)
    api_mod._health_lock = None
    monkeypatch.setattr(api_mod, "_db_ping", lambda: True)      # /health must not need a real DB
    monkeypatch.setattr(history_mod, "log", lambda *a, **k: None)
    yield api_mod
    api_mod._hits.clear()


@pytest.fixture
def client(api):
    from fastapi.testclient import TestClient
    return TestClient(api.app, raise_server_exceptions=False)
