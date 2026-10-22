# Hardware — machines compared

Three machines' results are recorded in `RESULTS.md`. Current state of the main
box and how speed carries over to other hardware: see "Machine 3, October 2026
state" and "Speed on other hardware" below. When comparing against
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

## Machine 3, October 2026 state (all runs from "October 2026 new models" on)

Same box as above; the software and the settings that matter for speed have moved on since the
first Machine 3 runs. These are the numbers to use when comparing against other hardware.

| Field | Value |
|---|---|
| Motherboard | ASUS ProArt X870E-CREATOR WIFI |
| CPU | AMD Ryzen 7 9800X3D, 8 cores / 16 threads, up to 5.27 GHz, 96 MB L3 (3D V-Cache) |
| System RAM | 4 x 32 GB DDR5 (123 GB usable), dual channel, **3600 MT/s** configured (`dmidecode`); theoretical bandwidth 57.6 GB/s. Four DIMMs run well below DDR5's rated speeds; at 4800-5600 MT/s, models spilling to RAM would gain roughly a third or more |
| RAM bandwidth, effective | **~40 GB/s** (~70% of theoretical), derived from the CPU-bound runs: Devstral 2 reads ~30 GB of weights from RAM per token at 1.25 tok/s, Mistral Medium 3.5 ~46 GB at 0.9 tok/s |
| RAM bandwidth ceiling | The 9800X3D has a single CCD; its Infinity Fabric link reads about 60-65 GB/s whatever the memory speed. EXPO at 5200-5600 MT/s would bring the effective figure close to that (+20-35% for models spilling to RAM); two DIMMs at 6000-6400 would add only ~5-10% more while halving capacity |
| GPU 0 | NVIDIA GeForce RTX 5090: 32 GB GDDR7, 512-bit, **1,792 GB/s**, 21,760 CUDA cores, Blackwell (SM 12.0) |
| GPU 1 | NVIDIA GeForce RTX 5070 Ti: 16 GB GDDR7, 256-bit, **896 GB/s**, 8,960 CUDA cores, Blackwell (SM 12.0) |
| PCIe | 5.0, both cards at x8 (the board splits the CPU's x16 lanes x8/x8 with two cards) |
| GPU driver | 615.71.09 |
| Ollama | 0.40.5, native install, `OLLAMA_CONTEXT_LENGTH=65536`; the benchmarks pass `num_ctx=32768` |
| Other engines | Strata 0.1.44 / 0.1.45 (Qwen3.8-Flash-Next), PrismML llama.cpp fork (Ternary Bonsai) |
| Storage | NVMe SSD, `/data` 1.7 TB |

For reference, the Mac baseline (Machine 1, Apple M3 Pro) has 150 GB/s of unified-memory
bandwidth. Apple M5 family (estimates in `CHAMPIONS.md`): M5 153 GB/s (up to 32 GB), M5 Pro
307 GB/s (64 GB), M5 Max 460 or 614 GB/s (128 GB), M5 Ultra 1.2 TB/s (512 GB).

## Speed on other hardware: measured scaling

Single-stream generation reads every active weight once per token, so memory bandwidth is the
first-order factor. How closely speed follows bandwidth, from runs of the same model on two
devices:

| Model (all of it in fast memory on both) | Type | Devices | Bandwidth ratio | Speed ratio |
|---|---|---|---|---|
| Qwen2.5-Coder-7B | dense | M3 Pro → 5070 Ti | 6.0x | 5.1x |
| Gemma4-26B-A4B | MoE, 4B active | M3 Pro → 5070 Ti | 6.0x | 2.9x |
| GLM-4.7-Flash | MoE | M3 Pro → 5070 Ti | 6.0x | 2.6x |
| Qwen3-Coder-30B-A3B | MoE, 3B active | M3 Pro → 5070 Ti | 6.0x | 2.3x |
| Strata IQ3_S (Qwen3.8-Flash-Next) | MoE, partly in RAM | 5070 Ti → 5090 | 2.0x | 1.9-2.1x |
| Ternary Bonsai 2 27B | dense, ternary | 5070 Ti → 5090 | 2.0x | 1.6x |
| Ternary Bonsai 2 9B / 4B / 2B | dense, ternary | 5070 Ti → 5090 | 2.0x | 1.5x / 1.3x / 1.2x |

(The Mac → 5070 Ti rows also differ in software: Ollama 0.33 Metal vs. 0.33 CUDA in Docker.)

Fraction of the 5090's bandwidth limit reached (tok/s ÷ (1,792 GB/s ÷ GB read per token); GB per
token ≈ file size for dense models, file size × active/total parameters for MoE):

| Model | GB per token (approx.) | Limit | Measured | Share |
|---|---|---|---|---|
| Devstral Small 2 24B (dense) | 15 | 119 tok/s | 95 tok/s | ~80% |
| Mistral Small 3.2 24B (dense) | 15 | 119 tok/s | 98 tok/s | ~80% |
| Nemotron 3.5 Lightning 30B-A3B | 2.5 | 717 tok/s | 465 tok/s | ~65% |
| Gemma4-26B-A4B | 2.8 | 640 tok/s | 400-420 tok/s | ~65% |
| Nemotron 3.5 Bolt 74B-A9B (IQ2) | 2.8 | 640 tok/s | 160 tok/s | ~25% |

Models that do not fit in VRAM are bound by system RAM instead: on this box, seconds per token
≈ GB of weights in RAM ÷ 40 GB/s (Devstral 2: 30 ÷ 40 = 0.75 s, measured 0.8 s). MoE models
beat this estimate (Nemotron 3.5 Super runs at 23 tok/s), since each token touches only the
active experts.

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
