# Kanoon retrieval evaluation

This folder measures how well the retrieval engine (`model/retrieval.py`) finds the right case, and how fast `/search` is on the Oracle VM (2 OCPU Ampere A1, no GPU).

## What this is, and what it is not

It is a **known-item proxy**. Each query is built from text that is already in the index:

- **passage queries**: the first 14 words of the middle chunk of a case. The gold answer is that case.
- **title queries**: the case title ("X vs Y"). The gold answer is that case.

Because the query text comes from the indexed text, scores are **optimistic**. Passage queries are almost verbatim, so keyword search (BM25) looks very strong. This is **not** a user benchmark. It does not measure whether real legal questions return useful cases, and it says nothing about answer quality.

To get a real measure, fill in `queries_human_template.csv` with questions a lawyer or student would ask and the case that answers each one (columns `query`, `gold_case_id`, `notes`). The five template rows are marked `EXAMPLE` and are skipped by default. Run the runner on your own file with `run_eval.py queries_human.csv results/methods_human.json`.

## Methods

All use the engine's own code inside the backend container.

| Method | How |
|---|---|
| dense | `_dense`, 50 candidates (MiniLM, pgvector) |
| BM25 | `_bm25`, 50 candidates (pg_search) |
| hybrid | RRF with k=60 over the two lists |
| hybrid + rerank | `RetrievalEngine.search` (cross-encoder on the fused list), cache cleared |

Metrics are **case level**: the chunk list is collapsed to distinct cases in order of first appearance. Top-1 and top-5 mean the gold case is at rank 1 or within rank 5. MRR@10 is the mean of 1/rank, counted only if rank is 10 or better. Confidence intervals are 95% percentile bootstrap over queries (2000 resamples, fixed seed). Paired top-1 differences between methods are also bootstrapped.

## Files

| File | Purpose |
|---|---|
| `build_queries.py` | Builds `queries_known_item.jsonl` (seed 20261104, 100 per type). Skips non-unique and ellipsis-truncated titles. |
| `queries_human_template.csv` | Template for hand-labelled queries. |
| `run_eval.py` | Runs the four methods, writes `results/methods_*.json`. Accepts `.jsonl` or `.csv`. |
| `sweep_depth.py` | RERANK_DEPTH 10/20/30/50: top-1, top-5, cold latency. |
| `latency_http.py` | `/search` cold and warm p50/p95 at concurrency 1/4/8 with memory samples. |
| `memwatch.sh` | Logs docker stats; kills the eval if the backend reaches 1100 MiB. |
| `report.py` | Builds `results/RESULTS.md` from the JSON files. |
| `test_common.py` | Tests for metrics, bootstrap and the CSV loader. |
| `run_all.sh` | Reproduces everything. |

## Reproduce

```
bash run_all.sh all          # sync, queries, methods, sweep, latency, report
bash run_all.sh methods      # or one step: sync | queries | methods | sweep | latency | report
python test_common.py
```

The scripts copy this folder into the running backend container's `/tmp/eval` (no image rebuild) and run Python there. The latency step runs on the VM host and uses `sudo docker stats`. Nothing writes to the `ailse` database (SELECT only). The search cache is in memory, so `latency_http.py` needs a fresh `--offset` if you run it twice against the same API process.

## Things to keep in mind

- The eval process loads a second copy of both models inside the 1200 MB backend container. The watchdog stops the run at 1100 MiB.
- `/search` is rate limited to 60 requests a minute per IP, so the latency harness paces itself at 55 a minute. Cold and warm numbers are not affected by the pacing.
- `/ask` and any LLM step are not tested (no key).
- Do not compare these numbers with the resume claims. They measure a different thing.
