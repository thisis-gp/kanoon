"""
Citation graph (Slice 3) — the legal moat.

Extracts references one judgment makes to other cases (Indian citation formats)
and stores them as edges in Postgres. Intra-corpus "cited-by" resolves when we
know each case's own neutral citation (mined from the PDF via markitdown).

HONEST SCOPE: regex citation extraction is best-effort/proxy — it will miss and
misfire (party-name citations, OCR noise). Outbound "cites" is reliable;
intra-corpus "cited-by" is only as complete as the self-citation mining.

Tables:
  citations(from_case, cited_ref, ref_type)   -- outbound references
  case_refs(case_id PK, neutral_cite)         -- each case's own neutral cite

CLI:
  python citations.py init
  python citations.py build <cleaned_texts_dir>
  python citations.py self-refs <pdf_dir>        # markitdown self-id mine (slow)
  python citations.py cites <case_id>
  python citations.py cited-by <case_id>
"""
import os
import re
import sys

from model.retrieval import RetrievalEngine  # reuse DSN + _conn

SCHEMA = """
CREATE TABLE IF NOT EXISTS citations (
    from_case TEXT NOT NULL,
    cited_ref TEXT NOT NULL,
    ref_type  TEXT,
    UNIQUE (from_case, cited_ref)
);
CREATE INDEX IF NOT EXISTS citations_from_idx ON citations (from_case);
CREATE INDEX IF NOT EXISTS citations_ref_idx  ON citations (cited_ref);
CREATE TABLE IF NOT EXISTS case_refs (
    case_id      TEXT PRIMARY KEY,
    neutral_cite TEXT
);
CREATE INDEX IF NOT EXISTS case_refs_neutral_idx ON case_refs (neutral_cite);
"""

# Indian Supreme Court citation formats
PATTERNS = [
    ("neutral", re.compile(r"\b(?:19|20)\d{2}\s+INSC\s+\d+\b", re.I)),
    ("scc",     re.compile(r"\(\s*(?:19|20)\d{2}\s*\)\s*\d+\s+SCC\s+\d+", re.I)),
    ("air",     re.compile(r"\bAIR\s+(?:19|20)\d{2}\s+SC\s+\d+", re.I)),
    ("scale",   re.compile(r"\(\s*(?:19|20)\d{2}\s*\)\s*\d+\s+SCALE\s+\d+", re.I)),
    ("scr",     re.compile(r"\b(?:19|20)\d{2}\s+\d+\s+SCR\s+\d+", re.I)),
]

def _norm(s):
    return re.sub(r"\s+", " ", s).strip().upper()

def extract_citations(text):
    """Return list of (ref_type, normalized_ref), de-duplicated."""
    found = {}
    for rtype, rx in PATTERNS:
        for m in rx.finditer(text):
            found[_norm(m.group(0))] = rtype
    return [(t, r) for r, t in found.items()]

def extract_self_ref(text):
    """Best-effort: the case's OWN neutral citation (usually top of the judgment)."""
    m = PATTERNS[0][1].search(text[:1500])
    return _norm(m.group(0)) if m else None


class CitationGraph:
    def __init__(self):
        self.eng = RetrievalEngine()

    def init_db(self):
        with self.eng._conn() as c, c.cursor() as cur:
            cur.execute(SCHEMA)
        print("[init] citation tables ready")

    def build(self, cases_dir):
        import glob
        from psycopg2.extras import execute_values
        files = sorted(glob.glob(os.path.join(cases_dir, "*.txt")))
        c = self.eng._conn(); cur = c.cursor()
        cur.execute("TRUNCATE citations;"); c.commit()
        total = 0
        for f in files:
            cid = os.path.splitext(os.path.basename(f))[0]
            txt = open(f, encoding="utf-8", errors="ignore").read()
            rows = [(cid, r, t) for t, r in extract_citations(txt)]
            if rows:
                execute_values(cur,
                    "INSERT INTO citations (from_case, cited_ref, ref_type) VALUES %s "
                    "ON CONFLICT DO NOTHING", rows)
                total += len(rows)
            self_ref = extract_self_ref(txt)
            if self_ref:
                cur.execute("INSERT INTO case_refs (case_id, neutral_cite) VALUES (%s,%s) "
                            "ON CONFLICT (case_id) DO UPDATE SET neutral_cite=EXCLUDED.neutral_cite",
                            (cid, self_ref))
            c.commit()
        c.close()
        print(f"[build] {len(files)} cases -> {total} citation edges")

    def self_refs(self, pdf_dir):
        """Mine each case's own neutral citation from its PDF via markitdown."""
        import glob, subprocess
        files = sorted(glob.glob(os.path.join(pdf_dir, "*.pdf")))
        c = self.eng._conn(); cur = c.cursor(); n = 0
        for f in files:
            cid = os.path.splitext(os.path.basename(f))[0]
            try:
                out = subprocess.run([sys.executable, "-m", "markitdown", f],
                                     capture_output=True, text=True, timeout=60).stdout
            except Exception:
                continue
            ref = extract_self_ref(out)
            if ref:
                cur.execute("INSERT INTO case_refs (case_id, neutral_cite) VALUES (%s,%s) "
                            "ON CONFLICT (case_id) DO UPDATE SET neutral_cite=EXCLUDED.neutral_cite",
                            (cid, ref)); c.commit(); n += 1
        c.close()
        print(f"[self-refs] mined neutral cite for {n}/{len(files)} cases")

    def cites(self, case_id):
        with self.eng._conn() as c, c.cursor() as cur:
            cur.execute("SELECT cited_ref, ref_type FROM citations WHERE from_case=%s "
                        "ORDER BY ref_type", (case_id,))
            return [{"ref": r, "type": t} for r, t in cur.fetchall()]

    def cited_by(self, case_id):
        """Intra-corpus: other cases whose text cites THIS case's neutral cite."""
        with self.eng._conn() as c, c.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ct.from_case
                FROM citations ct
                JOIN case_refs cr ON cr.neutral_cite = ct.cited_ref
                WHERE cr.case_id = %s AND ct.from_case <> %s
            """, (case_id, case_id))
            return [r[0] for r in cur.fetchall()]


def _cli():
    g = CitationGraph()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "init":       g.init_db()
    elif cmd == "build":    g.build(sys.argv[2])
    elif cmd == "self-refs": g.self_refs(sys.argv[2])
    elif cmd == "cites":    print(g.cites(sys.argv[2]))
    elif cmd == "cited-by": print(g.cited_by(sys.argv[2]))
    else:                   print(__doc__)

if __name__ == "__main__":
    _cli()
