#!/bin/bash
# Bonsai 2 9B coding attempt 2 on each GPU (attempt 1 was 0/23 on both), same flags.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
D=/data/apps/Bonsai-demo
F="$D/models/bonsai2-gguf/9B/Ternary-Bonsai-2-9B-PQ2_0.gguf"
MM="$D/models/bonsai2-gguf/9B/Ternary-Bonsai-2-9B-mmproj-Q8_0.gguf"
for G in 0 1; do
  NAME=$(nvidia-smi -i $G --query-gpu=name --format=csv,noheader | sed -e "s/NVIDIA GeForce //" -e "s/ //g" | tr A-Z a-z)
  M="ternary-bonsai-2-9b-pq2_0-$NAME"
  mv "coding-benchmark/runs/$M" "coding-benchmark/runs/$M-attempt1"
  cp "coding-benchmark/runs_$M.log" "coding-benchmark/runs_$M-attempt1.log"
  CUDA_VISIBLE_DEVICES=$G "$D/bin/cuda/llama-server" -m "$F" --mmproj "$MM" \
    --host 127.0.0.1 --port 8092 -ngl 99 -fa on -c 131072 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05 --jinja \
    > "bonsai9b_server_gpu${G}_attempt2.log" 2>&1 &
  SRV=$!
  until curl -sf localhost:8092/health >/dev/null; do kill -0 $SRV 2>/dev/null || break; sleep 3; done
  echo "=== GPU $G ($NAME) attempt 2 ==="
  BENCH_OPENAI_URL=http://localhost:8092 BENCH_MAX_TOKENS=100000 ./run_detached.sh coding-benchmark "$M"
  kill $SRV; wait $SRV 2>/dev/null
done
echo "=== BONSAI_9B_RETRY_DONE $(date -u +%FT%TZ) ==="
