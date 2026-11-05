"""
Case metadata (cutover option 1) — title / judges / date / summary per case.

The old Qdrant app lazily extracted this via Groq into SQLite. Here we extract
via the LLM gateway and store it in Postgres so every case page works on the
new stack. Backfill is resumable (skips cases already done) and commits per case.

Table: case_meta(case_id PK, title, judges, date, summary)

CLI:
  python -m model.metadata init
  python -m model.metadata backfill <cleaned_texts_dir> [--force] [--llm | --no-llm]
  python -m model.metadata get <case_id>
"""
import os
import re
import sys
import json
from contextlib import closing

from model.retrieval import RetrievalEngine
from model import llm_gateway
from model import metadata_regex

SCHEMA = """
CREATE TABLE IF NOT EXISTS case_meta (
    case_id TEXT PRIMARY KEY,
    title   TEXT,
    judges  TEXT,
    date    TEXT,
    summary TEXT
);
"""

SYSTEM = (
    "You extract metadata from an Indian Supreme Court judgment. Return ONLY valid "
    "JSON with keys title, judges, date, summary. title = case name (X vs Y). "
    "judges = comma-separated judge names, no titles. "
    "date = the date THIS Supreme Court judgment was pronounced/delivered — it "
    "appears near the END of the judgment, after 'New Delhi' / the bench's "
    "signatures, or as the pronouncement date. Do NOT use the date of any "
    "lower-court order, FIR, notification, or impugned judgment referenced in the "
    "text. Format DD-MM-YYYY. "
    "summary = <=100 word summary of the issue and outcome. Use 'Not available' "
    "if a field cannot be found. No text outside the JSON."
)

_eng = RetrievalEngine()


def _parse(text):
    try:
        s, e = text.find("{"), text.rfind("}") + 1
        d = json.loads(text[s:e])
    except Exception:
        d = {}
    out = {}
    for k in ("title", "judges", "date", "summary"):
        v = d.get(k)
        if isinstance(v, list):
            v = ", ".join(map(str, v))
        out[k] = (str(v).strip() if v else "Not available")
    return out


def extract(text):
    """Extract metadata dict from judgment text via the LLM gateway."""
    lines = text.splitlines()
    head = "\n".join(lines[:120])          # title usually near the top
    tail = "\n".join(lines[-120:])         # judges/date near the end
    body = text[:4000]
    prompt = f"FIRST PAGE:\n{head}\n\nLAST PAGE:\n{tail}\n\nBODY SAMPLE:\n{body}"
    try:
        raw, _ = llm_gateway.generate(prompt, system=SYSTEM, temperature=0.2)
        return _parse(raw)
    except Exception as e:
        print(f"[warn] extract failed: {e}", file=sys.stderr)
        return {k: "Not available" for k in ("title", "judges", "date", "summary")}


def extract_regex(text):
    """LLM-free first pass (see model/metadata_regex.py)."""
    return metadata_regex.extract_regex(text)


def init_db():
    with closing(_eng._conn()) as c, c, c.cursor() as cur:
        cur.execute(SCHEMA)
    print("[init] case_meta ready")


def backfill(cleaned_dir, force=False, llm=None):
    """Regex first (free, offline); the LLM is an optional second pass.
    llm=None  -> use the LLM only for fields the regex left as "Not available", and only if a
                 provider key is configured.
    llm=True  -> ask the LLM for every case; its answers replace the regex ones.
    llm=False -> regex only."""
    import glob
    files = sorted(glob.glob(os.path.join(cleaned_dir, "*.txt")),
                   key=lambda p: os.path.basename(p))
    c = _eng._conn(); cur = c.cursor()
    if force:                                    # re-extract every case (updates in place)
        done = set()
    else:
        # only count a case done if extraction actually succeeded (title found)
        cur.execute("SELECT case_id FROM case_meta WHERE title <> 'Not available';")
        done = {r[0] for r in cur.fetchall()}
    todo = [f for f in files if os.path.splitext(os.path.basename(f))[0] not in done]
    use_llm = llm if llm is not None else bool(llm_gateway.configured_providers())
    print(f"[backfill] {len(done)} done, {len(todo)} to extract, llm={'on' if use_llm else 'off'}")
    for n, f in enumerate(todo, 1):
        cid = os.path.splitext(os.path.basename(f))[0]
        txt = open(f, encoding="utf-8", errors="ignore").read()
        m = extract_regex(txt)
        if use_llm and (llm or any(m[k] == "Not available" for k in m)):
            ai = extract(txt)
            for k in m:
                if ai[k] != "Not available" and (llm or m[k] == "Not available"):
                    m[k] = ai[k]
        cur.execute(
            "INSERT INTO case_meta (case_id, title, judges, date, summary) "
            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (case_id) DO UPDATE SET "
            "title=EXCLUDED.title, judges=EXCLUDED.judges, date=EXCLUDED.date, "
            "summary=EXCLUDED.summary",
            (cid, m["title"], m["judges"], m["date"], m["summary"]))
        c.commit()
        if n % 50 == 0:
            print(f"  {n}/{len(todo)} (last {cid}: {m['title'][:50]})", flush=True)
    c.close()
    print("[backfill] complete")


def find(case_id):
    """Metadata dict for a case, or None if the case is not in case_meta."""
    with closing(_eng._conn()) as c, c, c.cursor() as cur:
        cur.execute("SELECT case_id,title,judges,date,summary FROM case_meta WHERE case_id=%s",
                    (case_id,))
        r = cur.fetchone()
    if not r:
        return None
    return {"id": r[0], "title": r[1], "judges": r[2], "date": r[3], "summary": r[4]}


def get(case_id):
    """Like find(), but returns a placeholder card for unknown ids (used by search results)."""
    return find(case_id) or {"id": case_id, "title": f"Case {case_id}", "judges": "Not available",
                             "date": "Not available", "summary": "Not available"}


def list_cases(limit=20, offset=0):
    with closing(_eng._conn()) as c, c, c.cursor() as cur:
        cur.execute("SELECT case_id,title,judges,date,summary FROM case_meta "
                    "ORDER BY case_id LIMIT %s OFFSET %s", (limit, offset))
        rows = cur.fetchall()
        cur.execute("SELECT count(*) FROM case_meta;")
        total = cur.fetchone()[0]
    cases = [{"id": r[0], "title": r[1], "judges": r[2], "date": r[3], "summary": r[4]}
             for r in rows]
    return {"cases": cases, "total": total, "limit": limit, "offset": offset}


def _cli():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "init":     init_db()
    elif cmd == "backfill":
        llm = True if "--llm" in sys.argv else (False if "--no-llm" in sys.argv else None)
        backfill(sys.argv[2], force="--force" in sys.argv, llm=llm)
    elif cmd == "get":    print(get(sys.argv[2]))
    else:                 print(__doc__)

if __name__ == "__main__":
    _cli()
