#!/bin/bash
# Usage: ./pull_and_build.sh <hf-repo> <gguf-filename> <ollama-tag>
# Example:
#   ./pull_and_build.sh unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF \
#       Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf qwen3-coder-30b-a3b
set -euo pipefail

REPO="$1"
FILE="$2"
TAG="$3"
DIR="$HOME/models/$TAG"

mkdir -p "$DIR"
cd "$DIR"

echo "=== Downloading $FILE from $REPO ==="
hf download "$REPO" "$FILE" --local-dir .

echo "=== Building Ollama model '$TAG' ==="
cat > Modelfile <<EOF
FROM ./$FILE
EOF
ollama create "$TAG" -f Modelfile

echo "=== Done. Verify with: ollama list ==="
ollama list | grep "$TAG" || true
