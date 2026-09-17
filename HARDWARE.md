# Hardware — machines compared

Three machines' results are recorded in `RESULTS.md`. When comparing against
further hardware, record the same fields below for the new machine.

## Machine 1: MacBook Pro M3 16, late 2023 (baseline)

| Field | Value |
|---|---|
| Model | MacBook Pro M3 16, late 2023 (Mac15,7) |
| Chip | Apple M3 Pro |
| CPU cores | 12 (6 performance + 6 efficiency) |
| GPU cores | 18 |
| Unified memory | 36 GB |
| Storage | SSD |
| OS | macOS 26.6.2 (build 25G83) |
| Ollama version | 0.33.1 |
| Inference backend | Metal (100% GPU for every model tested — all fit fully in unified memory) |

## Machine 2: workstation1, single-GPU (original discrete GPU comparison)

| Field | Value |
|---|---|
| CPU | AMD Ryzen 7 9800X3D (8 cores / 16 threads) |
| System RAM | 123 GB |
| GPU | NVIDIA GeForce RTX 5070 Ti, 16 GB VRAM |
| GPU driver | 610.57.04 |
| Storage | NVMe SSD, 1.8 TB |
| OS | Fedora Linux 44 (Workstation Edition), kernel 7.1.13 |
| Ollama version | 0.33.3 |
| Inference backend | CUDA. Models are Ollama-served inside a Docker container with GPU passthrough (NVIDIA Container Toolkit) rather than a bare-metal install. |

## Machine 3: workstation1, dual-GPU (RTX 5090 added)

Same physical box as Machine 2, after adding a second GPU. Directly
comparable to Machine 2 for the shared model set.

| Field | Value |
|---|---|
| CPU | AMD Ryzen 7 9800X3D (8 cores / 16 threads) |
| System RAM | 123 GB |
| GPU 0 | NVIDIA GeForce RTX 5090, 32 GB VRAM (**new**) |
| GPU 1 | NVIDIA GeForce RTX 5070 Ti, 16 GB VRAM (carried over from Machine 2) |
| Combined VRAM | 48 GB across both GPUs |
| GPU driver | 610.57.04 (unchanged) |
| Storage | NVMe SSD (`/data`, 1.7 TB, ~300 GB free at test time) |
| OS | Fedora Linux 44 (Workstation Edition), kernel 7.1.13 |
| Ollama version | 0.33.3 |
| Inference backend | CUDA, via a **native** `ollama serve` install (`/usr/local/bin/ollama`, port 11434), not the Docker-GPU-passthrough setup used for Machine 2 — the original `ollama-test` container from that run no longer exists on this host. Confirmed no `CUDA_VISIBLE_DEVICES` restriction, so Ollama sees and auto-splits across both GPUs. This is a genuine backend difference from Machine 2 (native vs. containerized); noted here as a methodology caveat, not expected to materially affect tok/s given GPU passthrough overhead is negligible for compute-bound inference. |
| Model source | All 11 models were already present as locally-pulled Ollama models on this host (different tag names than `MODELS.md`'s originals in most cases — see the "Machine 3 tag mapping" table in `RESULTS.md` — but the same underlying GGUF/quant per `MODELS.md`), so no re-downloading was needed. |

## Why this matters for the results

- Apple Silicon's unified memory means the GPU has full-bandwidth access to
  all 36 GB, not just a fixed VRAM pool — every model tested on the Mac (up
  to ~22 GB) loaded 100% onto GPU with no CPU offload.
- Machine 2's discrete GPU only has 16 GB of VRAM. Any model whose Q4
  file exceeds that (everything ≥~18 GB in `MODELS.md`) partially or almost
  entirely offloads to system RAM, which is dramatically slower — system RAM
  bandwidth is roughly 10-15x lower than GPU VRAM bandwidth. This is why
  every 70B+/236B model tested on Machine 2 runs at 0.4-1.5 tok/s
  regardless of how well-tuned or how large it is: once a model falls off
  the "fits in VRAM" cliff, CPU/RAM bandwidth sets the pace, not GPU
  compute or model quality. See the CPU/GPU layer-split percentages recorded
  per model in `RESULTS.md` (via `ollama ps`) for exact ratios.
- **Machine 3 moves that cliff up dramatically.** With 48 GB combined VRAM
  across two GPUs, every dense 70B model (42-47 GB on disk) now lands at
  ~86% GPU-resident instead of ~27%, and the 236B MoE model (142 GB on disk,
  8% GPU-resident on Machine 2) reaches 25% GPU-resident. That's the single
  biggest driver of the ~4.5-4.7x speedup seen across every 70B+ model on
  Machine 3 vs. Machine 2 — see `RESULTS.md`'s Machine 3 section.
- Tokens/sec numbers are **not portable** across hardware — re-run the
  benchmarks on new hardware and compare tok/s and wall-clock time directly.
  Pass/fail test scores (correctness) generally *should* reproduce
  (deterministic-ish for a given model + quant + prompt, modulo sampling),
  but that assumption is only worth trusting once you've re-run it, not
  before — see `RESULTS.md`'s bug-reproducibility notes for cases where
  re-running actually changed a score. Machine 3's own results include two
  same-model repeat runs (GLM-4.7-Flash, DeepSeek-Coder-V2-Lite, Qwen2.5-72B)
  that landed on different bugs/scores each time, confirming this isn't
  hypothetical.
