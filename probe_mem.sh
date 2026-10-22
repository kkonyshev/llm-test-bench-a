#!/bin/bash
# Usage: [PROBE_TOKENS=3000] ./probe_mem.sh <ollama-tag>...
# Memory/CPU probe of Ollama models with the benchmark context (BENCH_NUM_CTX, default 32768).
# For each tag, alone on idle GPUs: load it, save the `ollama ps` CPU/GPU split, then sample the
# runner and both GPUs every second while it generates PROBE_TOKENS tokens. The runner's RAM is
# split into RssAnon (its own memory: weights copied to RAM, KV cache, buffers) and RssFile
# (pages of the mmapped GGUF, reclaimable page cache). Output: resources/probe_<tag>.{csv,txt}.
# Holds .bench.lock so it never overlaps a benchmark.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
CTX="${BENCH_NUM_CTX:-32768}"; TOKENS="${PROBE_TOKENS:-3000}"
mkdir -p resources
exec 9>.bench.lock; flock 9
gen() {  # gen <tag> <prompt> <num_predict>
  curl -s localhost:11434/api/generate -d "{\"model\":\"$1\",\"stream\":false,\"prompt\":\"$2\",\"options\":{\"num_ctx\":$CTX,\"num_predict\":$3}}"
}
for TAG in "$@"; do
  for m in $(curl -s localhost:11434/api/ps | python3 -c "import json,sys;[print(m['name']) for m in json.load(sys.stdin)['models']]"); do ollama stop "$m"; done
  until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 500 ]; do sleep 2; done
  F="resources/probe_${TAG//:/_}"
  gen "$TAG" "Hi" 1 > /dev/null
  P=$(pgrep -f "/usr/local/lib/ollama/llama-server" | head -1)
  { echo "tag=$TAG ctx=$CTX"; ollama ps | sed -n 2p; } > "$F.txt"
  echo "time,proc_cpu_pct,proc_rss_gb,rss_anon_gb,rss_file_gb,ram_used_gb,ram_avail_gb,swap_used_gb,load1,gpu0_util,gpu0_mem_mib,gpu0_w,gpu1_util,gpu1_mem_mib,gpu1_w" > "$F.csv"
  (
    while sleep 1; do
      ST=$(awk '/^VmRSS|^RssAnon|^RssFile/{printf "%.1f,", $2/2^20}' /proc/$P/status) || break
      CPU=$(top -b -n1 -d0.5 -p $P | awk -v p=$P '$1==p{print $9}')
      MEM=$(free -b | awk '/^Mem/{printf "%.1f,%.1f", $3/2^30, $7/2^30}')
      SWAP=$(free -b | awk '/^Swap/{printf "%.1f", $3/2^30}')
      G=$(nvidia-smi --query-gpu=utilization.gpu,memory.used,power.draw --format=csv,noheader,nounits | tr -d ' ' | paste -sd,)
      echo "$(date +%T),$CPU,$ST$MEM,$SWAP,$(cut -d' ' -f1 /proc/loadavg),$G" >> "$F.csv"
    done
  ) & SAMPLER=$!
  OUT=$(gen "$TAG" "Write a detailed, well-commented Python implementation of an LRU cache with TTL support, plus unit tests." "$TOKENS")
  kill $SAMPLER; wait $SAMPLER 2>/dev/null
  echo "$OUT" | python3 -c "import json,sys;d=json.load(sys.stdin);print('tokens=%d tok/s=%.1f'%(d['eval_count'],d['eval_count']/d['eval_duration']*1e9))" >> "$F.txt"
  echo "== $TAG"; cat "$F.txt"
  ollama stop "$TAG" >/dev/null 2>&1
done
flock -u 9
echo PROBE_DONE
