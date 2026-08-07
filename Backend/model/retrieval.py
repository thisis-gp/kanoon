"""
AILSE retrieval core (Slice 1) — everything in Postgres/ParadeDB.

Pipeline (benchmark-proven): MiniLM dense (pgvector) + BM25 (pg_search) -> RRF
fuse -> cross-encoder rerank. One `chunks` table serves both scopes:
  - global "ask": search across all cases
  - per-case chat: search(query, case_id=X) -> WHERE case_id = X first

No FAISS, no numpy index files, no in-memory BM25 — Postgres is the store.

CLI:
  python retrieval.py init                     # create extensions + table + indexes
  python retrieval.py build <cleaned_texts_dir>
  python retrieval.py search "your question" [case_id]
"""
import os
import re
import sys

# psycopg2 imported lazily inside DB methods so the pure chunker works without it

# ---- config ----
DSN = os.getenv("DATABASE_URL", "postgresql://ailse:ailse@localhost:5432/ailse")
EMBED_MODEL = "all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DIM = 384
TARGET_CHARS = 1000        # ~256 tokens for MiniLM
OVERLAP_SENTENCES = 1
CAND = 50                  # candidates per method + rerank depth

SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;
CREATE TABLE IF NOT EXISTS chunks (
    id        BIGSERIAL PRIMARY KEY,
    case_id   TEXT NOT NULL,
    text      TEXT NOT NULL,
    embedding vector({DIM})
);
CREATE INDEX IF NOT EXISTS chunks_case_idx ON chunks (case_id);
CREATE INDEX IF NOT EXISTS chunks_hnsw_idx ON chunks
    USING hnsw (embedding vector_cosine_ops);
-- pg_search BM25 index (ParadeDB). key_field must be the PK.
CREATE INDEX IF NOT EXISTS chunks_bm25_idx ON chunks
    USING bm25 (id, case_id, text) WITH (key_field='id');
