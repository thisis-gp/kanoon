"""Citation extraction formats and the mining script, on small synthetic texts (no DB)."""
import os

import pytest

import citations_mining as cm
from model.citations import extract_citations, extract_self_ref
from conftest import FakeEngine


def refs(text):
    return {r for _, r in extract_citations(text)}


def test_all_report_formats_are_found_and_canonical():
    text = ("AIR 1995 SC 1234; A.I.R. 1973 S.C. 1461; (2010) 5 SCC 123; (2010) 5 SCC (Cri) 77; "
            "2019 SCC OnLine SC 1234; [2020] 3 SCR 456; (2020) 3 SCR 456; 1975 (3) SCR 9; "
            "1975 3 SCR 9; 2024 INSC 123; (2019) 4 SCALE 55")
    assert refs(text) == {
        "AIR 1995 SC 1234", "AIR 1973 SC 1461", "(2010) 5 SCC 123", "(2010) 5 SCC (CRI) 77",
        "2019 SCC ONLINE SC 1234", "[2020] 3 SCR 456", "[1975] 3 SCR 9", "2024 INSC 123",
        "(2019) 4 SCALE 55"}


def test_types_are_labelled():
    types = dict((r, t) for t, r in extract_citations("AIR 1995 SC 1234 and (2010) 5 SCC 123 and 2024 INSC 9"))
    assert types == {"AIR 1995 SC 1234": "air", "(2010) 5 SCC 123": "scc", "2024 INSC 9": "neutral"}


def test_no_false_positives_on_plain_numbers():
    assert refs("In 1995 the court sat 12 times; Section 5 SCC; page 1234 of the record; AIR 1800 SC 5.") == set()


def test_whitespace_and_case_variants_collapse():
    assert refs("air   1995   sc   1234") == {"AIR 1995 SC 1234"}
    assert refs("( 2010 )  5  scc  123") == {"(2010) 5 SCC 123"}


def test_self_ref_is_neutral_cite_in_header_only():
    assert extract_self_ref("REPORTABLE\n2023 INSC 456\nIN THE SUPREME COURT") == "2023 INSC 456"
    assert extract_self_ref("x" * 2000 + " 2023 INSC 456") is None


# ---- name matching ----

def test_title_key_rules():
    assert cm.title_key("Maneka Gandhi vs Union of India") == "maneka gandhi|union india"
    assert cm.title_key("State Of X vs Y Ors") is None                 # 3 tokens: too generic
    assert cm.title_key("State of Punjab vs Ram Singh and Others") == "state punjab|ram singh"
    assert cm.title_key("Not available") is None
    assert cm.title_key("Single Party Only") is None


def test_ambiguous_titles_are_not_indexed():
    idx, amb = cm.build_name_index({"1": "Ram Kumar vs State of Bihar", "2": "RAM KUMAR V. STATE OF BIHAR",
                                    "3": "Maneka Gandhi vs Union of India"})
    assert list(idx.values()) == ["3"] and amb == 1


INDEX, _ = cm.build_name_index({"10": "Maneka Gandhi vs Union of India",
                                "11": "Kesavananda Bharati vs State of Kerala",
                                "12": "State of Punjab vs Ram Singh"})


def test_name_mentions_variants():
    for text in ("as held in Maneka Gandhi v. Union of India (1978) 1 SCC 248, the court",
                 "see MANEKA GANDHI vs. UNION OF INDIA & ORS.",
                 "reliance on Maneka  Gandhi\nversus Union of India is misplaced"):
        assert cm.name_mentions(text, INDEX) == {"maneka gandhi|union india"}, text


def test_leading_words_are_trimmed():
    assert cm.name_mentions("Following the decision in State of Punjab v. Ram Singh it was held",
                            INDEX) == {"state punjab|ram singh"}
    assert cm.name_mentions("In Kesavananda Bharati v. State of Kerala, (1973) 4 SCC 225", INDEX) == {
        "kesavananda bharati|state kerala"}


def test_unrelated_names_do_not_match():
    assert cm.name_mentions("Ram Singh v. State of Punjab is a different case; X v. Y too.", INDEX) == set()
    assert cm.name_mentions("anything", {}) == set()


# ---- mining over a synthetic corpus ----

