#!/bin/bash
# Waits for Ternary-Bonsai-2-9B-PQ2_0.gguf to finish downloading (no .incomplete/.part
# siblings, size unchanged for 60s), then benchmarks it on each GPU alone with our own
# llama-server on :8092 (same flags as for the 27B).
set -uo pipefail
cd /data/remote-agent/local-llm-bench
D=/data/apps/Bonsai-demo

find_gguf() { find "$D/models" /data/models/sources -xdev -iname "Ternary-Bonsai-2-9B*PQ2_0*.gguf" 2>/dev/null | grep -v -i mmproj | head -1; }
while :; do
  F=$(find_gguf)
  if [ -n "$F" ] && ! find "$(dirname "$F")" -maxdepth 3 \( -name "*.incomplete" -o -name "*.part" -o -name "*.lock" -newer "$F" \) 2>/dev/null | grep -q .; then
    S1=$(stat -c %s "$F"); sleep 60; S2=$(stat -c %s "$F")
    [ "$S1" = "$S2" ] && break
  else
    sleep 30
  fi
done
MM=$(find "$(dirname "$F")" -maxdepth 1 -iname "*mmproj*.gguf" | head -1)
echo "=== BONSAI_9B_FOUND $F (mmproj: ${MM:-none}) $(date -u +%FT%TZ) ==="

for G in 0 1; do
  NAME=$(nvidia-smi -i $G --query-gpu=name --format=csv,noheader | sed -e "s/NVIDIA GeForce //" -e "s/ //g" | tr A-Z a-z)
  LABEL="ternary-bonsai-2-9b-pq2_0-$NAME"
  CUDA_VISIBLE_DEVICES=$G "$D/bin/cuda/llama-server" -m "$F" ${MM:+--mmproj "$MM"} \
    --host 127.0.0.1 --port 8092 -ngl 99 -fa on -c 131072 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05 --jinja \
    > "bonsai9b_server_gpu$G.log" 2>&1 &
  SRV=$!
  ok=1
  until curl -sf localhost:8092/health >/dev/null; do
    if ! kill -0 $SRV 2>/dev/null; then ok=0; break; fi
    sleep 3
  done
  if [ $ok = 0 ]; then
    echo "!!! server on GPU $G exited, see bonsai9b_server_gpu$G.log"; grep -E "out of memory|failed|error" "bonsai9b_server_gpu$G.log" | head -3; continue
  fi
  echo "=== GPU $G ($NAME) ready: $LABEL ==="
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
  ./run_openai_model.sh "$LABEL" http://localhost:8092 "llama-server.*--port 8092"
  kill $SRV; wait $SRV 2>/dev/null
done
echo "=== BONSAI_9B_DONE $(date -u +%FT%TZ) ==="
