#!/bin/bash
# Usage: ./run_openai_model.sh <label> <base-url> <process-pattern>
# Benchmarks a model behind an OpenAI-compatible server (llama-server, Strata, ...), with the
# server process CPU/RSS, system RAM and every GPU sampled every 5s into <label>_resources.csv.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
LABEL="$1"; export BENCH_OPENAI_URL="$2"; PAT="$3"
export BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-100000}"
CSV="${LABEL//[:\/]/_}_resources.csv"
echo "time,proc_cpu_pct,proc_rss_gb,ram_used_gb,ram_avail_gb,swap_used_gb,load1,gpu0_util,gpu0_mem_mib,gpu0_w,gpu1_util,gpu1_mem_mib,gpu1_w" > "$CSV"
(
  while sleep 5; do
    P=$(pgrep -f "$PAT" | head -1); [ -n "$P" ] || continue
    RSS=$(ps -o rss= -p $P)
    CPU=$(top -b -n1 -d0.5 -p $P | awk -v p=$P "\$1==p{print \$9}")
    MEM=$(free -b | awk "/^Mem/{printf \"%.1f,%.1f\", \$3/2^30, \$7/2^30}")
    SWAP=$(free -b | awk "/^Swap/{printf \"%.1f\", \$3/2^30}")
    G=$(nvidia-smi --query-gpu=utilization.gpu,memory.used,power.draw --format=csv,noheader,nounits | tr -d " " | paste -sd,)
    echo "$(date +%T),$CPU,$(awk -v r=$RSS "BEGIN{printf \"%.1f\", r/2^20}"),$MEM,$SWAP,$(cut -d" " -f1 /proc/loadavg),$G" >> "$CSV"
  done
) &
SAMPLER=$!
echo "=== MODEL_START $LABEL $BENCH_OPENAI_URL $(date -u +%FT%TZ) ==="
./run_detached.sh reasoning-benchmark "$LABEL"
./run_detached.sh coding-benchmark "$LABEL"
kill $SAMPLER
echo "=== MODEL_DONE $LABEL $(date -u +%FT%TZ) ==="
