"""
Slice-3 self-check: citation extraction + graph queries.

- extract_citations is pure (no DB) — always runs.
- Graph query tests need ParadeDB with a built citation graph; auto-skip otherwise.

Run:  python test/test_citations.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.citations import extract_citations, extract_self_ref, CitationGraph


def test_extract():
    text = ("Following AIR 1973 SC 1461 and (2020) 5 SCC 1, and the neutral "
            "citation 2024 INSC 123, the court held...")
    refs = {r for _, r in extract_citations(text)}
    assert "AIR 1973 SC 1461" in refs, refs
    assert "(2020) 5 SCC 1" in refs, refs
    assert "2024 INSC 123" in refs, refs
    assert extract_self_ref("2022 INSC 99\nIN THE SUPREME COURT") == "2022 INSC 99"
    print(f"  extract: {len(refs)} refs incl neutral/scc/air  OK")


def test_graph_queries():
    import psycopg2
    dsn = os.getenv("DATABASE_URL", "postgresql://ailse:ailse@localhost:5432/ailse")
    try:
        c = psycopg2.connect(dsn); cur = c.cursor()
        cur.execute("SELECT count(*) FROM citations;"); edges = cur.fetchone()[0]; c.close()
    except Exception as e:
        print(f"  graph: SKIPPED ({e})"); return
    if not edges:
        print("  graph: SKIPPED (no edges — run citations build)"); return

    g = CitationGraph()
    with g.eng._conn() as c, c.cursor() as cur:
        cur.execute("SELECT from_case FROM citations LIMIT 1;")
        case = cur.fetchone()[0]
    refs = g.cites(case)
    assert refs and all("ref" in r and "type" in r for r in refs), refs
    print(f"  graph: {edges} edges; cites({case}) -> {len(refs)} refs  OK")
    print(f"  graph: cited_by({case}) -> {g.cited_by(case)} "
          f"(empty until self-refs mined)")


if __name__ == "__main__":
    print("test_citations:")
    test_extract()
    test_graph_queries()
    print("done.")
