#!/bin/bash
# Usage: ./retry_coding.sh <ollama-tag>: coding attempt 2 for a 0/23 run (attempt 1 kept as -attempt1),
# under the shared .bench.lock so it never overlaps the queue.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
M="$1"
exec 9>.bench.lock; flock 9
mv "coding-benchmark/runs/$M" "coding-benchmark/runs/$M-attempt1"
cp "coding-benchmark/runs_$M.log" "coding-benchmark/runs_$M-attempt1.log"
BENCH_NUM_CTX=32768 ./run_detached.sh coding-benchmark "$M"
ollama stop "$M" >/dev/null 2>&1
echo "=== RETRY_DONE $M ==="
