#!/bin/bash
# Follow-up to run_bonsai_per_gpu.sh:
#  1) RTX 5070 Ti alone with -c 65536 (131072 does not fit 16 GB: cudaMalloc out of memory),
#     BENCH_MAX_TOKENS 64000 to stay inside that window.
#  2) RTX 5090 coding attempt 2 (attempt 1 was 0/23), same flags as attempt 1 (-c 131072).
set -uo pipefail
cd /data/remote-agent/local-llm-bench
D=/data/apps/Bonsai-demo

serve() {  # serve <gpu> <ctx> <log>
  CUDA_VISIBLE_DEVICES=$1 "$D/bin/cuda/llama-server" -m "$D/models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-PQ2_0.gguf" \
    --host 127.0.0.1 --port 8092 -ngl 99 -fa on -c "$2" --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05 --jinja \
    --mmproj "$D/models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf" > "$3" 2>&1 &
  SRV=$!
  until curl -sf localhost:8092/health >/dev/null; do
    kill -0 $SRV 2>/dev/null || { echo "!!! server on GPU $1 exited, see $3"; grep -E "out of memory|failed" "$3" | head -3; return 1; }
    sleep 3
  done
  echo "=== GPU $1 ready, -c $2 ==="
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
}

if serve 1 65536 bonsai_server_gpu1_ctx64k.log; then
  BENCH_MAX_TOKENS=64000 ./run_openai_model.sh ternary-bonsai-2-27b-pq2_0-rtx5070ti-ctx64k http://localhost:8092 "llama-server.*--port 8092"
  kill $SRV; wait $SRV 2>/dev/null
fi

M=ternary-bonsai-2-27b-pq2_0-rtx5090
mv "coding-benchmark/runs/$M" "coding-benchmark/runs/$M-attempt1"
cp "coding-benchmark/runs_$M.log" "coding-benchmark/runs_$M-attempt1.log"
if serve 0 131072 bonsai_server_gpu0_attempt2.log; then
  BENCH_OPENAI_URL=http://localhost:8092 BENCH_MAX_TOKENS=100000 ./run_detached.sh coding-benchmark "$M"
  kill $SRV; wait $SRV 2>/dev/null
fi
echo "=== FOLLOWUP_DONE $(date -u +%FT%TZ) ==="