"""

# ---- lazy models (loaded once per process) ----
_embedder = None
_reranker = None
def _embed():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(EMBED_MODEL, device="cpu")
    return _embedder
def _rerank():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(RERANK_MODEL, device="cpu")
    return _reranker


# ---- sentence-safe, word-safe chunking ----
_SENT = re.compile(r"(?<=[.?!;:])\s+(?=[A-Z0-9\"'(])")
def _sentences(text):
    text = re.sub(r"\s+", " ", text).strip()
    return [s for s in _SENT.split(text) if s]

def _word_split(sentence, limit):
    """Fallback for a single monster sentence — split on word boundaries only."""
    words, out, cur = sentence.split(" "), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > limit and cur:
            out.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return out

def chunk_text(text, target=TARGET_CHARS, overlap=OVERLAP_SENTENCES):
    """Pack whole sentences to ~target chars; never cut mid-word or mid-sentence."""
    sents, chunks, cur = _sentences(text), [], []
    cur_len = 0
    for s in sents:
        if len(s) > target * 1.5:                 # monster sentence -> word-safe split
            if cur:
                chunks.append(" ".join(cur)); cur, cur_len = [], 0
            chunks.extend(_word_split(s, target))
            continue
        if cur_len + len(s) > target and cur:
            chunks.append(" ".join(cur))
            cur = cur[-overlap:] if overlap else []  # sentence overlap
            cur_len = sum(len(x) for x in cur)
        cur.append(s); cur_len += len(s)
    if cur:
        chunks.append(" ".join(cur))
    return [c for c in chunks if len(c) > 60]

def _vec_literal(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


class RetrievalEngine:
    def __init__(self, dsn=DSN):
        self.dsn = dsn
        self._cache = {}          # (query, k, case_id) -> results; bounded below

    def _conn(self):
        import psycopg2
        return psycopg2.connect(self.dsn)

    def init_db(self):
        with self._conn() as c, c.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        print("[init] schema + extensions + indexes ready")

    def build(self, cases_dir, batch=256):
        import glob
        from psycopg2.extras import execute_values
        files = sorted(glob.glob(os.path.join(cases_dir, "*.txt")),
                       key=lambda p: os.path.basename(p))
        emb = _embed()
        c = self._conn()
        cur = c.cursor()
        cur.execute("TRUNCATE chunks RESTART IDENTITY;")
        c.commit()                                    # release lock immediately
        total = 0
        for f in files:
            cid = os.path.splitext(os.path.basename(f))[0]
            txt = open(f, encoding="utf-8", errors="ignore").read()
            cks = chunk_text(txt)
            if not cks:
                continue
            for i in range(0, len(cks), batch):
                part = cks[i:i+batch]
                vecs = emb.encode(part, normalize_embeddings=True,
                                  convert_to_numpy=True)
                rows = [(cid, t, _vec_literal(v)) for t, v in zip(part, vecs)]
                execute_values(cur,
                    "INSERT INTO chunks (case_id, text, embedding) VALUES %s",
                    rows, template="(%s, %s, %s::vector)")
                total += len(part)
            c.commit()                                # commit per case -> observable
            print(f"  {cid}: {len(cks)} chunks (total {total})", flush=True)
        c.close()
        print(f"[build] {len(files)} cases -> {total} chunks stored", flush=True)

    def _dense(self, cur, qvec, n, case_id):
        where = "WHERE case_id = %s" if case_id else ""
        params = [qvec] + ([case_id] if case_id else []) + [n]
        cur.execute(f"""
            SELECT id, case_id, text
            FROM chunks {where}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, params)
        return cur.fetchall()

    def _bm25(self, cur, query, n, case_id):
        extra = "AND case_id = %s" if case_id else ""
        params = [query] + ([case_id] if case_id else []) + [n]
        cur.execute(f"""
            SELECT id, case_id, text
            FROM chunks
            WHERE text @@@ %s {extra}
            ORDER BY paradedb.score(id) DESC
            LIMIT %s
        """, params)
        return cur.fetchall()

    def search(self, query, k=10, case_id=None):
        """Return [{case_id, text, score}] — hybrid RRF + cross-encoder rerank.
        case_id is None for global 'ask', or a case for per-case chat scope."""
        ckey = (query, k, case_id)
        if ckey in self._cache:
            return self._cache[ckey]
        qvec = _vec_literal(_embed().encode([query], normalize_embeddings=True,
                                            convert_to_numpy=True)[0])
        with self._conn() as c, c.cursor() as cur:
            dense = self._dense(cur, qvec, CAND, case_id)
            try:
                sparse = self._bm25(cur, query, CAND, case_id)
            except Exception as e:                # pg_search missing / API drift
                print(f"[warn] BM25 unavailable ({e}); dense-only", file=sys.stderr)
                sparse = []
        # RRF fuse on chunk id
        text_of, kk, score = {}, 60, {}
        for lst in (dense, sparse):
            for rank, (cid, case, text) in enumerate(lst):
                text_of[cid] = (case, text)
                score[cid] = score.get(cid, 0.0) + 1.0 / (kk + rank)
        fused = sorted(score, key=score.get, reverse=True)[:CAND]
        if not fused:
            self._cache[ckey] = []
            return []
        # cross-encoder rerank
        pairs = [(query, text_of[cid][1]) for cid in fused]
        rr = _rerank().predict(pairs)
        order = sorted(range(len(fused)), key=lambda i: rr[i], reverse=True)[:k]
        result = [{"case_id": text_of[fused[i]][0],
                   "text": text_of[fused[i]][1],
                   "score": float(rr[i])} for i in order]
        if len(self._cache) >= 512:          # bound: drop oldest
            self._cache.pop(next(iter(self._cache)))
        self._cache[ckey] = result
        return result


def _cli():
    eng = RetrievalEngine()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "init":
        eng.init_db()
    elif cmd == "build":
        eng.build(sys.argv[2])
    elif cmd == "search":
        case = sys.argv[3] if len(sys.argv) > 3 else None
        for r in eng.search(sys.argv[2], case_id=case):
            print(f"[{r['case_id']}] {r['score']:.2f}  {r['text'][:140]}...")
    else:
        print(__doc__)

if __name__ == "__main__":
    _cli()
