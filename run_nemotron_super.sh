#!/bin/bash
# Waits for nemotron-3.5-super to finish pulling, then benchmarks it alone (GPU + RAM offload)
# with the Ollama runner's CPU/RSS, system RAM and both GPUs sampled every 5s.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
find_tag() { curl -s localhost:11434/api/tags | python3 -c "import json,sys;print(next((m[\"name\"] for m in json.load(sys.stdin)[\"models\"] if m[\"name\"].startswith(\"nemotron-3.5-super\")),\"\"))"; }
until TAG=$(find_tag) && [ -n "$TAG" ]; do sleep 30; done
echo "=== SUPER_FOUND $TAG $(date -u +%FT%TZ) ==="
# one benchmark at a time: wait for run_queue.sh to finish its current model
exec 9>.bench.lock; flock 9
echo "=== SUPER_LOCK $(date -u +%FT%TZ) ==="
# wait until nothing else holds the GPUs (Strata, ComfyUI, our llama-server, a miner)
while nvidia-smi --query-compute-apps=pid --format=csv,noheader | grep -q .; do
  echo "waiting: GPUs busy: $(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | tr "\n" " ")"; sleep 60
done
for m in $(curl -s localhost:11434/api/ps | python3 -c "import json,sys;[print(m[\"name\"]) for m in json.load(sys.stdin)[\"models\"]]"); do ollama stop "$m"; done
free -g | sed -n 2p; nvidia-smi --query-gpu=index,memory.used --format=csv,noheader

LABEL="${TAG//:/_}"
CSV="${LABEL}_resources.csv"
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
) &
SAMPLER=$!
./run_ollama_model.sh "$TAG"
kill $SAMPLER
echo "=== SUPER_DONE $(date -u +%FT%TZ) ==="
