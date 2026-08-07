"""
Search history + suggestions (stored in Postgres — no Firebase needed).

Logs every query and surfaces the most popular recent ones as home-page
suggestions. Anonymous + aggregate, so no auth required.

Table: searches(id, query, kind, created_at)
"""
from model.retrieval import RetrievalEngine

_eng = RetrievalEngine()

SCHEMA = """
CREATE TABLE IF NOT EXISTS searches (
    id         BIGSERIAL PRIMARY KEY,
    query      TEXT NOT NULL,
    kind       TEXT,                       -- 'ask' or 'search'
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS searches_query_idx ON searches (query);
CREATE INDEX IF NOT EXISTS searches_created_idx ON searches (created_at DESC);
"""


def init_db():
    with _eng._conn() as c, c.cursor() as cur:
        cur.execute(SCHEMA)


def log(query, kind):
    """Record a query. Never raises — logging must not break a request."""
    q = (query or "").strip()
    if not q:
        return
    try:
        with _eng._conn() as c, c.cursor() as cur:
            cur.execute("INSERT INTO searches (query, kind) VALUES (%s, %s)", (q[:300], kind))
    except Exception as e:
        print(f"[history] log failed (non-fatal): {e}")


def suggestions(limit=6):
    """Most-used queries recently, de-duplicated (case-insensitive)."""
    try:
        with _eng._conn() as c, c.cursor() as cur:
            cur.execute("""
                SELECT query
                FROM searches
                WHERE created_at > now() - interval '30 days'
                GROUP BY lower(query), query
                ORDER BY count(*) DESC, max(created_at) DESC
                LIMIT %s
            """, (limit,))
            seen, out = set(), []
            for (q,) in cur.fetchall():
                k = q.lower()
                if k not in seen:
                    seen.add(k); out.append(q)
            return out[:limit]
    except Exception as e:
        print(f"[history] suggestions failed: {e}")
        return []
