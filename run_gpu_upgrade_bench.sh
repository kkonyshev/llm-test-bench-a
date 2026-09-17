#!/bin/bash
# Full re-run of the llm-test-bench-a model set on the new dual-GPU box
# (RTX 5090 32GB + RTX 5070 Ti 16GB, native Ollama on :11434 — see HARDWARE.md
# "Machine 3" entry for exact specs). Reuses ollama tags already pulled on
# this host instead of re-downloading GGUFs from HF; each row below is
# "<already-installed-ollama-tag>|<original-MODELS.md-name>|<optional BENCH_NUM_CTX>".
set -uo pipefail
cd /data/remote-agent/local-llm-bench

MODELS=(
  'qwen3-coder:30b-a3b-q4_K_M|qwen3-coder-30b-a3b|'
  'glm-4.7-flash:q4_K_M|glm-4.7-flash|'
  'qwen3.8:27b-q4_K_M|qwen3.8-27b|'
  'qwen2.5-coder:7b-instruct-q4_K_M|qwen2.5-coder-7b-test|'
  'deepseek-coder-v2:16b-lite-instruct-q4_K_M|deepseek-coder-v2-lite|'
  'gemma4:26b-a4b-it-q4_K_M|gemma4-26b|'
  'llama3.1:70b|llama3.1:70b|'
  'llama3.3:70b|llama3.3:70b|'
  'qwen2.5:72b|qwen2.5:72b|'
  'nemotron:70b|nemotron:70b|'
  'deepseek-coder-v2:236b-instruct-q4_K_M|deepseek-coder-v2-full-bench|8192'
)

echo "=== GPU_BENCH_SUITE_START $(date -u +%FT%TZ) ==="
nvidia-smi --query-gpu=index,name,memory.total,memory.used --format=csv

for entry in "${MODELS[@]}"; do
  IFS='|' read -r TAG LABEL CTX <<< "$entry"
  export BENCH_NUM_CTX="${CTX:-32768}"

  echo
  echo "=== BENCH_MODEL_START: $TAG (orig: $LABEL, num_ctx=$BENCH_NUM_CTX) $(date -u +%FT%TZ) ==="

  if ! ollama list | awk '{print $1}' | grep -qF "$TAG"; then
    echo "!!! MISSING TAG $TAG, skipping !!!"
    continue
  fi

  echo "--- coding benchmark: $TAG ---"
  ./run_detached.sh coding-benchmark "$TAG"

  echo "--- reasoning benchmark: $TAG ---"
  ./run_detached.sh reasoning-benchmark "$TAG"

  # free VRAM between models so each run starts from a clean load
  ollama stop "$TAG" >/dev/null 2>&1 || true

  echo "=== BENCH_MODEL_DONE: $TAG $(date -u +%FT%TZ) ==="
done

echo "=== GPU_BENCH_SUITE_COMPLETE $(date -u +%FT%TZ) ==="
