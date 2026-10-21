#!/bin/bash
# Strata (Qwen3.8-Flash-Next GSQ-RCO IQ3_S, original weights) through its OpenAI API on :8081,
# with CPU/RAM/GPU sampled every 5s into strata_iq3s_resources.csv.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
export BENCH_OPENAI_URL=http://localhost:8081
# the IQ3_S config has a 65,536-token context; Strata rejects max_tokens beyond it
export BENCH_MAX_TOKENS=64000
export BENCH_API_KEY=$(python3 -c "import json;print(json.load(open(\"/data/apps/Strata/strata-iq3_s.json\")).get(\"api_key\",\"\"))")
M="${BENCH_LABEL:-qwen3.8-flash-next-iq3_s}"   # Strata serves any model name; the label only names the run directory
GPU=$(python3 -c "import json;print(json.load(open(\"/data/apps/Strata/strata-iq3_s.json\"))[\"gpu\"])")
CSV=strata_iq3s_resources${BENCH_LABEL:+_${BENCH_LABEL#qwen3.8-flash-next-iq3_s-}}.csv
echo "time,strata_cpu_pct,strata_rss_gb,ram_used_gb,ram_avail_gb,swap_used_gb,load1,gpu_util,gpu_mem_mib,gpu_w" > $CSV
(
  while sleep 5; do
    P=$(pgrep -f "/data/apps/Strata/engine/strata --serve" | head -1); [ -n "$P" ] || continue
    RSS=$(ps -o rss= -p $P)
    CPU=$(top -b -n1 -d0.5 -p $P | awk -v p=$P "\$1==p{print \$9}")
    MEM=$(free -b | awk "/^Mem/{printf \"%.1f,%.1f\", \$3/2^30, \$7/2^30}")
    SWAP=$(free -b | awk "/^Swap/{printf \"%.1f\", \$3/2^30}")
    G=$(nvidia-smi -i $GPU --query-gpu=utilization.gpu,memory.used,power.draw --format=csv,noheader,nounits | tr -d " ")
    echo "$(date +%T),$CPU,$(awk -v r=$RSS "BEGIN{printf \"%.1f\", r/2^20}"),$MEM,$SWAP,$(cut -d" " -f1 /proc/loadavg),$G" >> $CSV
  done
) &
SAMPLER=$!
echo "=== STRATA_START $(date -u +%FT%TZ) gpu=$GPU ==="
./run_detached.sh reasoning-benchmark "$M"
./run_detached.sh coding-benchmark "$M"
kill $SAMPLER
echo "=== STRATA_DONE $(date -u +%FT%TZ) ==="
