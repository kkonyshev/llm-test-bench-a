#!/bin/bash
# One-time setup for this benchmark suite.
set -euo pipefail

BASE="$(cd "$(dirname "$0")" && pwd)"

echo "=== Checking for Ollama ==="
if ! command -v ollama &>/dev/null; then
  echo "Ollama not found. Install from https://ollama.com/download (or 'brew install ollama') first."
  exit 1
fi
ollama --version

echo "=== Checking for the Hugging Face CLI ('hf') ==="
if ! command -v hf &>/dev/null; then
  echo "Installing huggingface_hub[cli] via pipx..."
  if ! command -v pipx &>/dev/null; then
    echo "pipx not found — install it first (e.g. 'brew install pipx' on macOS), then re-run this script."
    exit 1
  fi
  pipx install "huggingface_hub[cli]"
fi
hf --version 2>/dev/null || true

echo "=== NOTE: SSL/corporate proxy ==="
echo "If 'hf download' fails with a CERTIFICATE_VERIFY_FAILED error (common on"
echo "networks with TLS-inspecting proxies, e.g. Zscaler), fix Python's trust"
echo "store to match the OS trust store:"
echo "    pipx inject huggingface-hub pip-system-certs"

echo "=== Setting up shared Python venv for the coding benchmark's test suite ==="
python3 -m venv "$BASE/.venv"
source "$BASE/.venv/bin/activate"
pip install -q --upgrade pip
pip install -q fastapi "uvicorn[standard]" pydantic sqlalchemy httpx pytest
python -c "import fastapi, pytest, httpx; print('deps ok')"

echo "=== Setup complete ==="
echo "Next: pull + build a model (see MODELS.md), then:"
echo "  ./run_detached.sh coding-benchmark <ollama-model-tag>"
echo "  ./run_detached.sh reasoning-benchmark <ollama-model-tag>"
