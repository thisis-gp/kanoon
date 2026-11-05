"""
Citation mining: fills `citations` (outbound edges) and `case_refs` (what each case is called)
so that GET /cases/{id}/cited-by stops returning [].

Run from Backend/ (standalone, one pass over the cleaned texts, one file in memory at a time):

    python citations_mining.py supreme_court_cleaned_texts            # writes to Postgres
    python citations_mining.py supreme_court_cleaned_texts --dry-run  # counts only, no DB

Strategy (regex, best effort; see "Limits"):

1. Report citations. model.citations.extract_citations finds, and normalises to one canonical
   string, these formats:
     "2024 INSC 123"                 neutral citation
     "(2010) 5 SCC 123"              SCC, also "(2010) 5 SCC (Cri) 77"
     "2019 SCC OnLine SC 1234"       SCC OnLine
     "AIR 1995 SC 1234"              AIR, also "A.I.R. 1995 S.C. 1234"
     "[2020] 3 SCR 456"              SCR, also "(2020) 3 SCR 456", "2020 (3) SCR 456", "2020 3 SCR 456"
     "(2019) 3 SCALE 12"             SCALE
2. Case names. "X v. Y", "X vs. Y", "X versus Y" in the body are matched against the titles of
   the corpus (case_meta.title, or the regex fallback in model.metadata when the title is
   missing). Both parties are normalised (lower case, punctuation, "the/and/ors/anr/others/..."
   and anything after "through/represented" dropped). A mention counts only if the whole
   "left|right" key equals a title key, the key has >= 4 tokens, and the key belongs to exactly
   ONE case. Leading words captured by mistake ("Following State of Punjab v. ...") are
   handled by trying shorter suffixes/prefixes of each side. Name edges are stored as
   cited_ref = "CASE:<left>|<right>", ref_type = "name".
3. What a case is called (case_refs, many rows per case): every report citation found in the
   first HEADER_CHARS characters of the judgment (its own neutral/SCC/AIR cite, when printed
   there) plus its own title key "CASE:<left>|<right>". cited_by joins citations.cited_ref to
   case_refs.neutral_cite, so a name mention or a printed citation links two corpus cases.
   A case's own identifiers are never stored as outbound edges of that case.

Idempotent: each case is deleted and re-inserted in its own transaction, so re-running gives the
same rows and an interrupted run can simply be restarted. case_refs gets a composite primary
key (case_id, neutral_cite); an old single-column key is migrated automatically.

Limits (results are best effort, not a legal citator):
- Regexes miss citations that OCR damaged and misfire on text that merely looks like one.
- Header identifiers can belong to a lower-court judgment quoted at the top.
- Name matching needs a correct title. Short, common or ambiguous titles are skipped on
  purpose (precision over recall). Judgments cite most cases by report citation, which links
  only if the cited case prints that citation in its own header; expect partial coverage.
- Treat counts printed at the end as the quality signal; spot check a few cases by hand.
"""
import os
import re
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model.citations import SCHEMA, extract_citations  # noqa: E402

HEADER_CHARS = 6000          # where a judgment prints its own citation / title
MIN_KEY_TOKENS = 4           # shorter name keys are too generic to trust
NAME_PREFIX = "CASE:"
NAME_TYPE = "name"

_STOP = {"the", "and", "ors", "or", "anr", "others", "another", "etc", "vs", "v", "versus", "of"}
_CUT = {"through", "thr", "represented", "rep"}
_SPLIT_TITLE = re.compile(r"\s+(?:vs\.?|v\.?|versus)\s+", re.I)
_WORD = r"[A-Z][\w.&'\-]*"
_PARTY = rf"{_WORD}(?:\s+(?:of|and|the|for|in|&|ors\.?|anr\.?|{_WORD})){{0,8}}"
_NAME_RX = re.compile(rf"({_PARTY}),?\s+(?:v\.?|vs\.?|versus)\s+({_PARTY})")


def party_tokens(text):
    """Normalise one side of a case name to a tuple of tokens."""
    out = []
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        if tok in _CUT:
            break
        if tok not in _STOP:
            out.append(tok)
    return tuple(out)


def _key(left, right):
    return f"{' '.join(left)}|{' '.join(right)}"


