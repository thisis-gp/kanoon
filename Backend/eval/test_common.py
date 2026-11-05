"""Run: python test_common.py"""
from common import case_ranking, gold_rank, per_query_scores, bootstrap_ci, load_queries


def test_ranking_and_metrics():
    rows = [(1, "a", ""), (2, "a", ""), (3, "b", ""), (4, "c", "")]
    r = case_ranking(rows)
    assert r == ["a", "b", "c"]
    assert gold_rank(r, "b") == 2 and gold_rank(r, "z") is None
    assert per_query_scores(2) == {"top1": 0.0, "top5": 1.0, "rr10": 0.5}
    assert per_query_scores(None)["rr10"] == 0.0
    assert per_query_scores(11)["rr10"] == 0.0


def test_bootstrap():
    ci = bootstrap_ci([1.0] * 50 + [0.0] * 50)
    assert abs(ci["mean"] - 0.5) < 1e-9 and ci["lo"] < 0.5 < ci["hi"]
    assert bootstrap_ci([1.0] * 10)["lo"] == 1.0


def test_template_examples_skipped():
    import os
    p = os.path.join(os.path.dirname(__file__), "queries_human_template.csv")
    assert load_queries(p) == []
    assert len(load_queries(p, include_examples=True)) == 5


if __name__ == "__main__":
    test_ranking_and_metrics(); test_bootstrap(); test_template_examples_skipped(); print("ok")
