# Kanoon retrieval evaluation results

Baseline commit (Backend/model code evaluated): `3ed459e`

Hardware and setup: Oracle Cloud VM, 2 OCPU Ampere A1 (aarch64), no GPU, Docker caps: backend 1200 MB, db 700 MB, swap off. Models: all-MiniLM-L6-v2 (dense), cross-encoder/ms-marco-MiniLM-L-6-v2 (rerank). Corpus: 924 cases, 46,281 chunks. INFER_CONCURRENCY=1 (default), RERANK_DEPTH default 50.

## 1. Method comparison (date 2026-11-04 04:56:19 UTC, known-item PROXY)

Candidates per method 50, RRF k=60, rerank depth 50. BM25 query failures (counted as misses): 10. 95% bootstrap CI in brackets.

### passage queries (n=100)

| Method | top-1 | top-5 | MRR@10 |
|---|---|---|---|
| dense only | 37.0% [27.0, 47.0] | 52.0% [42.0, 62.0] | 0.444 [0.355, 0.532] |
| BM25 only | 88.0% [81.0, 94.0] | 91.0% [85.0, 96.0] | 0.895 [0.840, 0.950] |
| hybrid (RRF k=60) | 50.0% [40.0, 60.0] | 85.0% [78.0, 92.0] | 0.657 [0.583, 0.727] |
| hybrid + rerank | 93.0% [88.0, 98.0] | 94.0% [89.0, 98.0] | 0.935 [0.885, 0.980] |

Paired top-1 difference (percentage points, 95% CI):

- rerank minus bm25: +5.0 [+1.0, +9.0]
- rerank minus hybrid: +43.0 [+33.0, +53.0]
- bm25 minus hybrid: +38.0 [+28.0, +48.0]

Hybrid+rerank cold latency in-process (depth 50): p50 5.16 s, p95 6.78 s.

### title queries (n=100)

| Method | top-1 | top-5 | MRR@10 |
|---|---|---|---|
| dense only | 24.0% [16.0, 33.0] | 46.0% [36.0, 56.0] | 0.331 [0.255, 0.410] |
| BM25 only | 84.0% [77.0, 91.0] | 95.0% [90.0, 99.0] | 0.889 [0.836, 0.936] |
| hybrid (RRF k=60) | 41.0% [31.0, 51.0] | 88.0% [81.0, 94.0] | 0.593 [0.521, 0.665] |
| hybrid + rerank | 96.0% [92.0, 99.0] | 97.0% [94.0, 100.0] | 0.967 [0.932, 0.995] |

Paired top-1 difference (percentage points, 95% CI):

- rerank minus bm25: +12.0 [+5.0, +19.0]
- rerank minus hybrid: +55.0 [+45.0, +66.0]
- bm25 minus hybrid: +43.0 [+31.0, +55.0]

Hybrid+rerank cold latency in-process (depth 50): p50 7.03 s, p95 9.50 s.

## 2. RERANK_DEPTH sweep (date 2026-11-04 04:56:46 UTC, known-item PROXY)

Hybrid+rerank, n=30 queries per type, cache cleared per call, in-process cold latency (embed + dense + BM25 + RRF + rerank), 2 OCPU Ampere A1.

### passage queries

| Depth | top-1 | top-5 | cold p50 | cold p95 |
|---|---|---|---|---|
| 10 | 96.7% [90.0, 100.0] | 96.7% [90.0, 100.0] | 1.09 s | 1.39 s |
| 20 | 96.7% [90.0, 100.0] | 96.7% [90.0, 100.0] | 2.05 s | 3.11 s |
| 30 | 96.7% [90.0, 100.0] | 96.7% [90.0, 100.0] | 3.15 s | 4.49 s |
| 50 | 100.0% [100.0, 100.0] | 100.0% [100.0, 100.0] | 5.31 s | 7.05 s |

### title queries

| Depth | top-1 | top-5 | cold p50 | cold p95 |
|---|---|---|---|---|
| 10 | 96.7% [90.0, 100.0] | 96.7% [90.0, 100.0] | 1.43 s | 2.40 s |
| 20 | 96.7% [90.0, 100.0] | 96.7% [90.0, 100.0] | 2.88 s | 4.45 s |
| 30 | 96.7% [90.0, 100.0] | 96.7% [90.0, 100.0] | 4.27 s | 6.39 s |
| 50 | 100.0% [100.0, 100.0] | 100.0% [100.0, 100.0] | 7.21 s | 9.83 s |

## 3. /search HTTP latency (date 2026-11-04 05:11:21 UTC)

GET /search?k=10 against 127.0.0.1:8080 on the VM. Cold = unseen query; warm = repeat (in-memory cache). Client-side latency including semaphore queueing. Requests paced at 55/min to stay under the 60/min rate limit. Aborted for memory: False.

| Concurrency | Cold n | Cold p50 | Cold p95 | Cold wall | Warm n | Warm p50 | Warm p95 | Non-200 | Peak backend MiB | Peak db MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 16/16 | 7.21 s | 8.92 s | 117 s | 60/60 | 2.7 ms | 4.7 ms | none | 530.7 | 180.3 |
| 4 | 16/16 | 31.27 s | 34.44 s | 126 s | 60/60 | 9.5 ms | 11.9 ms | none | 689.4 | 188.6 |
| 8 | 24/24 | 58.92 s | 61.52 s | 176 s | 60/60 | 17.2 ms | 21.8 ms | none | 770.6 | 200.1 |

## Caveats

- Known-item PROXY: every query is built from text that is in the index, so scores are optimistic. It is not a user benchmark and does not measure answer quality.
- Passage queries are near-verbatim chunk text, which favours BM25. Title queries are regex-extracted titles; 99 of 924 titles are 'Not available' and were excluded, as were non-unique titles.
- Metrics are case level (chunks collapsed to distinct cases). MRR@10 counts the first gold case within 10 distinct cases.
- Confidence intervals: percentile bootstrap over queries, 2000 resamples, fixed seed. They cover query sampling only.
- Sweep and method latency are in-process (engine call), not HTTP. HTTP latency includes queueing on the inference semaphore.
- The eval process shared the backend container (second copy of both models), so memory in that phase is higher than serving alone. Timings were taken with nothing else using the stack, but a second model copy can still change cache behaviour slightly.
- Warm HTTP latency at concurrency 4 and 8 is only lightly stressed: the 60/min rate limit forces the harness to pace warm requests, so few overlap.
- No human-labelled queries exist yet (see queries_human_template.csv). /ask and LLM answers were not tested (no key).
- These numbers do NOT reproduce, confirm or refute the resume claims (84% to 96% top-1, 7 s to 4 ms).
