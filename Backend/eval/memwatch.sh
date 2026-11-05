#!/bin/sh
# Run on the VM. Logs docker stats every 3 s to $1; if kanoon-backend-1 >= LIMIT_MIB, kills the eval python inside it.
LOG=${1:-/tmp/memwatch.log}; LIMIT_MIB=${LIMIT_MIB:-1100}
while :; do
  line=$(sudo docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' kanoon-backend-1 kanoon-db-1 | tr '\n' ' ')
  echo "$(date -u +%T) $line" >> "$LOG"
  mib=$(echo "$line" | sed -n 's/.*kanoon-backend-1 \([0-9.]*\)\(MiB\|GiB\).*/\1 \2/p' | awk '{ if ($2=="GiB") print $1*1024; else print $1 }')
  if [ -n "$mib" ] && [ "$(echo "$mib $LIMIT_MIB" | awk '{print ($1>=$2)}')" = 1 ]; then
    echo "$(date -u +%T) ABORT backend=$mib MiB" >> "$LOG"
    sudo docker exec kanoon-backend-1 pkill -f '/tmp/eval/' ; pkill -f latency_http.py
  fi
  sleep 3
done
