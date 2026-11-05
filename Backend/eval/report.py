"""Build results/RESULTS.md from results/*.json. Stdlib only. Usage: python report.py [--baseline-commit HASH]"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
METHODS = ("dense", "bm25", "hybrid", "hybrid+rerank")
METHOD_LABEL = {"dense": "dense only", "bm25": "BM25 only", "hybrid": "hybrid (RRF k=60)", "hybrid+rerank": "hybrid + rerank"}

HARDWARE = ("Oracle Cloud VM, 2 OCPU Ampere A1 (aarch64), no GPU, Docker caps: backend 1200 MB, db 700 MB, swap off. "
            "Models: all-MiniLM-L6-v2 (dense), cross-encoder/ms-marco-MiniLM-L-6-v2 (rerank). "
            "Corpus: 924 cases, 46,281 chunks. INFER_CONCURRENCY=1 (default), RERANK_DEPTH default 50.")
CAVEATS = [
    "Known-item PROXY: every query is built from text that is in the index, so scores are optimistic. "
    "It is not a user benchmark and does not measure answer quality.",
    "Passage queries are near-verbatim chunk text, which favours BM25. Title queries are regex-extracted titles; "
    "99 of 924 titles are 'Not available' and were excluded, as were non-unique titles.",
    "Metrics are case level (chunks collapsed to distinct cases). MRR@10 counts the first gold case within 10 distinct cases.",
    "Confidence intervals: percentile bootstrap over queries, 2000 resamples, fixed seed. They cover query sampling only.",
    "Sweep and method latency are in-process (engine call), not HTTP. HTTP latency includes queueing on the inference semaphore.",
    "The eval process shared the backend container (second copy of both models), so memory in that phase is higher than serving alone. "
    "Timings were taken with nothing else using the stack, but a second model copy can still change cache behaviour slightly.",
    "Warm HTTP latency at concurrency 4 and 8 is only lightly stressed: the 60/min rate limit forces the harness to pace warm requests, so few overlap.",
    "No human-labelled queries exist yet (see queries_human_template.csv). /ask and LLM answers were not tested (no key).",
    "These numbers do NOT reproduce, confirm or refute the resume claims (84% to 96% top-1, 7 s to 4 ms).",
]


def load(name):
    p = os.path.join(RES, name)
    return json.load(open(p)) if os.path.exists(p) else None


def pc(ci):
    return f"{ci['mean'] * 100:.1f}% [{ci['lo'] * 100:.1f}, {ci['hi'] * 100:.1f}]"


def mrr(ci):
    return f"{ci['mean']:.3f} [{ci['lo']:.3f}, {ci['hi']:.3f}]"


def ms(x):
    return "n/a" if x is None else (f"{x:.1f} ms" if x < 100 else f"{x / 1000:.2f} s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-commit", default="unknown")
    a = ap.parse_args()
    methods, sweep, lat = load("methods_known_item.json"), load("sweep_depth.json"), load("latency_http.json")
    out = ["# Kanoon retrieval evaluation results", "",
           f"Baseline commit (Backend/model code evaluated): `{a.baseline_commit}`", "",
           f"Hardware and setup: {HARDWARE}", ""]
    if methods:
        out += [f"## 1. Method comparison (date {methods['date_utc']} UTC, known-item PROXY)", "",
                f"Candidates per method {methods['cand']}, RRF k={methods['rrf_k']}, rerank depth {methods['rerank_depth']}. "
                f"BM25 query failures (counted as misses): {methods['bm25_failures']}. 95% bootstrap CI in brackets.", ""]
        for qtype, t in methods["types"].items():
            out += [f"### {qtype} queries (n={t['n']})", "", "| Method | top-1 | top-5 | MRR@10 |", "|---|---|---|---|"]
            for m in METHODS:
                s = t["methods"][m]
                out.append(f"| {METHOD_LABEL[m]} | {pc(s['top1'])} | {pc(s['top5'])} | {mrr(s['rr10'])} |")
            out += ["", "Paired top-1 difference (percentage points, 95% CI):", ""]
            for k, v in t["paired_top1_diff"].items():
                out.append(f"- {k.replace('_', ' ')}: {v['mean'] * 100:+.1f} [{v['lo'] * 100:+.1f}, {v['hi'] * 100:+.1f}]")
            rc = t["rerank_cold_ms"]
            out += ["", f"Hybrid+rerank cold latency in-process (depth {methods['rerank_depth']}): "
                        f"p50 {ms(rc['p50'])}, p95 {ms(rc['p95'])}.", ""]
    if sweep:
        out += [f"## 2. RERANK_DEPTH sweep (date {sweep['date_utc']} UTC, known-item PROXY)", "",
                f"Hybrid+rerank, n={sweep['n_per_type']} queries per type, cache cleared per call, "
                "in-process cold latency (embed + dense + BM25 + RRF + rerank), 2 OCPU Ampere A1.", ""]
        for qtype, d in sweep["types"].items():
            out += [f"### {qtype} queries", "", "| Depth | top-1 | top-5 | cold p50 | cold p95 |", "|---|---|---|---|---|"]
            for depth, v in d.items():
                out.append(f"| {depth} | {pc(v['top1'])} | {pc(v['top5'])} | {ms(v['cold_ms']['p50'])} | {ms(v['cold_ms']['p95'])} |")
            out.append("")
    if lat:
        out += [f"## 3. /search HTTP latency (date {lat['date_utc']} UTC)", "",
                "GET /search?k=10 against 127.0.0.1:8080 on the VM. Cold = unseen query; warm = repeat (in-memory cache). "
                "Client-side latency including semaphore queueing. Requests paced at "
                f"{lat['rate_limit_per_min_used']}/min to stay under the 60/min rate limit. "
                f"Aborted for memory: {lat['aborted']}.", "",
                "| Concurrency | Cold n | Cold p50 | Cold p95 | Cold wall | Warm n | Warm p50 | Warm p95 | Non-200 | Peak backend MiB | Peak db MiB |",
                "|---|---|---|---|---|---|---|---|---|---|---|"]
        for conc, v in lat["levels"].items():
            c, w, m = v["cold"], v["warm"], v["peak_mem_mib"]
            bad = ",".join(c["non200"] + w["non200"]) or "none"
            out.append(f"| {conc} | {c['ok']}/{c['n']} | {ms(c['p50_ms'])} | {ms(c['p95_ms'])} | {c['wall_s']:.0f} s | "
                       f"{w['ok']}/{w['n']} | {ms(w['p50_ms'])} | {ms(w['p95_ms'])} | {bad} | {m['backend']} | {m['db']} |")
        out.append("")
    out += ["## Caveats", ""] + [f"- {c}" for c in CAVEATS] + [""]
    open(os.path.join(RES, "RESULTS.md"), "w", encoding="utf-8").write("\n".join(out))
    print("wrote results/RESULTS.md")


if __name__ == "__main__":
    main()
