"""Needs Postgres. RUN_INTEGRATION=1 and DATABASE_URL pointing at a THROWAWAY database: these tests drop
and recreate `searches` and `answer_cache`."""
from contextlib import closing


def _count_conns(eng):
    import psycopg2
    with closing(psycopg2.connect(eng.dsn)) as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                    "AND pid <> pg_backend_pid()")
        return cur.fetchone()[0]


def test_pg_pool_reuses_connections_and_suggestions_sql():
    from model import history as h
    from model.retrieval import RetrievalEngine
    eng = RetrievalEngine()
    h._eng = eng
    with closing(eng._conn()) as c, c, c.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS searches, answer_cache")
        # old production shape: no ip_hash column
        cur.execute("CREATE TABLE searches (id BIGSERIAL PRIMARY KEY, query TEXT NOT NULL, kind TEXT, "
                    "created_at TIMESTAMPTZ DEFAULT now())")
        cur.execute("INSERT INTO searches (query, kind) VALUES ('legacy row', 'ask')")
        cur.execute("CREATE TABLE answer_cache (cache_key TEXT PRIMARY KEY, response JSONB NOT NULL, "
                    "created_at TIMESTAMPTZ DEFAULT now())")
    h.init_db(); h.init_db()                                  # migration is idempotent
    base = _count_conns(eng)
    for i in range(200):                                      # far more calls than the pool size
        h.log(f"Section 302 IPC {i % 2}", "ask", f"hash{i % 7}")
    assert _count_conns(eng) - base <= 10                    # bounded by DB_POOL_MAX, no per-call connection
    h.log("buy pills at spam.example.com", "ask", "x1")
    for i in range(6):
        h.log("buy pills at spam.example.com", "ask", f"spam{i}")
    out = h.suggestions(limit=8)
    assert "Section 302 IPC 0" in out and "Section 302 IPC 1" in out
    assert not any("spam" in q for q in out) and "legacy row" not in out
    assert len(out) == 8                                      # topped up from the curated list
    with closing(eng._conn()) as c, c, c.cursor() as cur:     # backdate, then purge
        cur.execute("UPDATE searches SET created_at = now() - interval '45 days' WHERE query LIKE 'Section%'")
        cur.execute("INSERT INTO answer_cache VALUES ('old', '{}', now() - interval '45 days'), "
                    "('new', '{}', now())")
    deleted = h.purge_old()
    assert deleted["searches"] == 200 and deleted["answer_cache"] == 1
    with closing(eng._conn()) as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM answer_cache"); assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM searches WHERE query LIKE 'Section%'"); assert cur.fetchone()[0] == 0
