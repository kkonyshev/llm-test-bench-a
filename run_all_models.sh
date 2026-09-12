#!/bin/bash
set -uo pipefail
cd /data/remote-agent/local-llm-bench
source /data/remote-agent/llm-bench/hf-venv/bin/activate
HF=/data/remote-agent/llm-bench/hf-venv/bin/hf

MODELS_DIR=/data/remote-agent/llm-bench/models

MODELS=(
  'unsloth/Qwen3.8-27B-GGUF|Qwen3.8-27B-UD-Q4_K_M.gguf|qwen3.8-27b|qwen3.8-27b-bench'
  'bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF|DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf|deepseek-coder-v2-lite|deepseek-coder-v2-lite-bench'
  'unsloth/gemma-4-26B-A4B-it-GGUF|gemma-4-26B-A4B-it-UD-Q4_K_M.gguf|gemma4-26b|gemma4-26b-bench'
)

for entry in "${MODELS[@]}"; do
  IFS='|' read -r REPO FILE DIRTAG OLLTAG <<< "$entry"
  echo "=== BENCH_MODEL_START: $OLLTAG ($REPO/$FILE) $(date -u +%FT%TZ) ==="
  DIR="$MODELS_DIR/$DIRTAG"
  mkdir -p "$DIR"

  if [ ! -f "$DIR/$FILE" ]; then
    echo "--- downloading $DIRTAG ---"
    "$HF" download "$REPO" "$FILE" --local-dir "$DIR"
  else
    echo "--- $DIRTAG already downloaded ---"
  fi

  if [ ! -f "$DIR/$FILE" ]; then
    echo "!!! DOWNLOAD FAILED for $DIRTAG, skipping model !!!"
    continue
  fi

  echo "--- creating ollama model $OLLTAG ---"
  docker exec ollama-test sh -c "printf 'FROM /staging/$DIRTAG/$FILE\n' > /tmp/Modelfile_$DIRTAG && ollama create $OLLTAG -f /tmp/Modelfile_$DIRTAG"

  if ! docker exec ollama-test ollama list | grep -q "^$OLLTAG:"; then
    echo "!!! OLLAMA CREATE FAILED for $OLLTAG, skipping benchmarks !!!"
    continue
  fi

  echo "--- coding benchmark: $OLLTAG ---"
  ./run_detached.sh coding-benchmark "$OLLTAG"

  echo "--- reasoning benchmark: $OLLTAG ---"
  ./run_detached.sh reasoning-benchmark "$OLLTAG"

  echo "=== BENCH_MODEL_DONE: $OLLTAG $(date -u +%FT%TZ) ==="
done

echo "=== ALL_MODELS_COMPLETE $(date -u +%FT%TZ) ==="
