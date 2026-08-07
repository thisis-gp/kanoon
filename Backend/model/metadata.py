"""
Case metadata (cutover option 1) — title / judges / date / summary per case.

The old Qdrant app lazily extracted this via Groq into SQLite. Here we extract
via the LLM gateway and store it in Postgres so every case page works on the
new stack. Backfill is resumable (skips cases already done) and commits per case.

Table: case_meta(case_id PK, title, judges, date, summary)

CLI:
  python -m model.metadata init
  python -m model.metadata backfill <cleaned_texts_dir>
  python -m model.metadata get <case_id>
"""
import os
import re
import sys
import json

from model.retrieval import RetrievalEngine
from model import llm_gateway

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


_VS = re.compile(r"^\s*(?:VERSUS|V\s*/\s*S|Vs\.?)\s*$", re.I)
_MONTHS = ("January|February|March|April|May|June|July|August|September|October|"
           "November|December")

def extract_regex(text):
    """LLM-free metadata extraction from an Indian SC judgment (heuristic)."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    top = lines[:60]
    # title: petitioner line ... VERSUS ... respondent line
    title = "Not available"
    for i, l in enumerate(top):
        if _VS.match(l):
            pet = top[i - 1] if i > 0 else ""
            resp = top[i + 1] if i + 1 < len(top) else ""
            pet = re.sub(r"\b(APPELLANT|PETITIONER)\S*\b.*", "", pet, flags=re.I).strip(" .-")
            resp = re.sub(r"\b(RESPONDENT|ORS?|ANR|ETC)\b.*", "", resp, flags=re.I).strip(" .-&,")
            if pet and resp:
                title = f"{pet.title()} vs {resp.title()}"
            break
    # judges: signature lines like "ABHAY S. OKA, J."
    judges = []
    for l in lines[:60] + lines[-60:]:
        m = re.match(r"^([A-Z][A-Za-z.\s]{2,40}?),?\s+J\.?$", l)
        if m and "SUPREME" not in m.group(1).upper():
            judges.append(re.sub(r"\s+", " ", m.group(1)).strip().title())
    judges = ", ".join(dict.fromkeys(judges)) or "Not available"
    # date: near the end
    tail = text[-1800:]
    dm = (re.search(rf"(\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})[,]?\s+\d{{4}})", tail, re.I)
          or re.search(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b", tail))
    date = re.sub(r"\s+", " ", dm.group(1)) if dm else "Not available"
    # summary: first numbered paragraph
    sm = re.search(r"(?:^|\n)\s*1\.\s+(.{60,700}?)(?:\n\s*2\.|\Z)", text, re.S)
    summary = re.sub(r"\s+", " ", sm.group(1)).strip()[:400] if sm else "Not available"
    out = {"title": title[:200], "judges": judges, "date": date, "summary": summary}
    # strip U+FFFD encoding artifacts and tidy
    return {k: re.sub(r"\s+", " ", v.replace("�", "").replace("( vs", "vs")).strip(" -,")
            or "Not available" for k, v in out.items()}


def init_db():
    with _eng._conn() as c, c.cursor() as cur:
        cur.execute(SCHEMA)
    print("[init] case_meta ready")


def backfill(cleaned_dir, force=False):
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
    print(f"[backfill] {len(done)} done, {len(todo)} to extract")
    for n, f in enumerate(todo, 1):
        cid = os.path.splitext(os.path.basename(f))[0]
        txt = open(f, encoding="utf-8", errors="ignore").read()
        m = extract(txt)                # LLM — accurate title/judges/date/summary
        if any(m[k] == "Not available" for k in m):   # fill misses from regex
            rx = extract_regex(txt)
            for k in m:
                if m[k] == "Not available":
                    m[k] = rx[k]
        cur.execute(
            "INSERT INTO case_meta (case_id, title, judges, date, summary) "
            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (case_id) DO UPDATE SET "
            "title=EXCLUDED.title, judges=EXCLUDED.judges, date=EXCLUDED.date, "
            "summary=EXCLUDED.summary",
            (cid, m["title"], m["judges"], m["date"], m["summary"]))
        c.commit()
        if n % 10 == 0:
            print(f"  {n}/{len(todo)} (last {cid}: {m['title'][:50]})", flush=True)
    c.close()
    print(f"[backfill] complete")


def get(case_id):
    with _eng._conn() as c, c.cursor() as cur:
        cur.execute("SELECT case_id,title,judges,date,summary FROM case_meta WHERE case_id=%s",
                    (case_id,))
        r = cur.fetchone()
    if not r:
        return {"id": case_id, "title": f"Case {case_id}", "judges": "Not available",
                "date": "Not available", "summary": "Not available"}
    return {"id": r[0], "title": r[1], "judges": r[2], "date": r[3], "summary": r[4]}


def list_cases(limit=20, offset=0):
    with _eng._conn() as c, c.cursor() as cur:
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
    elif cmd == "backfill": backfill(sys.argv[2], force="--force" in sys.argv)
    elif cmd == "get":    print(get(sys.argv[2]))
    else:                 print(__doc__)

if __name__ == "__main__":
    _cli()
