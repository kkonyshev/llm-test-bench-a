#!/bin/bash
# Waits for a glm-4.7-flash q8 tag to finish pulling, then benchmarks it alone on the GPUs.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
find_tag() { curl -s localhost:11434/api/tags | python3 -c "import json,sys;print(next((m[\"name\"] for m in json.load(sys.stdin)[\"models\"] if m[\"name\"].startswith(\"glm-4.7-flash\") and \"q8\" in m[\"name\"].lower()),\"\"))"; }
until TAG=$(find_tag) && [ -n "$TAG" ]; do sleep 30; done
echo "=== GLM_Q8_FOUND $TAG $(date -u +%FT%TZ) ==="
for m in $(curl -s localhost:11434/api/ps | python3 -c "import json,sys;[print(m[\"name\"]) for m in json.load(sys.stdin)[\"models\"]]"); do ollama stop "$m"; done
nvidia-smi --query-gpu=index,name,memory.used --format=csv,noheader
export BENCH_NUM_CTX=32768
./run_detached.sh reasoning-benchmark "$TAG"
./run_detached.sh coding-benchmark "$TAG"
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
cat "coding-benchmark/runs/$TAG/ollama_ps_after.txt"
ollama stop "$TAG"
echo "=== GLM_Q8_DONE $(date -u +%FT%TZ) ==="
