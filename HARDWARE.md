# Hardware — machines compared

Two machines' results are recorded in `RESULTS.md`. When comparing against
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

## Machine 2: workstation1 (discrete GPU comparison)

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

## Why this matters for the results

- Apple Silicon's unified memory means the GPU has full-bandwidth access to
  all 36 GB, not just a fixed VRAM pool — every model tested on the Mac (up
  to ~22 GB) loaded 100% onto GPU with no CPU offload.
- workstation1's discrete GPU only has 16 GB of VRAM. Any model whose Q4
  file exceeds that (everything ≥~18 GB in `MODELS.md`) partially or almost
  entirely offloads to system RAM, which is dramatically slower — system RAM
  bandwidth is roughly 10-15x lower than GPU VRAM bandwidth. This is why
  every 70B+/236B model tested on workstation1 runs at 0.4-1.5 tok/s
  regardless of how well-tuned or how large it is: once a model falls off
  the "fits in VRAM" cliff, CPU/RAM bandwidth sets the pace, not GPU
  compute or model quality. See the CPU/GPU layer-split percentages recorded
  per model in `RESULTS.md` (via `ollama ps`) for exact ratios.
- Tokens/sec numbers are **not portable** across hardware — re-run the
  benchmarks on new hardware and compare tok/s and wall-clock time directly.
  Pass/fail test scores (correctness) generally *should* reproduce
  (deterministic-ish for a given model + quant + prompt, modulo sampling),
  but that assumption is only worth trusting once you've re-run it, not
  before — see `RESULTS.md`'s bug-reproducibility notes for cases where
  re-running actually changed a score.
