#!/bin/bash
# Usage: ./run_queue.sh <tag-regex> [idle-hours]
# Watches Ollama for newly pulled tags matching <tag-regex> and benchmarks each one, one at a
# time (shares .bench.lock with run_nemotron_super.sh) with the GPUs free (run_ollama_model.sh
# + resource sampling into <tag>_resources.csv). Tags already benchmarked: queue_done.txt.
# Exits after [idle-hours] (default 6) with nothing new.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
RE="$1"; IDLE_MAX=$(( ${2:-6} * 3600 )); idle=0
touch queue_done.txt

sample() {  # sample <csv>: Ollama runner CPU/RSS, RAM, both GPUs every 5s
  echo "time,proc_cpu_pct,proc_rss_gb,ram_used_gb,ram_avail_gb,swap_used_gb,load1,gpu0_util,gpu0_mem_mib,gpu0_w,gpu1_util,gpu1_mem_mib,gpu1_w" > "$1"
  while sleep 5; do
    P=$(pgrep -f "/usr/local/lib/ollama/llama-server" | head -1); [ -n "$P" ] || continue
    RSS=$(ps -o rss= -p $P)
    CPU=$(top -b -n1 -d0.5 -p $P | awk -v p=$P "\$1==p{print \$9}")
    MEM=$(free -b | awk "/^Mem/{printf \"%.1f,%.1f\", \$3/2^30, \$7/2^30}")
    SWAP=$(free -b | awk "/^Swap/{printf \"%.1f\", \$3/2^30}")
    G=$(nvidia-smi --query-gpu=utilization.gpu,memory.used,power.draw --format=csv,noheader,nounits | tr -d " " | paste -sd,)
    echo "$(date +%T),$CPU,$(awk -v r=$RSS "BEGIN{printf \"%.1f\", r/2^20}"),$MEM,$SWAP,$(cut -d" " -f1 /proc/loadavg),$G" >> "$1"
  done
}

echo "=== QUEUE_START /$RE/ $(date -u +%FT%TZ) ==="
while [ $idle -lt $IDLE_MAX ]; do
  TAG=$(curl -s localhost:11434/api/tags | python3 -c "
import json, re, sys
done = set(open('queue_done.txt').read().split())
tags = sorted(m['name'] for m in json.load(sys.stdin)['models'] if re.search(sys.argv[1], m['name']) and m['name'] not in done)
print(tags[0] if tags else '')" "$RE")
  if [ -z "$TAG" ]; then sleep 60; idle=$((idle + 60)); continue; fi
  idle=0
  # one benchmark at a time across run_queue.sh and run_nemotron_super.sh
  exec 9>.bench.lock; flock 9
  while nvidia-smi --query-compute-apps=pid --format=csv,noheader | grep -q . && ! curl -s localhost:11434/api/ps | grep -q '"name"'; do
    echo "waiting for free GPUs before $TAG: $(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | tr "\n" " ")"; sleep 60
  done
  echo "=== QUEUE_NEXT $TAG $(date -u +%FT%TZ) ==="
  sample "${TAG//:/_}_resources.csv" & SAMPLER=$!
  ./run_ollama_model.sh "$TAG"
  kill $SAMPLER
  echo "$TAG" >> queue_done.txt
  flock -u 9
done
echo "=== QUEUE_IDLE_EXIT $(date -u +%FT%TZ) ==="
