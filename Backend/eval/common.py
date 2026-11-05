"""Shared helpers: query loading, case-level ranking, metrics, bootstrap CIs. Stdlib only."""
import csv
import json
import random
import statistics

TOP_K_RR = 10  # MRR is truncated at rank 10
N_BOOT = 2000
BOOT_SEED = 12345
EXAMPLE_MARK = "EXAMPLE"


def load_queries(path, include_examples=False):
    """Load .jsonl (id,type,query,gold_case_id) or .csv (query,gold_case_id,notes).
    CSV rows whose notes start with EXAMPLE are skipped unless include_examples."""
    rows = []
    if path.endswith(".jsonl"):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows
    with open(path, encoding="utf-8", newline="") as f:
        for i, r in enumerate(csv.DictReader(f)):
            query = (r.get("query") or "").strip()
            gold = (r.get("gold_case_id") or "").strip()
            notes = (r.get("notes") or "").strip()
            if not query or not gold:
                continue
            if notes.upper().startswith(EXAMPLE_MARK) and not include_examples:
                continue
            rows.append({"id": f"human-{i}", "type": "human", "query": query,
                         "gold_case_id": gold, "notes": notes})
    return rows


def case_ranking(chunk_rows):
    """Chunk rows (id, case_id, text) in rank order -> distinct case ids in order of first appearance."""
    seen, out = set(), []
    for row in chunk_rows:
        cid = row[1]
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def gold_rank(ranking, gold):
    """1-based rank of gold in a case ranking, or None."""
    for i, cid in enumerate(ranking):
        if cid == gold:
            return i + 1
    return None


def per_query_scores(rank):
    """Return dict of per-query metric values for one gold rank."""
    return {
        "top1": 1.0 if rank == 1 else 0.0,
        "top5": 1.0 if rank is not None and rank <= 5 else 0.0,
        "rr10": 1.0 / rank if rank is not None and rank <= TOP_K_RR else 0.0,
    }


def bootstrap_ci(values, n_boot=N_BOOT, seed=BOOT_SEED, alpha=0.05):
    """Mean and percentile bootstrap CI over per-query values."""
    n = len(values)
    if n == 0:
        return {"mean": None, "lo": None, "hi": None, "n": 0}
    rng = random.Random(seed)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return {"mean": sum(values) / n, "lo": lo, "hi": hi, "n": n}


def paired_diff_ci(a, b, n_boot=N_BOOT, seed=BOOT_SEED, alpha=0.05):
    """Bootstrap CI of mean(a - b) for paired per-query values."""
    return bootstrap_ci([x - y for x, y in zip(a, b)], n_boot, seed, alpha)


def percentile(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def summarize_method(ranks):
    """ranks: list of gold ranks (None = miss). Returns metrics with CIs."""
    scores = [per_query_scores(r) for r in ranks]
    return {m: bootstrap_ci([s[m] for s in scores]) for m in ("top1", "top5", "rr10")}


def median(xs):
    return statistics.median(xs) if xs else None
