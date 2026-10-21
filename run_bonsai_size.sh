#!/bin/bash
# Usage: ./run_bonsai_size.sh <size>...   e.g. ./run_bonsai_size.sh 4B 2B
# Each Ternary Bonsai 2 size on each GPU alone (own llama-server on :8092, same flags as the
# 27B/9B runs): reasoning + coding with resource sampling; a 0/23 coding run gets one retry.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
D=/data/apps/Bonsai-demo

start_server() {  # start_server <gpu> <gguf> <mmproj> <log>
  CUDA_VISIBLE_DEVICES=$1 "$D/bin/cuda/llama-server" -m "$2" --mmproj "$3" \
    --host 127.0.0.1 --port 8092 -ngl 99 -fa on -c 131072 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05 --jinja \
    > "$4" 2>&1 &
  SRV=$!
  until curl -sf localhost:8092/health >/dev/null; do
    kill -0 $SRV 2>/dev/null || { echo "!!! server exited, see $4"; return 1; }
    sleep 2
  done
}

for SIZE in "$@"; do
  s=$(echo "$SIZE" | tr A-Z a-z)
  F="$D/models/bonsai2-gguf/$SIZE/Ternary-Bonsai-2-$SIZE-PQ2_0.gguf"
  MM="$D/models/bonsai2-gguf/$SIZE/Ternary-Bonsai-2-$SIZE-mmproj-Q8_0.gguf"
  for G in 0 1; do
    NAME=$(nvidia-smi -i $G --query-gpu=name --format=csv,noheader | sed -e "s/NVIDIA GeForce //" -e "s/ //g" | tr A-Z a-z)
    M="ternary-bonsai-2-$s-pq2_0-$NAME"
    start_server $G "$F" "$MM" "bonsai${s}_server_gpu$G.log" || continue
    echo "=== $SIZE on GPU $G ($NAME) ready ==="
    ./run_openai_model.sh "$M" http://localhost:8092 "llama-server.*--port 8092"
    if grep -q "pytest_exit_code=[^0]" "coding-benchmark/runs/$M/wall_clock.txt" && ! grep -qE "[1-9][0-9]* passed" "coding-benchmark/runs/$M/pytest_result.txt"; then
      echo "--- $M coding 0/23, attempt 2 ---"
      mv "coding-benchmark/runs/$M" "coding-benchmark/runs/$M-attempt1"
      cp "coding-benchmark/runs_$M.log" "coding-benchmark/runs_$M-attempt1.log"
      BENCH_OPENAI_URL=http://localhost:8092 BENCH_MAX_TOKENS=100000 ./run_detached.sh coding-benchmark "$M"
    fi
    kill $SRV; wait $SRV 2>/dev/null
  done
done
echo "=== BONSAI_SIZES_DONE $(date -u +%FT%TZ) ==="
