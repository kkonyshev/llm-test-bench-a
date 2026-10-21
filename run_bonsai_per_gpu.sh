#!/bin/bash
# Ternary Bonsai 2 27B on each GPU alone: starts its own llama-server (Bonsai-demo binary,
# same weights and flags as scripts/start_llama_server.sh used, port 8092) pinned with
# CUDA_VISIBLE_DEVICES, benchmarks it, stops it. Waits for the dual-GPU run to finish and
# for the Bonsai server on :8081 to be stopped first.
set -uo pipefail
cd /data/remote-agent/local-llm-bench
D=/data/apps/Bonsai-demo
until grep -q MODEL_DONE bonsai.log; do sleep 15; done
echo "=== DUAL_DONE, waiting for :8081 to stop $(date -u +%FT%TZ) ==="
while pgrep -f "$D/bin/cuda/llama-server.*--port 8081" >/dev/null; do sleep 15; done
echo "=== PER_GPU_START $(date -u +%FT%TZ) ==="
for G in 0 1; do
  NAME=$(nvidia-smi -i $G --query-gpu=name --format=csv,noheader | sed -e "s/NVIDIA GeForce //" -e "s/ //g" | tr A-Z a-z)
  LABEL="ternary-bonsai-2-27b-pq2_0-$NAME"
  CUDA_VISIBLE_DEVICES=$G "$D/bin/cuda/llama-server" -m "$D/models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-PQ2_0.gguf" \
    --host 127.0.0.1 --port 8092 -ngl 99 -fa on -c 131072 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05 --jinja \
    --mmproj "$D/models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf" > "bonsai_server_gpu$G.log" 2>&1 &
  SRV=$!
  ok=1
  until curl -sf localhost:8092/health >/dev/null; do
    if ! kill -0 $SRV 2>/dev/null; then ok=0; break; fi
    sleep 3
  done
  if [ $ok = 0 ]; then
    echo "!!! server on GPU $G exited, see bonsai_server_gpu$G.log"; tail -5 "bonsai_server_gpu$G.log"; continue
  fi
  echo "=== GPU $G ($NAME) ready: $LABEL ==="
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
  ./run_openai_model.sh "$LABEL" http://localhost:8092 "llama-server.*--port 8092"
  kill $SRV; wait $SRV 2>/dev/null
done
echo "=== PER_GPU_DONE $(date -u +%FT%TZ) ==="