PAD = "filler words. " * 500            # pushes the body past the header window


@pytest.fixture
def corpus(tmp_path):
    files = {
        "10": ("IN THE SUPREME COURT OF INDIA\nMANEKA GANDHI ... PETITIONER\nVERSUS\nUNION OF INDIA ... RESPONDENT\n"
               "2024 INSC 77\n1. The passport was impounded.\n" + PAD + "We follow AIR 1973 SC 1461.\n"),
        "11": ("KESAVANANDA BHARATI ... PETITIONER\nVERSUS\nSTATE OF KERALA ... RESPONDENT\n"
               "(1973) 4 SCC 225\nBody text.\n"),
        "12": ("STATE OF PUNJAB ... APPELLANT\nVERSUS\nRAM SINGH ... RESPONDENT\n" + PAD +
               "Relying on Maneka Gandhi v. Union of India and on (1973) 4 SCC 225 and 2024 INSC 77 "
               "and Kesavananda Bharati vs. State of Kerala. Also 2024 INSC 77 again.\n"),
    }
    for cid, text in files.items():
        (tmp_path / f"{cid}.txt").write_text(text, encoding="utf-8")
    return str(tmp_path)


def test_mine_builds_edges_and_identities(corpus):
    sink = cm.MemorySink()
    stats = cm.mine(corpus, {}, sink)                   # titles come from the regex fallback
    assert sink.refs["10"] == ["2024 INSC 77", "CASE:maneka gandhi|union india"]
    assert "(1973) 4 SCC 225" in sink.refs["11"]
    assert set(sink.edges["12"]) == {
        ("name", "CASE:maneka gandhi|union india"), ("name", "CASE:kesavananda bharati|state kerala"),
        ("scc", "(1973) 4 SCC 225"), ("neutral", "2024 INSC 77")}
    assert ("air", "AIR 1973 SC 1461") in sink.edges["10"]
    assert all(r not in sink.refs["10"] for _, r in sink.edges["10"])     # no self edges
    assert stats["cases"] == 3 and stats["resolved_edges"] == 4 and stats["cases_citing_corpus"] == 1
    assert stats["edges_by_type"]["name"] == 2


def test_mine_is_deterministic_and_idempotent(corpus):
    a, b = cm.MemorySink(), cm.MemorySink()
    cm.mine(corpus, {}, a)
    cm.mine(corpus, {}, b)
    assert (a.edges, a.refs) == (b.edges, b.refs)


def test_db_titles_take_precedence_over_regex(corpus):
    sink = cm.MemorySink()
    cm.mine(corpus, {"12": "Zed Alpha vs Beta Gamma Delta"}, sink)
    assert "CASE:zed alpha|beta gamma delta" in sink.refs["12"]


class _Cur:
    def __init__(self, log):
        self.log = log

    def execute(self, sql, params=None):
        self.log.append((" ".join(sql.split())[:40], params))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def __init__(self):
        self.log, self.commits = [], 0

    def cursor(self):
        return _Cur(self.log)

    def commit(self):
        self.commits += 1


def test_pg_sink_replaces_rows_per_case(monkeypatch):
    import psycopg2.extras as extras
    inserted = []
    monkeypatch.setattr(extras, "execute_values", lambda cur, sql, rows: inserted.append((sql[:30], rows)))
    conn = _Conn()
    sink = cm.PgSink(conn)
    sink.write_case("12", [("scc", "(1973) 4 SCC 225")], ["2024 INSC 5"])
    sink.write_case("12", [("scc", "(1973) 4 SCC 225")], ["2024 INSC 5"])
    deletes = [p for s, p in conn.log if s.startswith("DELETE")]
    assert deletes == [("12",)] * 4                          # citations + case_refs, twice
    assert inserted[0][1] == [("12", "(1973) 4 SCC 225", "scc")] and inserted == inserted[:2] + inserted[2:]
    assert conn.commits == 3                                 # schema + one per case
    assert "PRIMARY KEY (case_id, neutral_cite)" in cm.SCHEMA


def test_main_dry_run_prints_counts(corpus, capsys):
    assert cm.main([corpus, "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "cases=3" in out and "Best effort" in out
    assert cm.main(["/no/such/dir"]) == 2
