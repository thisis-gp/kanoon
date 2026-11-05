"""Suggestions: poisoning resistance, privacy (ip_hash), retention. Fake DB, no network."""
import pytest

from model import history as h
from conftest import FakeEngine


class Store:
    """Plays `searches`: rows of (query, kind, ip_hash)."""

    def __init__(self):
        self.rows, self.sql = [], []

    def handler(self, sql, params):
        self.sql.append((sql, params))
        if sql.startswith("INSERT INTO searches"):
            self.rows.append(params)
            return []
        if sql.startswith("SELECT min(query)"):
            groups = {}
            for q, _, ip in self.rows:
                if ip is not None:
                    groups.setdefault(q.lower(), (q, set()))[1].add(ip)
            need = params[1]
            ok = [v for v in groups.values() if len(v[1]) >= need]
            ok.sort(key=lambda v: -len(v[1]))
            return [(q,) for q, _ in ok]
        return []


@pytest.fixture
def store(monkeypatch):
    st = Store()
    monkeypatch.setattr(h, "_eng", FakeEngine(st.handler))
    return st


def _ask(store, q, n_ips, prefix="ip"):
    for i in range(n_ips):
        h.log(q, "ask", f"{prefix}{i}")


def test_log_stores_hash_not_raw_ip(store):
    h.log("  bail law  ", "ask", "abcd" * 8)
    assert store.rows == [("bail law", "ask", "abcd" * 8)]
    h.log("legacy caller", "ask")                           # still works without a hash
    assert store.rows[-1][2] is None


def test_one_client_cannot_plant_a_suggestion(store):
    _ask(store, "Buy cheap watches here", 1)
    for _ in range(50):
        h.log("Buy cheap watches here", "ask", "same-ip")   # 50 hits, one client
    assert "Buy cheap watches here" not in h.suggestions()


def test_needs_five_distinct_clients(store):
    _ask(store, "Doctrine of promissory estoppel", 4)
    assert "Doctrine of promissory estoppel" not in h.suggestions()
    _ask(store, "Doctrine of promissory estoppel", 5)
    assert h.suggestions()[0] == "Doctrine of promissory estoppel"


def test_distinct_threshold_is_in_sql(store):
    h.suggestions(limit=3)
    sql, params = next(x for x in store.sql if x[0].startswith("SELECT min(query)"))
    assert "count(DISTINCT ip_hash)" in " ".join(sql.split()) and "ip_hash IS NOT NULL" in sql
    assert params[1] == 5


@pytest.mark.parametrize("bad", [
    "hi", "x" * 81, "see https://evil.example/x now", "visit www.spam.com", "mail me bob@example.com",
    "call +91 98765 43210 for help", "call 9876543210 now", "free casino bonus tips",
    "aaaaaaaaaaaa", "!!! ??? ### $$$ %%%", "FUCK this court",
])
def test_filter_rejects(bad):
    assert not h.is_suggestable(bad)


@pytest.mark.parametrize("good", [
    "Section 302 IPC", "Anticipatory bail conditions", "what is res judicata", "Article 21 right to life"])
def test_filter_accepts_legal_queries(good):
    assert h.is_suggestable(good)


def test_bad_queries_dropped_even_with_many_clients(store):
    _ask(store, "contact me at bob@example.com", 9)
    _ask(store, "Section 498A IPC", 6)
    out = h.suggestions()
    assert "contact me at bob@example.com" not in out and out[0] == "Section 498A IPC"


def test_falls_back_to_curated_list(store):
    out = h.suggestions(limit=6)
    assert out == h.CURATED_SUGGESTIONS[:6]
    assert all(h.is_suggestable(q) for q in h.CURATED_SUGGESTIONS)


def test_real_suggestions_come_first_then_curated(store):
    _ask(store, "Section 498A IPC", 5)
    out = h.suggestions(limit=3)
    assert out == ["Section 498A IPC", h.CURATED_SUGGESTIONS[0], h.CURATED_SUGGESTIONS[1]]


def test_db_failure_returns_curated(monkeypatch):
    def broken(sql, params):
        raise OSError("db down: postgresql://u:p@h/db")
    monkeypatch.setattr(h, "_eng", FakeEngine(broken))
    assert h.suggestions(3) == h.CURATED_SUGGESTIONS[:3]


def test_purge_deletes_both_tables_with_retention_days(monkeypatch):
    seen = []

    def handler(sql, params):
        seen.append((sql, params))
        return []
    eng = FakeEngine(handler)
    monkeypatch.setattr(h, "_eng", eng)
    out = h.purge_old(days=30)
    assert [s for s, _ in seen] == [
        "DELETE FROM searches WHERE created_at < now() - make_interval(days => %s)",
        "DELETE FROM answer_cache WHERE created_at < now() - make_interval(days => %s)"]
    assert all(p == (30,) for _, p in seen) and set(out) == {"searches", "answer_cache"}


def test_purge_skips_missing_table(monkeypatch):
    def handler(sql, params):
        if "answer_cache" in sql:
            raise RuntimeError("relation does not exist")
        return []
    monkeypatch.setattr(h, "_eng", FakeEngine(handler))
    assert set(h.purge_old()) == {"searches"}


def test_retention_default_and_env():
    assert h.RETENTION_DAYS == 30
    assert h.RETENTION_INTERVAL_S == 86400


def test_retention_runs_at_start_then_waits_a_day(monkeypatch):
    import threading
    runs = []
    monkeypatch.setattr(h, "purge_old", lambda days=None: runs.append(1))
    waits = []

    class Stop(threading.Event):
        def wait(self, t=None):
            waits.append(t); self.set()
    stop = Stop()
    h._retention_loop(stop)
    assert runs == [1] and waits == [86400]


def test_schema_has_migration_for_ip_hash():
    assert "ALTER TABLE searches ADD COLUMN IF NOT EXISTS ip_hash" in h.SCHEMA


def test_startup_runs_migration_and_retention(monkeypatch):
    from model import api as api_mod
    called = []
    monkeypatch.setattr(h, "init_db", lambda: called.append("init"))
    monkeypatch.setattr(h, "start_retention", lambda: called.append("retention"))
    import model.retrieval as rt
    monkeypatch.setattr(rt, "_embed", lambda: None)
    monkeypatch.setattr(rt, "_rerank", lambda: None)
    api_mod._warm_models()
    assert called == ["init", "retention"]


def test_api_passes_hashed_ip_to_history(monkeypatch):
    from fastapi.testclient import TestClient
    from model import api as api_mod, ask as ask_mod
    got = []
    monkeypatch.setattr(h, "log", lambda q, kind, ip_hash=None: got.append((q, kind, ip_hash)))
    monkeypatch.setattr(ask_mod, "answer", lambda *a, **k: {})
    monkeypatch.setattr(api_mod._engine, "search", lambda *a, **k: [])
    api_mod._hits.clear()
    c = TestClient(api_mod.app)
    c.post("/ask", json={"query": "q1"}, headers={"x-forwarded-for": "7.7.7.7"})
    c.post("/query", json={"query": "q2"}, headers={"x-forwarded-for": "7.7.7.7"})
    api_mod._hits.clear()
    assert [(q, k) for q, k, _ in got] == [("q1", "ask"), ("q2", "search")]
    expect = api_mod.ip_hash("7.7.7.7", 32)
    assert all(ip == expect and "7.7.7.7" not in ip and len(ip) == 32 for _, _, ip in got)
