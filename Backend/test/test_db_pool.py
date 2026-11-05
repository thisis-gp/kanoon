"""DB connections go back to the pool (no leaks), pool exhaustion gives Busy, BM25 errors don't leak queries."""
import threading
from contextlib import closing

import pytest

from model import retrieval as rt
from model.errors import Busy


class _RawConn:
    closed = 0

    def __init__(self):
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def rollback(self):
        self.rollbacks += 1

    def cursor(self):
        raise NotImplementedError


class _FakePool:
    def __init__(self):
        self.out, self.put = [], []

    def getconn(self):
        c = _RawConn()
        self.out.append(c)
        return c

    def putconn(self, conn, close=False):
        self.put.append(conn)


@pytest.fixture
def pool(monkeypatch):
    p = _FakePool()
    monkeypatch.setitem(rt._pools, "dsn-test", (p, threading.BoundedSemaphore(2)))
    monkeypatch.setattr(rt, "DB_POOL_TIMEOUT", 0.05)
    yield p
    rt._pools.pop("dsn-test", None)


def test_closing_returns_connection_to_pool(pool):
    eng = rt.RetrievalEngine("dsn-test")
    for _ in range(10):                       # more iterations than pool slots: nothing leaks
        with closing(eng._conn()) as c, c:
            pass
    assert len(pool.out) == 10 and pool.put == pool.out
    assert all(c.rollbacks == 1 for c in pool.out)


def test_connection_returned_even_when_body_raises(pool):
    eng = rt.RetrievalEngine("dsn-test")
    with pytest.raises(ValueError):
        with closing(eng._conn()) as c, c:
            raise ValueError("boom")
    assert pool.put == pool.out
    with closing(eng._conn()), closing(eng._conn()):   # both slots free again
        pass


def test_double_close_returns_once(pool):
    c = rt.RetrievalEngine("dsn-test")._conn()
    c.close(); c.close()
    assert len(pool.put) == 1


def test_exhausted_pool_raises_busy_instead_of_blocking(pool):
    eng = rt.RetrievalEngine("dsn-test")
    a, b = eng._conn(), eng._conn()
    with pytest.raises(Busy):
        eng._conn()
    a.close()
    eng._conn().close()                       # a freed slot is usable again
    b.close()


def test_failed_getconn_releases_slot(monkeypatch, pool):
    eng = rt.RetrievalEngine("dsn-test")
    monkeypatch.setattr(pool, "getconn", lambda: (_ for _ in ()).throw(OSError("down")))
    for _ in range(5):
        with pytest.raises(OSError):
            eng._conn()


def test_every_module_closes_its_connections():
    """Static guard: no module opens a connection with a bare `with x._conn() as ...` (commit only)."""
    import pathlib, re
    root = pathlib.Path(rt.__file__).parent
    bad = []
    for f in root.glob("*.py"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"with\s+[\w\.\(\)]+\._conn\(\)\s+as", line):
                bad.append(f"{f.name}:{i}")
    assert not bad, bad


def test_bm25_failure_logs_only_exception_type(capsys, monkeypatch):
    from conftest import FakeConn

    class _Emb:
        def encode(self, t, **k):
            return [[0.1, 0.2]]

    class _Rer:
        def predict(self, pairs, batch_size=16):
            return [1.0] * len(pairs)
    monkeypatch.setattr(rt, "_embed", lambda: _Emb())
    monkeypatch.setattr(rt, "_rerank", lambda: _Rer())

    def handler(sql, params):
        if "@@@" in sql:
            raise RuntimeError("syntax error near 'my private legal question'")
        return [(1, "A", "some passage text")]
    eng = rt.RetrievalEngine("x")
    eng._conn = lambda: FakeConn(handler)
    assert eng.search("my private legal question", k=1)[0]["case_id"] == "A"   # dense-only fallback
    err = capsys.readouterr().err
    assert "RuntimeError" in err and "private" not in err
