"""
Perplexity-style grounded answering (Slice 2).

Grounding layers:
  1. Grounded prompt + abstention — answer ONLY from retrieved sources,
     else say the info isn't in the sources.
  2. Enforced inline citations — sources numbered [1..n]; the model must cite
     [n]; each [n] maps back to a case_id (+ chunk) the user can click through.

Scope: answer(question) searches ALL cases; answer(question, case_id=X)
restricts to one judgment (per-case chat).

CLI:  python ask.py "your question" [case_id]
"""
import json
import re
import sys

from model.retrieval import RetrievalEngine
from model import llm_gateway

_engine = None
def _eng():
    global _engine
    if _engine is None:
        _engine = RetrievalEngine()
    return _engine

SYSTEM = (
    "You are Kanoon, an assistant for Indian Supreme Court case law. "
    "Answer ONLY using the numbered SOURCES provided. After each claim, cite the "
    "source(s) you used as [n]. If the sources do not contain the answer, reply "
    "exactly: 'Not available in the sources.' Do not use outside knowledge. "
    "Be concise and use clear legal language."
)

def _build_prompt(question, hits):
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(f"[{i}] (case {h['case_id']}) {h['text']}")
    sources = "\n\n".join(blocks)
    return f"SOURCES:\n{sources}\n\nQUESTION: {question}\n\nANSWER (cite [n]):"

_answer_cache = {}   # cache_key -> result; bounded L1 in front of Postgres
_cache_ready = False

def _ensure_cache():
    """Create the answer_cache table once per process. Best-effort."""
    global _cache_ready
    if _cache_ready:
        return
    conn = _eng()._conn()
    with conn, conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS answer_cache ("
                    "cache_key TEXT PRIMARY KEY, response JSONB NOT NULL, "
                    "created_at TIMESTAMPTZ DEFAULT now())")
    _cache_ready = True

def _cache_get(cache_key):
    try:
        _ensure_cache()
        conn = _eng()._conn()
        with conn, conn.cursor() as cur:
            cur.execute("SELECT response FROM answer_cache WHERE cache_key=%s", (cache_key,))
            row = cur.fetchone()
            return row[0] if row else None   # JSONB -> dict
    except Exception:
        return None   # cache is never allowed to break /ask

def _cache_put(cache_key, res):
    try:
        _ensure_cache()
        conn = _eng()._conn()
        with conn, conn.cursor() as cur:
            cur.execute("INSERT INTO answer_cache (cache_key, response) "
                        "VALUES (%s, %s::jsonb) ON CONFLICT DO NOTHING",
                        (cache_key, json.dumps(res)))
    except Exception:
        pass

def answer(question, case_id=None, k=6):
    """Return {answer, provider, sources, cited}. sources = [{n, case_id, text}].
    Cached in Postgres (persists across restarts): repeat questions skip
    retrieval + the LLM call, with a bounded in-memory L1 in front."""
    cache_key = json.dumps([question.strip().lower(), case_id, k])
    if cache_key in _answer_cache:
        return _answer_cache[cache_key]
    hit = _cache_get(cache_key)
    if hit is not None:
        _answer_cache[cache_key] = hit
        return hit
    hits = _eng().search(question, k=k, case_id=case_id)
    if not hits:
        res = {"answer": "Not available in the sources.", "provider": None,
               "sources": [], "cited": []}
    else:
        prompt = _build_prompt(question, hits)
        text, provider = llm_gateway.generate(prompt, system=SYSTEM)
        cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text)
                        if 1 <= int(n) <= len(hits)})
        sources = [{"n": i + 1, "case_id": h["case_id"], "text": h["text"]}
                   for i, h in enumerate(hits)]
        res = {"answer": text, "provider": provider, "sources": sources, "cited": cited}
    _cache_put(cache_key, res)
    if len(_answer_cache) >= 256:          # bound: drop oldest
        _answer_cache.pop(next(iter(_answer_cache)))
    _answer_cache[cache_key] = res
    return res


if __name__ == "__main__":
    q = sys.argv[1]
    case = sys.argv[2] if len(sys.argv) > 2 else None
    r = answer(q, case_id=case)
    print(f"\n[{r['provider']}] {r['answer']}\n")
    print("Sources cited:", r["cited"])
    for s in r["sources"]:
        mark = "*" if s["n"] in r["cited"] else " "
        print(f" {mark}[{s['n']}] case {s['case_id']}: {s['text'][:90]}...")
