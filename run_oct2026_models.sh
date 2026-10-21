#!/bin/bash
# New models from October 2026 on the dual-GPU box (RTX 5090 + RTX 5070 Ti).
# Same suite as run_gpu_upgrade_bench.sh; each row is "<ollama-tag>|<label>|<optional BENCH_NUM_CTX>".
set -uo pipefail
cd /data/remote-agent/local-llm-bench

MODELS=(
  "nemotron-3.5-bolt:74b-a9b|nemotron-3.5-bolt-74b-a9b-iq2|"
  "sage-a1.5:q4_k_m|sage-a1.5-q4_k_m|"
  "sage-a1.5:q8_0|sage-a1.5-q8_0|"
)

echo "=== OCT2026_SUITE_START $(date -u +%FT%TZ) ==="
nvidia-smi --query-gpu=index,name,memory.total,memory.used --format=csv

for entry in "${MODELS[@]}"; do
  IFS="|" read -r TAG LABEL CTX <<< "$entry"
  export BENCH_NUM_CTX="${CTX:-32768}"
  echo
  echo "=== BENCH_MODEL_START: $TAG ($LABEL, num_ctx=$BENCH_NUM_CTX) $(date -u +%FT%TZ) ==="
  if ! ollama list | awk "{print \$1}" | grep -qxF "$TAG"; then
    echo "!!! MISSING TAG $TAG, skipping !!!"; continue
  fi
  echo "--- coding benchmark: $TAG ---"
  ./run_detached.sh coding-benchmark "$TAG"
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
  echo "--- reasoning benchmark: $TAG ---"
  ./run_detached.sh reasoning-benchmark "$TAG"
  ollama stop "$TAG" >/dev/null 2>&1 || true
  echo "=== BENCH_MODEL_DONE: $TAG $(date -u +%FT%TZ) ==="
done
echo "=== OCT2026_SUITE_COMPLETE $(date -u +%FT%TZ) ==="
