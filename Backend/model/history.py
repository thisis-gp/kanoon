"""
Search history + suggestions (stored in Postgres — no Firebase needed).

Logs every query with a salted hash of the client address (never the address itself). The home-page
suggestions only show queries that at least MIN_DISTINCT_CLIENTS different clients asked and that pass a
content filter, so one person cannot plant a query that everybody sees. Old rows are deleted after
RETENTION_DAYS (searches and answer_cache).

Table: searches(id, query, kind, created_at, ip_hash)
"""
import os
import re
import threading
from contextlib import closing

from model.retrieval import RetrievalEngine

_eng = RetrievalEngine()

MIN_DISTINCT_CLIENTS = 5
MIN_SUGGESTION_CHARS = 3
MAX_SUGGESTION_CHARS = 80
SUGGESTION_WINDOW_DAYS = 30
CANDIDATE_ROWS = 60                 # rows scanned before the content filter
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
RETENTION_INTERVAL_S = 24 * 3600

# Shown when too few real queries qualify. Curated, no personal data.
CURATED_SUGGESTIONS = [
    "Anticipatory bail conditions under Section 438 CrPC",
    "Doctrine of basic structure of the Constitution",
    "Right to privacy as a fundamental right",
    "Grounds for quashing an FIR under Section 482 CrPC",
    "Limitation period for filing a civil suit",
    "Burden of proof in circumstantial evidence cases",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS searches (
    id         BIGSERIAL PRIMARY KEY,
    query      TEXT NOT NULL,
    kind       TEXT,                       -- 'ask' or 'search'
    created_at TIMESTAMPTZ DEFAULT now(),
    ip_hash    TEXT                        -- salted hash of the client address, never the address
);
-- Migration for databases created before ip_hash existed (old rows keep NULL and are never suggested).
ALTER TABLE searches ADD COLUMN IF NOT EXISTS ip_hash TEXT;
CREATE INDEX IF NOT EXISTS searches_query_idx ON searches (query);
CREATE INDEX IF NOT EXISTS searches_created_idx ON searches (created_at DESC);
"""


def init_db():
    with closing(_eng._conn()) as c, c, c.cursor() as cur:
        cur.execute(SCHEMA)


def log(query, kind, ip_hash=None):
    """Record a query. Never raises — logging must not break a request."""
    q = (query or "").strip()
    if not q:
        return
    try:
        with closing(_eng._conn()) as c, c, c.cursor() as cur:
            cur.execute("INSERT INTO searches (query, kind, ip_hash) VALUES (%s, %s, %s)",
                        (q[:300], kind, ip_hash))
    except Exception as e:
        print(f"[history] log failed (non-fatal): {type(e).__name__}")


# ---- what may be shown to everybody ----
_URL = re.compile(r"(https?://|www\.|\b[\w-]+\.(com|net|org|io|in|co|ly|xyz|ru|cn|info|biz)\b)", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
_BAD_WORDS = {"fuck", "shit", "bitch", "bastard", "asshole", "cunt", "slut", "porn",
              "nude", "xxx", "casino", "viagra", "bitcoin", "crypto", "lottery", "betting"}
_REPEAT = re.compile(r"(.)\1{5,}")
_WORD = re.compile(r"[a-z]+")


def is_suggestable(q: str) -> bool:
    """True when a query is safe to show to every visitor."""
    q = (q or "").strip()
    if not MIN_SUGGESTION_CHARS <= len(q) <= MAX_SUGGESTION_CHARS:
        return False
    if _URL.search(q) or _EMAIL.search(q) or _PHONE.search(q) or _REPEAT.search(q):
        return False
    if any(w in _BAD_WORDS for w in _WORD.findall(q.lower())):
        return False
    letters = sum(ch.isalpha() for ch in q)
    return letters >= len(q) * 0.5                      # mostly text, not symbols or digits


def suggestions(limit=6):
    """Popular recent queries that >= MIN_DISTINCT_CLIENTS distinct clients asked and that pass the
    content filter; topped up with the curated list."""
    out, seen = [], set()
    try:
        with closing(_eng._conn()) as c, c, c.cursor() as cur:
            cur.execute("""
                SELECT min(query)
                FROM searches
                WHERE created_at > now() - make_interval(days => %s) AND ip_hash IS NOT NULL
                GROUP BY lower(query)
                HAVING count(DISTINCT ip_hash) >= %s
                ORDER BY count(DISTINCT ip_hash) DESC, max(created_at) DESC
                LIMIT %s
            """, (SUGGESTION_WINDOW_DAYS, MIN_DISTINCT_CLIENTS, CANDIDATE_ROWS))
            for (q,) in cur.fetchall():
                if is_suggestable(q) and q.lower() not in seen:
                    seen.add(q.lower())
                    out.append(q)
    except Exception as e:
        print(f"[history] suggestions failed: {type(e).__name__}")
    for q in CURATED_SUGGESTIONS:
        if len(out) >= limit:
            break
        if q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out[:limit]


# ---- retention ----
def purge_old(days=None):
    """Delete searches and cached answers older than `days` (default RETENTION_DAYS).
    Returns {table: rows deleted}; a missing table is skipped."""
    days = RETENTION_DAYS if days is None else days
    deleted = {}
    for table in ("searches", "answer_cache"):
        try:
            with closing(_eng._conn()) as c, c, c.cursor() as cur:
                cur.execute(f"DELETE FROM {table} WHERE created_at < now() - make_interval(days => %s)",
                            (days,))
                deleted[table] = cur.rowcount
        except Exception as e:
            print(f"[history] purge {table} skipped: {type(e).__name__}")
    return deleted


def _retention_loop(stop: threading.Event):
    while not stop.is_set():
        purge_old()
        stop.wait(RETENTION_INTERVAL_S)


def start_retention():
    """Purge now and then once a day, on a daemon thread. Returns the stop event."""
    stop = threading.Event()
    threading.Thread(target=_retention_loop, args=(stop,), name="retention", daemon=True).start()
    return stop
