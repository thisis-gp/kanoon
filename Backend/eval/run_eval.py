"""Known-item retrieval evaluation. Run INSIDE the backend container with eval/ copied to /tmp/eval.

Methods (all use the engine's own code in model.retrieval):
  dense          RetrievalEngine._dense, CAND=50
  bm25           RetrievalEngine._bm25, CAND=50 (a failed BM25 query counts as a miss and is tallied)
  hybrid         RRF k=60 over dense+bm25 (same formula as RetrievalEngine.search), top RERANK_DEPTH
  hybrid+rerank  RetrievalEngine.search(query, k=depth) with the cache cleared (cold path)
Metrics are CASE level: chunk results are collapsed to distinct cases in first-appearance order.
Usage: python run_eval.py QUERIES(.jsonl|.csv) OUT.json [--include-examples] [--limit N]
"""
import argparse
import json
import sys
import time

sys.path.insert(0, "/app")
sys.path.insert(0, "/tmp/eval")
import model.retrieval as R  # noqa: E402
from common import (case_ranking, gold_rank, load_queries, paired_diff_ci,  # noqa: E402
                    per_query_scores, summarize_method, median, percentile)

METHODS = ("dense", "bm25", "hybrid", "hybrid+rerank")
RRF_K = 60
DEPTH = R.CAND  # engine default
WARMUP_QUERY = "warm up the models before timing anything"


def rrf(dense, sparse, depth):
    text, score = {}, {}
    for lst in (dense, sparse):
        for rank, (i, c, t) in enumerate(lst):
            text[i] = (c, t)
            score[i] = score.get(i, 0.0) + 1.0 / (RRF_K + rank)
    return [(i, *text[i]) for i in sorted(score, key=score.get, reverse=True)[:depth]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queries")
    ap.add_argument("out")
    ap.add_argument("--include-examples", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    qpath, out = a.queries, a.out
    queries = load_queries(qpath, include_examples=a.include_examples)
    if a.limit:
        queries = queries[:a.limit]

    eng = R.RetrievalEngine()
    R.RERANK_DEPTH = DEPTH
    conn = eng._conn()
    conn.autocommit = True
    cur = conn.cursor()
    eng.search(WARMUP_QUERY, k=10)  # load both models
    eng._cache.clear()

    per_type = {}
    bm25_failures = 0
    t_start = time.time()
    for n_done, q in enumerate(queries):
        qv = R._vec_literal(R._embed().encode([q["query"]], normalize_embeddings=True, convert_to_numpy=True)[0])
        dense = eng._dense(cur, qv, R.CAND, None)
        try:
            sparse = eng._bm25(cur, q["query"], R.CAND, None)
        except Exception:
            sparse, bm25_failures = [], bm25_failures + 1
        hybrid = rrf(dense, sparse, DEPTH)
        eng._cache.clear()
        t0 = time.perf_counter()
        reranked = eng.search(q["query"], k=DEPTH)
        rerank_ms = (time.perf_counter() - t0) * 1000
        rankings = {
            "dense": case_ranking(dense), "bm25": case_ranking(sparse), "hybrid": case_ranking(hybrid),
            "hybrid+rerank": case_ranking([(0, r["case_id"], "") for r in reranked]),
        }
        bucket = per_type.setdefault(q["type"], {"ranks": {m: [] for m in METHODS}, "rerank_ms": []})
        for m in METHODS:
            bucket["ranks"][m].append(gold_rank(rankings[m], q["gold_case_id"]))
        bucket["rerank_ms"].append(rerank_ms)
        if (n_done + 1) % 20 == 0:
            print(f"  {n_done + 1}/{len(queries)} elapsed {time.time() - t_start:.0f}s", flush=True)

    result = {"queries_file": qpath, "date_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
              "rrf_k": RRF_K, "cand": R.CAND, "rerank_depth": DEPTH, "bm25_failures": bm25_failures,
              "embed_model": R.EMBED_MODEL, "rerank_model": R.RERANK_MODEL, "types": {}}
    for qtype, b in per_type.items():
        scores = {m: [per_query_scores(r) for r in b["ranks"][m]] for m in METHODS}
        top1 = lambda m: [s["top1"] for s in scores[m]]
        result["types"][qtype] = {
            "n": len(b["ranks"]["dense"]),
            "methods": {m: summarize_method(b["ranks"][m]) for m in METHODS},
            "paired_top1_diff": {
                "rerank_minus_bm25": paired_diff_ci(top1("hybrid+rerank"), top1("bm25")),
                "rerank_minus_hybrid": paired_diff_ci(top1("hybrid+rerank"), top1("hybrid")),
                "bm25_minus_hybrid": paired_diff_ci(top1("bm25"), top1("hybrid")),
            },
            "rerank_cold_ms": {"p50": median(b["rerank_ms"]), "p95": percentile(b["rerank_ms"], 95)},
            "gold_ranks": b["ranks"],
        }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(f"wrote {out} in {time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
