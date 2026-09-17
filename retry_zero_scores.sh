#!/bin/bash
set -uo pipefail
cd /data/remote-agent/local-llm-bench
echo "=== RETRY_START $(date -u +%FT%TZ) ==="
for TAG in "glm-4.7-flash:q4_K_M" "deepseek-coder-v2:16b-lite-instruct-q4_K_M" "qwen2.5:72b"; do
  echo "=== RETRY_MODEL_START: $TAG $(date -u +%FT%TZ) ==="
  ./run_detached.sh coding-benchmark "$TAG"
  ollama stop "$TAG" >/dev/null 2>&1 || true
  echo "=== RETRY_MODEL_DONE: $TAG $(date -u +%FT%TZ) ==="
done
echo "=== RETRY_COMPLETE $(date -u +%FT%TZ) ==="
