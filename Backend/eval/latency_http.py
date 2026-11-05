"""/search latency harness. Run ON the VM host (python3.9+, stdlib only; needs passwordless `sudo docker`).

For each concurrency level (1, 4, 8, max 8): send N_COLD unique queries (cold = never seen by the API
process, so cache miss) then repeat them for N_WARM requests (warm = in-memory cache hit).
Latency is client side, from send to full body, so under concurrency it includes queueing on the
inference semaphore (INFER_CONCURRENCY, default 1). Gate-wait for the 60/min rate limit is NOT counted.
docker stats of kanoon-backend-1 / kanoon-db-1 are sampled every 2 s; the run aborts if backend >= 1100 MiB.
Usage: python3 latency_http.py QUERIES.jsonl OUT.json [--base http://127.0.0.1:8080] [--offset 0]
Re-running against the same API process needs a new --offset (otherwise the queries are no longer cold).
"""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

LEVELS = (1, 4, 8)
MAX_CONCURRENCY = 8
N_COLD = {1: 16, 4: 16, 8: 24}
N_WARM = 60
RATE_LIMIT_PER_MIN = 55          # server allows 60/min/IP; stay under it
BACKEND_ABORT_MIB = 1100
SAMPLE_EVERY_S = 2.0
REQUEST_TIMEOUT_S = 300


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None


class RateGate:
    def __init__(self, per_min):
        self.per_min, self.stamps, self.lock = per_min, collections.deque(), threading.Lock()

    def wait(self):
        while True:
            with self.lock:
                now = time.monotonic()
                while self.stamps and now - self.stamps[0] > 60:
                    self.stamps.popleft()
                if len(self.stamps) < self.per_min:
                    self.stamps.append(now)
                    return
                sleep_for = 60 - (now - self.stamps[0]) + 0.05
            time.sleep(sleep_for)


def to_mib(s):
    s = s.strip()
    for unit, mult in (("GiB", 1024.0), ("MiB", 1.0), ("KiB", 1 / 1024)):
        if s.endswith(unit):
            return float(s[: -len(unit)]) * mult
    return float(s.rstrip("B")) / (1024 * 1024)


def docker_mem():
    out = subprocess.run(
        ["sudo", "docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.MemUsage}}",
         "kanoon-backend-1", "kanoon-db-1"], capture_output=True, text=True, timeout=60).stdout
    mem = {}
    for line in out.strip().splitlines():
        name, usage = line.split("|")
        mem[name] = to_mib(usage.split("/")[0])
    return mem


class MemSampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop_ev, self.abort = threading.Event(), threading.Event()
        self.peak = {"kanoon-backend-1": 0.0, "kanoon-db-1": 0.0}

    def reset(self):
        self.peak = {k: 0.0 for k in self.peak}

    def run(self):
        while not self.stop_ev.is_set():
            try:
                for k, v in docker_mem().items():
                    self.peak[k] = max(self.peak.get(k, 0.0), v)
                    if k == "kanoon-backend-1" and v >= BACKEND_ABORT_MIB:
                        self.abort.set()
            except Exception:
                pass
            self.stop_ev.wait(SAMPLE_EVERY_S)


def get(base, q, gate, sampler):
    if sampler.abort.is_set():
        return None, "aborted", 0.0
    gate.wait()
    url = f"{base}/search?" + urllib.parse.urlencode({"q": q, "k": 10})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_S) as r:
            r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__, (time.perf_counter() - t) * 1000
    return code, None, (time.perf_counter() - t) * 1000


def run_phase(base, queries, conc, gate, sampler):
    t0 = time.perf_counter()
    with ThreadPoolExecutor(conc) as ex:
        res = list(ex.map(lambda q: get(base, q, gate, sampler), queries))
    wall = time.perf_counter() - t0
    ok = [ms for code, err, ms in res if code == 200]
    return {"n": len(queries), "ok": len(ok), "non200": sorted({str(c) for c, e, _ in res if c != 200}),
            "p50_ms": pct(ok, 50), "p95_ms": pct(ok, 95), "max_ms": max(ok) if ok else None,
            "wall_s": wall, "throughput_rps": len(ok) / wall if wall else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queries")
    ap.add_argument("out")
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    ap.add_argument("--offset", type=int, default=0)
    a = ap.parse_args()
    pool = [json.loads(l)["query"] for l in open(a.queries, encoding="utf-8") if l.strip()
            if json.loads(l)["type"] == "title"]
    need = sum(N_COLD.values())
    if a.offset + need > len(pool):
        raise SystemExit(f"need {need} unique title queries from offset {a.offset}, have {len(pool)}")
    gate, sampler = RateGate(RATE_LIMIT_PER_MIN), MemSampler()
    sampler.start()
    result = {"date_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "base": a.base, "levels": {},
              "aborted": False, "rate_limit_per_min_used": RATE_LIMIT_PER_MIN}
    pos = a.offset
    for conc in LEVELS:
        assert conc <= MAX_CONCURRENCY
        qs = pool[pos:pos + N_COLD[conc]]
        pos += N_COLD[conc]
        sampler.reset()
        cold = run_phase(a.base, qs, conc, gate, sampler)
        warm_qs = [qs[i % len(qs)] for i in range(N_WARM)]
        warm = run_phase(a.base, warm_qs, conc, gate, sampler)
        time.sleep(SAMPLE_EVERY_S * 1.5)
        result["levels"][str(conc)] = {"cold": cold, "warm": warm,
                                       "peak_mem_mib": {k.replace("kanoon-", "").replace("-1", ""): round(v, 1)
                                                        for k, v in sampler.peak.items()}}
        print(conc, json.dumps(result["levels"][str(conc)]), flush=True)
        if sampler.abort.is_set():
            result["aborted"] = True
            print("ABORT: backend memory >= %d MiB" % BACKEND_ABORT_MIB, flush=True)
            break
        time.sleep(5)
    sampler.stop_ev.set()
    json.dump(result, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
