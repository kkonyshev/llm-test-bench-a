#!/bin/bash
set -uo pipefail
cd /data/remote-agent/local-llm-bench
source /data/remote-agent/llm-bench/hf-venv/bin/activate
HF=/data/remote-agent/llm-bench/hf-venv/bin/hf

wait_for_ollama_tag() {
  local tag="$1"
  while ! docker exec ollama-test ollama list | grep -q "^$tag "; do
    sleep 15
  done
}

echo "=== waiting for llama3.3:70b benchmarks to finish $(date -u +%FT%TZ) ==="
while pgrep -f 'wait_and_run_llama33|run_bench.sh llama3.3:70b' >/dev/null; do sleep 15; done

echo "=== BENCH_MODEL_START: qwen2.5:72b $(date -u +%FT%TZ) ==="
wait_for_ollama_tag 'qwen2.5:72b'
./run_detached.sh coding-benchmark qwen2.5:72b
./run_detached.sh reasoning-benchmark qwen2.5:72b
echo "=== BENCH_MODEL_DONE: qwen2.5:72b $(date -u +%FT%TZ) ==="

echo "=== BENCH_MODEL_START: nemotron:70b $(date -u +%FT%TZ) ==="
wait_for_ollama_tag 'nemotron:70b'
./run_detached.sh coding-benchmark nemotron:70b
./run_detached.sh reasoning-benchmark nemotron:70b
echo "=== BENCH_MODEL_DONE: nemotron:70b $(date -u +%FT%TZ) ==="

echo "=== BENCH_MODEL_START: deepseek-coder-v2-full-bench $(date -u +%FT%TZ) ==="
DIR=/data/remote-agent/llm-bench/models/deepseek-coder-v2-full
mkdir -p "$DIR"
"$HF" download bartowski/DeepSeek-Coder-V2-Instruct-GGUF --include 'DeepSeek-Coder-V2-Instruct-Q4_K_M.gguf/*' --local-dir "$DIR"
docker exec ollama-test sh -c "printf 'FROM /staging/deepseek-coder-v2-full/DeepSeek-Coder-V2-Instruct-Q4_K_M.gguf/DeepSeek-Coder-V2-Instruct-Q4_K_M-00001-of-00004.gguf\n' > /tmp/Modelfile_dsv2full && ollama create deepseek-coder-v2-full-bench -f /tmp/Modelfile_dsv2full"

if docker exec ollama-test ollama list | grep -q '^deepseek-coder-v2-full-bench:'; then
  ./run_detached.sh coding-benchmark deepseek-coder-v2-full-bench
  ./run_detached.sh reasoning-benchmark deepseek-coder-v2-full-bench
else
  echo '!!! OLLAMA CREATE FAILED for deepseek-coder-v2-full-bench !!!'
fi
echo "=== ALL_EXTRA_MODELS_COMPLETE $(date -u +%FT%TZ) ==="