def title_key(title):
    """'State of X vs Y Ors' -> 'state x|y', or None if it is not a usable 'A vs B' title."""
    if not title or title.strip().lower() == "not available":
        return None
    parts = _SPLIT_TITLE.split(title.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    left, right = party_tokens(parts[0]), party_tokens(parts[1])
    if not left or not right or len(left) + len(right) < MIN_KEY_TOKENS:
        return None
    return _key(left, right)


def build_name_index(titles):
    """titles: {case_id: title}. Returns ({key: case_id} for unambiguous keys, n_ambiguous)."""
    owners = {}
    for cid, title in titles.items():
        k = title_key(title)
        if k:
            owners.setdefault(k, set()).add(cid)
    index = {k: next(iter(v)) for k, v in owners.items() if len(v) == 1}
    return index, sum(1 for v in owners.values() if len(v) > 1)


def name_mentions(text, index):
    """Set of title keys (present in `index`) mentioned in `text` as 'X v. Y'."""
    if not index:
        return set()
    flat = re.sub(r"\s+", " ", text)
    found = set()
    for m in _NAME_RX.finditer(flat):
        lw, rw = m.group(1).split(), m.group(2).split()
        hit = None
        for i in range(len(lw)):                          # longest left suffix first
            lt = party_tokens(" ".join(lw[i:]))
            if not lt:
                continue
            for j in range(len(rw), 0, -1):               # longest right prefix first
                rt = party_tokens(" ".join(rw[:j]))
                if rt and _key(lt, rt) in index:
                    hit = _key(lt, rt)
                    break
            if hit:
                break
        if hit:
            found.add(hit)
    return found


def identities(header, title, index):
    """Identifiers this case is known by: citations printed in its header + its own title key."""
    ids = {ref for _, ref in extract_citations(header)}
    k = title_key(title)
    if k and k in index:
        ids.add(NAME_PREFIX + k)
    return ids


def outbound_edges(text, own_ids, index):
    """[(ref_type, ref)] this judgment cites, excluding the case's own identifiers."""
    edges = {ref: t for t, ref in extract_citations(text)}
    for k in name_mentions(text, index):
        edges.setdefault(NAME_PREFIX + k, NAME_TYPE)
    return [(t, r) for r, t in sorted(edges.items()) if r not in own_ids]


def _read(path, limit=None):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read(limit) if limit else f.read()


def _case_files(cleaned_dir):
    files = sorted(glob.glob(os.path.join(cleaned_dir, "*.txt")), key=os.path.basename)
    return [(os.path.splitext(os.path.basename(p))[0], p) for p in files]


def mine(cleaned_dir, titles, sink):
    """Two streaming passes. titles: {case_id: title or None}. Returns a stats dict."""
    from model.metadata import extract_regex
    cases = _case_files(cleaned_dir)
    resolved_titles, headers_ids = {}, {}
    for cid, path in cases:                                   # pass 1: headers only
        head = _read(path, HEADER_CHARS)
        title = titles.get(cid)
        if not title or title.strip().lower() == "not available":
            title = extract_regex(head)["title"]
        resolved_titles[cid] = title
        headers_ids[cid] = head
    index, ambiguous = build_name_index(resolved_titles)
    own = {cid: identities(h, resolved_titles[cid], index) for cid, h in headers_ids.items()}
    headers_ids.clear()
    all_ids = set().union(*own.values()) if own else set()

    stats = {"cases": len(cases), "cases_with_own_id": sum(1 for v in own.values() if v),
             "own_ids": len(all_ids), "name_keys": len(index), "ambiguous_name_keys": ambiguous,
             "edges": 0, "edges_by_type": {}, "resolved_edges": 0, "cases_citing_corpus": 0}
    for cid, path in cases:                                   # pass 2: full text, one file at a time
        edges = outbound_edges(_read(path), own[cid], index)
        sink.write_case(cid, edges, sorted(own[cid]))
        stats["edges"] += len(edges)
        hits = 0
        for t, r in edges:
            stats["edges_by_type"][t] = stats["edges_by_type"].get(t, 0) + 1
            if r in all_ids:
                hits += 1
        stats["resolved_edges"] += hits
        stats["cases_citing_corpus"] += 1 if hits else 0
    return stats


class MemorySink:
    """Collects rows in memory (tests, --dry-run)."""
    def __init__(self):
        self.edges, self.refs = {}, {}

    def write_case(self, cid, edges, own_ids):
        self.edges[cid], self.refs[cid] = list(edges), list(own_ids)


MIGRATE_CASE_REFS = """
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint
             WHERE conrelid = 'case_refs'::regclass AND contype = 'p' AND array_length(conkey, 1) = 1) THEN
    ALTER TABLE case_refs DROP CONSTRAINT case_refs_pkey;
    DELETE FROM case_refs WHERE neutral_cite IS NULL;
    ALTER TABLE case_refs ALTER COLUMN neutral_cite SET NOT NULL;
    ALTER TABLE case_refs ADD PRIMARY KEY (case_id, neutral_cite);
  END IF;
END $$;
"""


class PgSink:
    """Writes per case in its own transaction: delete the case's rows, insert the fresh ones."""
    def __init__(self, conn):
        self.conn = conn
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute(MIGRATE_CASE_REFS)
        conn.commit()

    def write_case(self, cid, edges, own_ids):
        from psycopg2.extras import execute_values
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM citations WHERE from_case = %s", (cid,))
            cur.execute("DELETE FROM case_refs WHERE case_id = %s", (cid,))
            if edges:
                execute_values(cur, "INSERT INTO citations (from_case, cited_ref, ref_type) VALUES %s "
                                    "ON CONFLICT DO NOTHING", [(cid, r, t) for t, r in edges])
            if own_ids:
                execute_values(cur, "INSERT INTO case_refs (case_id, neutral_cite) VALUES %s "
                                    "ON CONFLICT DO NOTHING", [(cid, r) for r in own_ids])
        self.conn.commit()


def _db_titles(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT case_id, title FROM case_meta")
            return dict(cur.fetchall())
    except Exception:
        conn.rollback()
        return {}


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    dry = "--dry-run" in argv
    if len(args) != 1 or not os.path.isdir(args[0]):
        print(__doc__)
        return 2
    if dry:
        sink, titles, conn = MemorySink(), {}, None
    else:
        from model.retrieval import RetrievalEngine
        conn = RetrievalEngine()._conn()
        sink, titles = PgSink(conn), _db_titles(conn)
    stats = mine(args[0], titles, sink)
    if conn:
        conn.close()
    print(("[dry-run] " if dry else "[mined] ") + ", ".join(
        f"{k}={v}" for k, v in stats.items() if k != "edges_by_type"))
    print("[edges by type] " + ", ".join(f"{k}={v}" for k, v in sorted(stats["edges_by_type"].items())))
    print("Best effort: regex citation matching misses and misfires; spot check before relying on cited-by.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
