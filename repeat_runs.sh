#!/bin/bash
# Usage: ./repeat_runs.sh <ollama-tag> <total-runs>
# Repeat runs of both benchmarks for a heavy model, to judge run-to-run quality. Waits until the
# first run is done (the tag in queue_done.txt, or SUPER_DONE for Nemotron Super), then runs
# 2..<total-runs> under the shared .bench.lock into runs/<tag>-runN with resource sampling.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
TAG="$1"; N="$2"
first_done() {
  grep -qxF "$TAG" queue_done.txt 2>/dev/null || { [[ "$TAG" == nemotron-3.5-super* ]] && grep -q SUPER_DONE nemotron_super.log; }
}
until first_done; do sleep 60; done
echo "=== REPEAT_READY $TAG $(date -u +%FT%TZ) ==="
for i in $(seq 2 "$N"); do
  exec 9>.bench.lock; flock 9
  while nvidia-smi --query-compute-apps=pid --format=csv,noheader | grep -q . && ! curl -s localhost:11434/api/ps | grep -q '"name"'; do
    echo "waiting for free GPUs: $(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | tr "\n" " ")"; sleep 60
  done
  for m in $(curl -s localhost:11434/api/ps | python3 -c "import json,sys;[print(m[\"name\"]) for m in json.load(sys.stdin)[\"models\"]]"); do ollama stop "$m"; done
  export BENCH_RUN_SUFFIX="-run$i" BENCH_NUM_CTX=32768
  CSV="${TAG//:/_}-run${i}_resources.csv"
  echo "time,proc_cpu_pct,proc_rss_gb,ram_used_gb,ram_avail_gb,swap_used_gb,load1,gpu0_util,gpu0_mem_mib,gpu0_w,gpu1_util,gpu1_mem_mib,gpu1_w" > "$CSV"
  (
    while sleep 5; do
      P=$(pgrep -f "/usr/local/lib/ollama/llama-server" | head -1); [ -n "$P" ] || continue
      RSS=$(ps -o rss= -p $P)
      CPU=$(top -b -n1 -d0.5 -p $P | awk -v p=$P "\$1==p{print \$9}")
      MEM=$(free -b | awk "/^Mem/{printf \"%.1f,%.1f\", \$3/2^30, \$7/2^30}")
      SWAP=$(free -b | awk "/^Swap/{printf \"%.1f\", \$3/2^30}")
      G=$(nvidia-smi --query-gpu=utilization.gpu,memory.used,power.draw --format=csv,noheader,nounits | tr -d " " | paste -sd,)
      echo "$(date +%T),$CPU,$(awk -v r=$RSS "BEGIN{printf \"%.1f\", r/2^20}"),$MEM,$SWAP,$(cut -d" " -f1 /proc/loadavg),$G" >> "$CSV"
    done
  ) & SAMPLER=$!
  echo "=== REPEAT_START $TAG run $i $(date -u +%FT%TZ) ==="
  ./run_detached.sh reasoning-benchmark "$TAG"
  ./run_detached.sh coding-benchmark "$TAG"
  kill $SAMPLER
  ollama stop "$TAG" >/dev/null 2>&1
  echo "=== REPEAT_DONE $TAG run $i $(date -u +%FT%TZ) ==="
  flock -u 9
done
echo "=== REPEAT_ALL_DONE $TAG $(date -u +%FT%TZ) ==="
