#!/bin/bash
cd /data/remote-agent/local-llm-bench
while ! docker exec ollama-test ollama list | grep -q '^llama3.3:70b '; do
  sleep 15
done
echo '=== llama3.3:70b registered, starting benchmarks ==='
./run_detached.sh coding-benchmark llama3.3:70b
./run_detached.sh reasoning-benchmark llama3.3:70b
echo === LLAMA33_ALL_DONE ===
