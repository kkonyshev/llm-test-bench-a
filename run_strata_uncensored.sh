#!/bin/bash
# Strata (Qwen3.8-Flash-Next Orca Uncensored IQ3_XXS, RTX 5070 Ti) through its OpenAI API on :8081.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
export BENCH_OPENAI_URL=http://localhost:8081
M="qwen3.8-flash-next-iq3_xxs:unsensored"
echo "=== STRATA_START $(date -u +%FT%TZ) ==="
./run_detached.sh reasoning-benchmark "$M"
./run_detached.sh coding-benchmark "$M"
echo "=== STRATA_DONE $(date -u +%FT%TZ) ==="
