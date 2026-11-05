"""RERANK_DEPTH sweep for hybrid+rerank, run INSIDE the backend container (eval/ copied to /tmp/eval).
Each query is searched once per depth with the engine's in-memory cache cleared, so latency is the cold path
(embed + dense + BM25 + RRF + cross-encoder at that depth). Latency is in-process, no HTTP.
Usage: python sweep_depth.py QUERIES.jsonl OUT.json [--n 30] [--depths 10,20,30,50]
The first --n queries of each type are used (the file is already seeded and shuffled).
"""
import argparse
import json
import sys
import time

sys.path.insert(0, "/app")
sys.path.insert(0, "/tmp/eval")
import model.retrieval as R  # noqa: E402
from common import (bootstrap_ci, case_ranking, gold_rank, load_queries,  # noqa: E402
                    median, percentile, per_query_scores)

WARMUP_QUERY = "warm up the models before timing anything"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queries")
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--depths", default="10,20,30,50")
    a = ap.parse_args()
    depths = [int(d) for d in a.depths.split(",")]
    queries = load_queries(a.queries)
    by_type = {}
    for q in queries:
        by_type.setdefault(q["type"], []).append(q)

    eng = R.RetrievalEngine()
    R.RERANK_DEPTH = R.CAND
    eng.search(WARMUP_QUERY, k=10)
    t_start = time.time()
    result = {"date_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "n_per_type": a.n,
              "depths": depths, "types": {}}
    for qtype, qs in by_type.items():
        qs = qs[:a.n]
        result["types"][qtype] = {}
        for depth in depths:
            R.RERANK_DEPTH = depth
            ranks, lat = [], []
            for q in qs:
                eng._cache.clear()
                t0 = time.perf_counter()
                res = eng.search(q["query"], k=depth)
                lat.append((time.perf_counter() - t0) * 1000)
                ranks.append(gold_rank(case_ranking([(0, r["case_id"], "") for r in res]), q["gold_case_id"]))
            sc = [per_query_scores(r) for r in ranks]
            result["types"][qtype][str(depth)] = {
                "n": len(qs),
                "top1": bootstrap_ci([s["top1"] for s in sc]),
                "top5": bootstrap_ci([s["top5"] for s in sc]),
                "cold_ms": {"p50": median(lat), "p95": percentile(lat, 95)},
            }
            d = result["types"][qtype][str(depth)]
            print(f"{qtype} depth={depth} top1={d['top1']['mean']:.3f} top5={d['top5']['mean']:.3f} "
                  f"p50={d['cold_ms']['p50']:.0f}ms ({time.time() - t_start:.0f}s)", flush=True)
    R.RERANK_DEPTH = R.CAND
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)


if __name__ == "__main__":
    main()
