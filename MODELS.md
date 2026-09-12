# Models tested

All quants are Q4_K_M (or the closest unsloth "UD-Q4_K_M" dynamic-quant
equivalent) unless noted. Sizes are the actual GGUF file size, verified via
the Hugging Face API at the time of testing (Sept 2026) — re-verify if
repos have since changed.

## Original 6 (baseline set, tested on both machines)

| Model | Architecture | HF repo | GGUF file | Size | Ollama tag used |
|---|---|---|---|---|---|
| Qwen3-Coder-30B-A3B-Instruct | MoE, 30B total / 3B active | `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF` | `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf` | 18.6 GB | `qwen3-coder-30b-a3b` |
| GLM-4.7-Flash | MoE, ~23B total / 3B active | `unsloth/GLM-4.7-Flash-GGUF` | `GLM-4.7-Flash-Q4_K_M.gguf` | 18.3 GB | `glm-4.7-flash` |
| Qwen3.8-27B | Dense, 27B | `unsloth/Qwen3.8-27B-GGUF` | `Qwen3.8-27B-UD-Q4_K_M.gguf` | 16.5 GB | `qwen3.8-27b` |
| Qwen2.5-Coder-7B-Instruct | Dense, 7B | `Qwen/Qwen2.5-Coder-7B-Instruct-GGUF` | `qwen2.5-coder-7b-instruct-q4_k_m.gguf` | 4.7 GB | `qwen2.5-coder-7b-test` |
| DeepSeek-Coder-V2-Lite-Instruct | MoE, 16B total / 2.4B active | `bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF` | `DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf` | 10.4 GB | `deepseek-coder-v2-lite` |
| Gemma4-26B (A4B) | MoE, 26B total / 4B active | `unsloth/gemma-4-26B-A4B-it-GGUF` | `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf` | 16.9 GB | `gemma4-26b` |

## Added on workstation1: 70B+ class, out of curiosity re: CPU/GPU offload

Pulled directly from Ollama's public library (`ollama pull <tag>`) rather
than the HF-GGUF-plus-`ollama create` flow, since official quants already
exist there.

| Model | Architecture | Ollama tag | Size (on disk) | Notes |
|---|---|---|---|---|
| Llama 3.1 70B Instruct | Dense, 70B | `llama3.1:70b` | 42 GB | Generic instruct model, mid-2024 |
| Llama 3.3 70B Instruct | Dense, 70B | `llama3.3:70b` | 42 GB | Same base weights as 3.1, redone post-training only (Dec 2024) |
| Qwen2.5-72B Instruct | Dense, 72B | `qwen2.5:72b` | 47 GB | |
| Llama-3.1-Nemotron-70B-Instruct | Dense, 70B | `nemotron:70b` | 42 GB | NVIDIA RLHF fine-tune of the Llama 3.1 70B base |
| DeepSeek-Coder-V2-Instruct (full) | MoE, 236B total / 21B active | `deepseek-coder-v2-full-bench` | 142 GB | See "Split-GGUF models" below — required a manual merge step |

## Split-GGUF models (files >50GB on Hugging Face)

Hugging Face auto-splits any single file over ~50GB into numbered parts
(e.g. `model-Q4_K_M.gguf/model-Q4_K_M-00001-of-00004.gguf`). This tripped
up Ollama 0.33.3's `ollama create`: pointing `FROM` at the first part
reliably failed with `Error: split GGUF "...-00001-of-00004.gguf" has 1
shards, expected 4` regardless of where the Modelfile was placed relative
to the shards — a real limitation/bug in this Ollama version's split-GGUF
support, not a path or config mistake.

**Workaround**: merge the shards into one physical GGUF file before running
`ollama create`, using the pure-Python `gguf` package (no need to build
llama.cpp/`gguf-split` from source):

```bash
pip install gguf
python3 merge_gguf.py shard1.gguf shard2.gguf shard3.gguf shard4.gguf merged.gguf
```

The merge script (not included in this repo — write it against
`gguf.GGUFReader`/`gguf.GGUFWriter`) copies all non-split metadata KVs
from shard 1, then streams every tensor from all shards into a single
output file via `add_tensor_info` + `write_tensor_data` (memory-mapped
reads, so it doesn't need to hold the whole multi-hundred-GB model in RAM
at once). Verify the shard tensor counts sum to the GGUF's own
`split.tensors.count` metadata key before merging, and verify the merged
file's size exactly matches the sum of the shard sizes afterward.

Then point the Modelfile at the single merged file:
```
FROM /path/to/merged.gguf
```

## Reproducing on new hardware

For a model already in Ollama's public library:
```bash
ollama pull <tag>
```

For a custom HF GGUF (single-file, not split):
```bash
./pull_and_build.sh <hf-repo> <gguf-file> <ollama-tag>
```

Example:
```bash
./pull_and_build.sh unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF \
    Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf qwen3-coder-30b-a3b
```

This downloads the file to `~/models/<tag>/`, writes a minimal `Modelfile`
(`FROM ./<file>`), and runs `ollama create <tag> -f Modelfile`.

## Sizing quants to your hardware

Before picking a quant on different hardware, check what's available and
its size via the Hugging Face API (no auth needed):

```bash
curl -s "https://huggingface.co/api/models/<repo>/tree/main" | python3 -c "
import json,sys
d = json.load(sys.stdin)
for f in d:
    n = f.get('path','')
    if n.endswith('.gguf'):
        s = f.get('size') or (f.get('lfs') or {}).get('size')
        if s: print(f'{n}: {s/1e9:.1f} GB')
"
```

If a `.gguf` entry comes back as a directory (size 0), it's a split file —
query `.../tree/main/<that-path>` to see and sum the individual shard
sizes, and see "Split-GGUF models" above for how to load it.

Rule of thumb used throughout this project: keep the GGUF file size to
roughly 60-70% of total available memory (unified memory on Apple Silicon,
or VRAM if you want to stay 100% GPU-resident on a discrete-GPU machine),
leaving room for context/KV cache and OS overhead. Once a model exceeds
that threshold on a discrete-GPU machine, expect a steep — not gradual —
drop in throughput (see `RESULTS.md`).
