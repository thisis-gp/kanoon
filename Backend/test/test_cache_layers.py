"""Cache layers (answer L1 + Postgres L2, search cache) and search SQL parameter order, with a fake DB."""
import json

import pytest

from model import ask as ask_mod
from model import llm_gateway
from model import retrieval as rt
from conftest import FakeEngine

HITS = [{"case_id": "660", "text": "The appeal is allowed.", "score": 1.0},
        {"case_id": "12", "text": "Costs awarded.", "score": 0.5}]


class FakeStore:
    """Plays answer_cache in Postgres."""

    def __init__(self):
        self.rows, self.puts, self.gets = {}, 0, 0

    def handler(self, sql, params):
        if sql.startswith("SELECT response"):
            self.gets += 1
            return [(self.rows[params[0]],)] if params[0] in self.rows else []
        if sql.startswith("INSERT INTO answer_cache"):
            self.puts += 1
            self.rows.setdefault(params[0], json.loads(params[1]))
        return []


@pytest.fixture
def env(monkeypatch):
    store = FakeStore()
    calls = {"search": 0, "llm": 0}

    class Eng(FakeEngine):
        def search(self, q, k=6, case_id=None):
            calls["search"] += 1
            return HITS

    eng = Eng(store.handler)
    monkeypatch.setattr(ask_mod, "_engine", eng)
    monkeypatch.setattr(ask_mod, "_cache_ready", False)
    ask_mod._answer_cache.clear()

    def gen(prompt, system=None, temperature=0.2):
        calls["llm"] += 1
        return "Allowed [1] with costs [2] and bogus [9].", "fake"
    monkeypatch.setattr(llm_gateway, "generate", gen)
    yield store, calls
    ask_mod._answer_cache.clear()


def test_miss_then_memory_hit_then_db_hit(env):
    store, calls = env
    r1 = ask_mod.answer("What happened?")
    assert calls == {"search": 1, "llm": 1} and store.puts == 1
    assert r1["cited"] == [1, 2] and r1["provider"] == "fake"      # [9] is out of range
    assert [s["case_id"] for s in r1["sources"]] == ["660", "12"]

    assert ask_mod.answer("  what HAPPENED? ") == r1               # L1 (normalised key)
    assert calls == {"search": 1, "llm": 1}

    ask_mod._answer_cache.clear()                                   # simulate restart
    assert ask_mod.answer("What happened?") == r1                   # L2 (Postgres)
    assert calls == {"search": 1, "llm": 1} and store.gets >= 1
    assert len(ask_mod._answer_cache) == 1                          # L2 hit refills L1


def test_scope_and_k_are_part_of_the_key(env):
    _, calls = env
    ask_mod.answer("q")
    ask_mod.answer("q", case_id="660")
    ask_mod.answer("q", k=3)
    assert calls["llm"] == 3


def test_no_hits_abstains_without_llm_call(env, monkeypatch):
    store, calls = env
    monkeypatch.setattr(type(ask_mod._engine), "search", lambda self, *a, **k: [])
    r = ask_mod.answer("anything")
    assert r["answer"] == "Not available in the sources."
    assert r["sources"] == [] and r["cited"] == [] and calls["llm"] == 0


def test_db_failure_never_breaks_answering(env, monkeypatch):
    _, calls = env

    def broken(sql, params):
        raise OSError("db down")
    monkeypatch.setattr(ask_mod._engine, "handler", broken)
    r = ask_mod.answer("q")
    assert r["answer"].startswith("Allowed") and calls["llm"] == 1


def test_l1_is_bounded(env):
    for i in range(256):
        ask_mod._answer_cache[f"k{i}"] = {}
    ask_mod.answer("fresh")
    assert len(ask_mod._answer_cache) <= 256


def test_abstention_instruction_is_exact():
    assert "Not available in the sources." in ask_mod.SYSTEM


# ---- retrieval engine search cache + SQL parameter order ----

class _Embedder:
    def encode(self, texts, **k):
        return [[0.1, 0.2]]


class _Reranker:
    def __init__(self):
        self.pairs = []

    def predict(self, pairs, batch_size=16):
        self.pairs.append(len(pairs))
        return [float(len(t)) for _, t in pairs]


@pytest.fixture
def engine(monkeypatch):
    rer = _Reranker()
    monkeypatch.setattr(rt, "_embed", lambda: _Embedder())
    monkeypatch.setattr(rt, "_rerank", lambda: rer)
    eng = rt.RetrievalEngine("unused")
    queries = []

    def handler(sql, params):
        queries.append((sql, params))
        if "embedding <=>" in sql:
            return [(1, "A", "short"), (2, "A", "a much longer passage here")]
        return [(2, "A", "a much longer passage here"), (3, "B", "mid length")]
    eng._conn = lambda: __import__("conftest").FakeConn(handler)
    return eng, rer, queries


def test_search_ranks_by_rerank_and_caches(engine):
    eng, rer, queries = engine
    out = eng.search("tax", k=2)
    assert [h["text"] for h in out] == ["a much longer passage here", "mid length"]
    n = len(queries)
    assert eng.search("tax", k=2) == out
    assert len(queries) == n and len(rer.pairs) == 1               # cache hit: no DB, no rerank
    eng.search("tax", k=3)                                         # different k -> new entry
    assert len(rer.pairs) == 2


def test_dense_parameter_order_with_case_id(engine):
    eng, _, queries = engine
    eng.search("tax", k=2, case_id="660")
    dense = next(q for q in queries if "embedding <=>" in q[0])
    assert dense[0].index("WHERE case_id") < dense[0].index("ORDER BY embedding")
    assert dense[1][0] == "660" and dense[1][1].startswith("[") and dense[1][2] == rt.CAND
    bm25 = next(q for q in queries if "@@@" in q[0])
    assert bm25[1] == ["tax", "660", rt.CAND]


def test_search_cache_is_bounded(engine):
    eng, _, _ = engine
    for i in range(520):
        eng.search(f"q{i}", k=1)
    assert len(eng._cache) <= 512


def test_rerank_depth_limits_pairs(engine, monkeypatch):
    eng, rer, _ = engine
    monkeypatch.setattr(rt, "RERANK_DEPTH", 2)
    eng.search("depth", k=5)
    assert rer.pairs[-1] == 2
