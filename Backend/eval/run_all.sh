#!/bin/bash
# Reproduce everything. Run from a PC with `ssh a1` access (VM stack kanoon-backend-1 / kanoon-db-1 up).
# Usage: bash run_all.sh [sync|queries|methods|sweep|latency|report|all]
# Needs: nothing installed on the VM; eval/ is copied into the container's /tmp (the image is not rebuilt).
set -euo pipefail
cd "$(dirname "$0")"
STEP=${1:-all}
SSH="ssh -o LogLevel=ERROR a1"
C=kanoon-backend-1
N_PER_TYPE=${N_PER_TYPE:-100}
SWEEP_N=${SWEEP_N:-30}
mkdir -p results

sync_pkg() {
  tar --exclude=results --exclude=__pycache__ -cf - . | $SSH 'rm -rf ~/eval_pkg && mkdir ~/eval_pkg && tar -xf - -C ~/eval_pkg'
  $SSH "sudo docker exec $C rm -rf /tmp/eval && sudo docker cp ~/eval_pkg $C:/tmp/eval && sudo docker exec $C mkdir -p /tmp/eval/results"
}
in_c() { $SSH "sudo docker exec $C python /tmp/eval/$*"; }
fetch() { $SSH "sudo docker cp $C:/tmp/eval/results/$1 /tmp/$1 && cat /tmp/$1" > "results/$1"; }

start_watch() {  # memory guard: aborts the eval if backend >= 1100 MiB (pidfile, so we never pkill ourselves)
  stop_watch_quiet
  $SSH 'rm -f /tmp/memwatch.log; nohup sh ~/eval_pkg/memwatch.sh /tmp/memwatch.log >/dev/null 2>&1 </dev/null & echo $! > /tmp/memwatch.pid'
}
stop_watch_quiet() { $SSH 'test -f /tmp/memwatch.pid && kill $(cat /tmp/memwatch.pid) 2>/dev/null; rm -f /tmp/memwatch.pid; true'; }
stop_watch() { $SSH 'cp /tmp/memwatch.log ~/memwatch.log'; $SSH 'cat ~/memwatch.log' > results/memwatch.log; stop_watch_quiet; }

case "$STEP" in
  sync|all) sync_pkg ;;&
  queries|all)
    in_c "build_queries.py /tmp/eval/queries_known_item.jsonl $N_PER_TYPE"
    $SSH "sudo docker cp $C:/tmp/eval/queries_known_item.jsonl /tmp/q.jsonl && cat /tmp/q.jsonl" > queries_known_item.jsonl
    $SSH 'cp /tmp/q.jsonl ~/eval_pkg/queries_known_item.jsonl' ;;&
  methods|all)
    start_watch
    in_c "run_eval.py /tmp/eval/queries_known_item.jsonl /tmp/eval/results/methods_known_item.json"
    fetch methods_known_item.json ;;&
  sweep|all)
    start_watch
    in_c "sweep_depth.py /tmp/eval/queries_known_item.jsonl /tmp/eval/results/sweep_depth.json --n $SWEEP_N"
    fetch sweep_depth.json ;;&
  latency|all)
    start_watch
    $SSH 'python3 ~/eval_pkg/latency_http.py ~/eval_pkg/queries_known_item.jsonl /tmp/latency.json'
    $SSH 'cat /tmp/latency.json' > results/latency_http.json
    stop_watch ;;&
  report|all)
    python report.py --baseline-commit "${BASELINE_COMMIT:-3ed459e}" ;;
esac
