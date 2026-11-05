"""Needs Postgres (any, pg_search not required). Run with RUN_INTEGRATION=1 and DATABASE_URL set to a
THROWAWAY database: this test drops and recreates the citations, case_refs and case_meta tables."""
import citations_mining as cm
from test_citations_mining import corpus  # noqa: F401  (fixture)


def test_pg_mining_and_cited_by(corpus):
    from model.citations import CitationGraph
    from model.retrieval import RetrievalEngine
    eng = RetrievalEngine()
    with eng._conn() as c, c.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS citations, case_refs, case_meta")
        # old production shape: single-column primary key
        cur.execute("CREATE TABLE case_refs (case_id TEXT PRIMARY KEY, neutral_cite TEXT)")
        cur.execute("CREATE TABLE case_meta (case_id TEXT PRIMARY KEY, title TEXT, judges TEXT, date TEXT, summary TEXT)")
        cur.execute("INSERT INTO case_meta VALUES ('10','Maneka Gandhi vs Union of India','x','x','x'),"
                    "('11','Not available','x','x','x'),('12','State of Punjab vs Ram Singh','x','x','x')")
    for _ in range(2):                                    # second run proves idempotence
        conn = eng._conn()
        stats = cm.mine(corpus, cm._db_titles(conn), cm.PgSink(conn))
        conn.close()
    with eng._conn() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM citations")
        n_edges = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM case_refs")
        n_refs = cur.fetchone()[0]
    assert n_edges == stats["edges"] and n_refs == 5
    g = CitationGraph()
    assert g.cited_by("10") == ["12"]
    assert g.cited_by("11") == ["12"]
    assert g.cited_by("12") == []
    assert {"neutral", "scc", "name"} <= {r["type"] for r in g.cites("12")}
    print(f"\ningest ok: {stats}")
