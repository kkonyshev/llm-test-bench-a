#!/bin/bash
# Usage: ./run_ollama_model.sh <ollama-tag>
# Benchmarks one Ollama model alone: unloads the others, runs reasoning then coding,
# and records where the model was placed.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
TAG="$1"
export BENCH_NUM_CTX="${BENCH_NUM_CTX:-32768}"
echo "=== MODEL_START $TAG $(date -u +%FT%TZ) ==="
for m in $(curl -s localhost:11434/api/ps | python3 -c "import json,sys;[print(m[\"name\"]) for m in json.load(sys.stdin)[\"models\"]]"); do ollama stop "$m"; done
nvidia-smi --query-gpu=index,name,memory.used --format=csv,noheader
./run_detached.sh reasoning-benchmark "$TAG"
./run_detached.sh coding-benchmark "$TAG"
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
cat "coding-benchmark/runs/$TAG/ollama_ps_after.txt"
ollama stop "$TAG"
echo "=== MODEL_DONE $TAG $(date -u +%FT%TZ) ==="
